// @vitest-environment node
// Node-only helpers are explicitly typed; production code remains browser-only.
declare function require(id: 'node:fs'): { readFileSync(path: URL, encoding: string): string }
declare function require(id: 'node:vm'): { runInNewContext(source: string, context: Record<string, unknown>): unknown }
const { readFileSync } = require('node:fs')
const { runInNewContext } = require('node:vm')
import { describe, expect, it, vi } from 'vitest'

const origin = 'https://mall.test'
const source = () => readFileSync(new URL('../../public/image-cache-sw.js', import.meta.url), 'utf8')
const image = (headers = {}) => new Response('image bytes', {
  headers: { 'Content-Type': 'image/webp', ...headers },
})

function storage() {
  const entries = new Map<string, Response>()
  const cache = {
    match: vi.fn(async (request: Request) => entries.get(request.url)?.clone()),
    put: vi.fn(async (request: Request, response: Response) => { entries.set(request.url, response.clone()) }),
    delete: vi.fn(async (request: Request) => entries.delete(request.url)),
    keys: vi.fn(async () => [...entries.keys()].map(url => new Request(url))),
  }
  return {
    entries, cache,
    open: vi.fn(async () => cache),
    keys: vi.fn(async () => ['ai-mall-images-v0', 'unrelated-cache']),
    delete: vi.fn(async () => true),
  }
}

function worker(store = storage(), fetcher = vi.fn(async () => image())) {
  const handlers: Record<string, (event: any) => void> = {}
  let now = Date.now()
  const background: Promise<unknown>[] = []
  const self = {
    location: { origin },
    registration: { scope: `${origin}/` },
    addEventListener: (name: string, handler: any) => { handlers[name] = handler },
    skipWaiting: vi.fn(async () => {}),
    clients: { claim: vi.fn(async () => {}) },
  }
  runInNewContext(source(), {
    self, caches: store, fetch: fetcher, URL, Response, Headers,
    Date: { now: () => now, parse: Date.parse }, Map, Promise,
  })
  function request(path = '/api/v1/product-images/test.webp', overrides = {}) {
    const req = new Request(new URL(path, origin))
    Object.defineProperty(req, 'destination', { value: 'image', configurable: true })
    Object.entries(overrides).forEach(([key, value]) => Object.defineProperty(req, key, { value }))
    let result: Promise<Response> | undefined
    handlers.fetch({ request: req, respondWith: (value: Promise<Response>) => { result = value },
      waitUntil: (value: Promise<unknown>) => { background.push(value) } })
    return result
  }
  return { request, store, fetcher, self, handlers, drain: () => Promise.all(background), advance: (ms: number) => { now += ms } }
}

describe('image cache worker', () => {
  it('persists an image and serves it without network even after worker restart', async () => {
    const first = worker()
    expect(await (await first.request())!.text()).toBe('image bytes')
    await first.drain()
    const restarted = worker(first.store, vi.fn(async () => { throw new Error('offline') }))
    expect(await (await restarted.request())!.text()).toBe('image bytes')
    expect(restarted.fetcher).not.toHaveBeenCalled()
  })

  it('does not delay image display while persistent storage is writing', async () => {
    const w = worker()
    let release!: () => void
    w.store.cache.put.mockImplementationOnce(() => new Promise<void>(resolve => { release = resolve }))
    let delivered = false
    const response = w.request()!.then(value => { delivered = true; return value })
    try {
      await vi.waitFor(() => expect(w.store.cache.put).toHaveBeenCalled())
      await vi.waitFor(() => expect(delivered).toBe(true), { timeout: 100 })
    } finally {
      release()
      await response
    }
  })
  it('coalesces simultaneous requests with independently readable responses', async () => {
    const w = worker()
    const responses = await Promise.all([w.request(), w.request(), w.request()])
    expect(await Promise.all(responses.map(response => response!.text()))).toEqual(Array(3).fill('image bytes'))
    expect(w.fetcher).toHaveBeenCalledTimes(1)
  })

  it('subtracts apparent response age even if HTTP cache supplies no Age header', async () => {
    const w = worker(storage(), vi.fn(async () => image({
      'Cache-Control': 'max-age=60', Date: new Date(Date.now() - 50000).toUTCString(),
    })))
    await w.request()
    await w.drain()
    w.advance(11000)
    await w.request()
    expect(w.fetcher).toHaveBeenCalledTimes(2)
    await w.drain()
  })

  it('does not extend freshness while a cache write waits in the queue', async () => {
    const w = worker(storage(), vi.fn(async () => image({ 'Cache-Control': 'max-age=60' })))
    let release!: () => void
    w.store.cache.put.mockImplementationOnce(() => new Promise<void>(resolve => { release = resolve }))
    await w.request('/blocked.webp')
    await vi.waitFor(() => expect(w.store.cache.put).toHaveBeenCalledTimes(1))
    await w.request('/queued.webp')
    w.advance(120000)
    release()
    await w.drain()
    expect(w.store.entries.has(`${origin}/queued.webp`)).toBe(false)
  })

  it('starts network refresh without waiting for expired-cache deletion', async () => {
    const w = worker()
    await w.request()
    await w.drain()
    w.advance(30 * 86400 * 1000 + 1)
    let release!: () => void
    w.store.cache.delete.mockImplementationOnce(() => new Promise<boolean>(resolve => {
      release = () => resolve(true)
    }))
    const response = w.request()
    try {
      await vi.waitFor(() => expect(w.store.cache.delete).toHaveBeenCalled())
      await vi.waitFor(() => expect(w.fetcher).toHaveBeenCalledTimes(2), { timeout: 100 })
    } finally {
      release()
      await response
      await w.drain()
    }
  })
  it('caches public cross-origin images using an anonymous CORS request', async () => {
    const external = 'https://picsum.photos/seed/product/600/600'
    const redirected = image()
    Object.defineProperty(redirected, 'redirected', { value: true })
    const w = worker(storage(), vi.fn(async () => redirected))
    expect(await (await w.request(external))!.text()).toBe('image bytes')
    await w.drain()
    expect(w.fetcher).toHaveBeenCalledWith(expect.objectContaining({ url: external }), {
      mode: 'cors', credentials: 'omit', cache: 'reload',
    })
    const restarted = worker(w.store, vi.fn(async () => { throw new Error('offline') }))
    expect(await (await restarted.request(external))!.text()).toBe('image bytes')
    expect(restarted.fetcher).not.toHaveBeenCalled()
  })

  it.each([401, 403, 200])('preserves original loading when anonymous CORS returns %s or non-image HTML', async status => {
    const w = worker()
    w.fetcher.mockResolvedValueOnce(new Response('login required', {
      status, headers: { 'Content-Type': 'text/html' },
    }))
    expect(await (await w.request('https://private.test/image.webp'))!.text()).toBe('image bytes')
    expect(w.fetcher).toHaveBeenCalledTimes(2)
    expect(w.fetcher.mock.calls[1]).toHaveLength(1)
    await w.drain()
    expect(w.store.entries.size).toBe(0)
  })
  it('falls back to original image loading if the remote server denies CORS', async () => {
    const opaque = image()
    Object.defineProperty(opaque, 'status', { value: 0 })
    Object.defineProperty(opaque, 'type', { value: 'opaque' })
    const w = worker(storage(), vi.fn(async () => opaque))
    w.fetcher.mockRejectedValueOnce(new TypeError('CORS denied'))
    expect(await w.request('https://private.test/image.webp')).toBeDefined()
    expect(w.fetcher).toHaveBeenCalledTimes(2)
    expect(w.fetcher.mock.calls[1]).toHaveLength(1)
    await w.drain()
    expect(w.store.entries.size).toBe(0)
  })
  it('keeps URL query versions separate', async () => {
    const w = worker()
    await w.request('/image.webp?v=1')
    await w.request('/image.webp?v=2')
    expect(w.fetcher).toHaveBeenCalledTimes(2)
  })

  it('expires images after 30 days and respects shorter max-age', async () => {
    const w = worker()
    await w.request()
    w.advance(30 * 86400 * 1000 + 1)
    await w.request()
    expect(w.fetcher).toHaveBeenCalledTimes(2)
    const short = worker(storage(), vi.fn(async () => image({ 'Cache-Control': 'public, max-age=1' })))
    await short.request()
    short.advance(1001)
    await short.request()
    expect(short.fetcher).toHaveBeenCalledTimes(2)
  })

  it.each([
    () => new Response('missing', { status: 404 }),
    () => new Response('html', { headers: { 'Content-Type': 'text/html' } }),
    () => image({ 'Cache-Control': 'no-store' }),
    () => image({ 'Cache-Control': 'private, max-age=100' }),
    () => image({ 'Cache-Control': 'no-cache' }),
  ])('does not cache errors, non-images or restricted responses', async factory => {
    const w = worker(storage(), vi.fn(async () => factory()))
    await w.request()
    await w.request()
    expect(w.fetcher).toHaveBeenCalledTimes(2)
    expect(w.store.entries.size).toBe(0)
  })

  it.each([
    ['/api/v1/products', { destination: '' }],
    ['/script.js', { destination: 'script' }],
    ['http://other.test/image.webp', {}],
    ['/image.webp', { method: 'POST' }],
    ['/image.webp', { cache: 'no-store' }],
    ['/image.webp', { cache: 'reload' }],
    ['/image.webp', { headers: new Headers({ Range: 'bytes=0-10' }) }],
  ])('leaves excluded request %s to the browser', (path, overrides) => {
    const w = worker()
    expect(w.request(path, overrides)).toBeUndefined()
    expect(w.fetcher).not.toHaveBeenCalled()
  })

  it('bounds the cache to 200 images, evicting oldest entries', async () => {
    const w = worker()
    for (let i = 0; i < 201; i++) await w.request(`/image-${i}.webp`)
    await w.drain()
    expect(w.store.entries.size).toBe(200)
    expect(w.store.entries.has(`${origin}/image-0.webp`)).toBe(false)
    expect(w.store.entries.has(`${origin}/image-200.webp`)).toBe(true)
  })

  it('still returns network images if cache storage is unavailable or full', async () => {
    const w = worker()
    w.store.open.mockRejectedValueOnce(new Error('storage disabled'))
    expect(await (await w.request())!.text()).toBe('image bytes')
    w.store.cache.put.mockRejectedValueOnce(new Error('quota exceeded'))
    expect(await (await w.request('/another.webp'))!.text()).toBe('image bytes')
  })

  it('clears failed in-flight requests so a later retry can succeed', async () => {
    const w = worker()
    w.fetcher.mockRejectedValueOnce(new Error('offline'))
    await expect(w.request()).rejects.toThrow('offline')
    expect(await (await w.request())!.text()).toBe('image bytes')
  })

  it('activates immediately and removes only obsolete image caches', async () => {
    const w = worker()
    let pending: Promise<unknown> | undefined
    w.handlers.install({ waitUntil: (value: Promise<unknown>) => { pending = value } })
    await pending
    expect(w.self.skipWaiting).toHaveBeenCalled()
    w.handlers.activate({ waitUntil: (value: Promise<unknown>) => { pending = value } })
    await pending
    expect(w.store.delete).toHaveBeenCalledWith('ai-mall-images-v0')
    expect(w.store.delete).not.toHaveBeenCalledWith('unrelated-cache')
    expect(w.self.clients.claim).toHaveBeenCalled()
  })
})
