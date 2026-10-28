import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { AxiosAdapter, InternalAxiosRequestConfig } from 'axios'

vi.mock('element-plus', () => ({ ElMessage: { error: vi.fn() } }))

const CACHE_PREFIX = 'aimall:hot-content:v1:'
const data = { records: [{ id: 1, name: '商品' }], total: 1, page: 1, size: 24 }
const flush = async () => { for (let i = 0; i < 12; i++) await Promise.resolve() }
const session = (userId: number) => {
  localStorage.setItem('token', 'test-token')
  localStorage.setItem('user', JSON.stringify({ userId, role: 'CUSTOMER' }))
}
const cacheKeys = () => Object.keys(localStorage).filter(key => key.startsWith(CACHE_PREFIX))
const response = (config: InternalAxiosRequestConfig, value: unknown = data) => ({
  status: 200, statusText: 'OK', data: { code: 0, data: JSON.parse(JSON.stringify(value)) }, config, headers: {},
})
let request: typeof import('./request')
let adapter: ReturnType<typeof vi.fn<AxiosAdapter>>

beforeEach(async () => {
  vi.resetModules()
  localStorage.clear()
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-10-28T08:00:00Z'))
  session(1)
  request = await import('./request')
  adapter = vi.fn<AxiosAdapter>(async config => response(config))
  request.default.defaults.adapter = adapter
})
afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
  vi.unstubAllEnvs()
  localStorage.clear()
})

describe('user-scoped hot content', () => {
  it('persists GET results across module reloads without caching credentials', async () => {
    await request.get('/products', { params: { page: 1, size: 24 } })
    expect(cacheKeys()).toHaveLength(1)
    expect(localStorage.getItem(cacheKeys()[0]!)).not.toContain('test-token')
    vi.resetModules()
    request = await import('./request')
    request.default.defaults.adapter = adapter
    expect(await request.get('/products', { params: { size: 24, page: 1 } })).toEqual(data)
    expect(adapter).toHaveBeenCalledTimes(1)
  })

  it('isolates deployments using the API base path', async () => {
    await request.get('/products')
    vi.stubEnv('BASE_URL', '/another-mall/')
    vi.resetModules()
    request = await import('./request')
    request.default.defaults.adapter = adapter
    await request.get('/products')
    expect(adapter).toHaveBeenCalledTimes(2)
    expect(cacheKeys()).toHaveLength(2)
  })

  it('keys every filter/page/sort and ignores object property order', async () => {
    await request.get('/products', { params: { page: 1, category: 'PHONE', sort: 'price_asc' } })
    await request.get('/products', { params: { sort: 'price_asc', category: 'PHONE', page: 1 } })
    await request.get('/products', { params: { page: 2, category: 'PHONE', sort: 'price_asc' } })
    await request.get('/products', { params: { page: 1, category: 'HOME', sort: 'price_asc' } })
    await request.get('/products', { params: { page: 1, category: 'PHONE', sort: 'price_desc' } })
    expect(adapter).toHaveBeenCalledTimes(4)
  })

  it.each([
    ['/products', 60_000], ['/products/categories', 600_000],
    ['/catalog/categories', 600_000], ['/catalog/brands', 600_000],
  ])('expires %s at its exact TTL', async (url, ttl) => {
    await request.get(url)
    vi.advanceTimersByTime(ttl - 1)
    await request.get(url)
    expect(adapter).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(1)
    await request.get(url)
    expect(adapter).toHaveBeenCalledTimes(2)
  })

  it('isolates users and guests without discarding a different user bucket', async () => {
    await request.get('/products')
    session(2)
    await request.get('/products')
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    await request.get('/products')
    session(1)
    await request.get('/products')
    expect(adapter).toHaveBeenCalledTimes(3)
    expect(cacheKeys()).toHaveLength(3)
  })

  it('does not mutate cached data through a returned response', async () => {
    await request.get('/products')
    const hit = await request.get<typeof data>('/products')
    hit.records[0]!.name = 'changed'
    expect((await request.get<typeof data>('/products')).records[0]!.name).toBe('商品')
    expect(adapter).toHaveBeenCalledTimes(1)
  })

  it('deduplicates simultaneous misses', async () => {
    const values = await Promise.all([request.get('/products'), request.get('/products')])
    expect(values).toEqual([data, data])
    expect(adapter).toHaveBeenCalledTimes(1)
  })

  it('does not retain failed requests and retries normally', async () => {
    adapter.mockRejectedValueOnce(new Error('offline'))
    await expect(request.get('/products')).rejects.toThrow('offline')
    await request.get('/products')
    await request.get('/products')
    expect(adapter).toHaveBeenCalledTimes(2)
  })

  it.each(['/products/1', '/catalog/products/1/skus', '/orders/my', '/cart', '/addresses',
    '/promotions/coupons', '/auth/me', '/conversations', '/admin/products'])('never caches %s', async url => {
    await request.get(url)
    await request.get(url)
    expect(adapter).toHaveBeenCalledTimes(2)
    expect(cacheKeys()).toHaveLength(0)
  })

  it('supports explicit bypass without reading or populating the cache', async () => {
    await request.get('/products')
    adapter.mockImplementationOnce(async config => response(config, { fresh: true }))
    await expect(request.get('/products', { cache: false })).resolves.toEqual({ fresh: true })
    await expect(request.get('/products')).resolves.toEqual(data)
    expect(adapter).toHaveBeenCalledTimes(2)
  })

  it('preserves request cancellation even with a warm cache', async () => {
    await request.get('/products')
    const controller = new AbortController()
    controller.abort()
    const axios = (await import('axios')).default
    await expect(request.get('/products', { signal: controller.signal })).rejects.toSatisfy(axios.isCancel)
    expect(adapter).toHaveBeenCalledTimes(1)
  })

  it('bypasses requests with custom headers or non-flat query values', async () => {
    await request.get('/products')
    await request.get('/products', { headers: { 'X-Variant': 'other' } })
    await request.get('/products', { params: { filter: { category: 'PHONE' } } })
    await request.get('/products', { params: { filter: { category: 'HOME' } } })
    expect(adapter).toHaveBeenCalledTimes(4)
  })

  it('refreshes expired tokens even with a warm cache', async () => {
    await request.get('/products')
    const axios = (await import('axios')).default
    localStorage.setItem('token', `header.${btoa(JSON.stringify({ exp: Date.now() / 1000 - 1 }))}.sig`)
    localStorage.setItem('refreshToken', 'refresh')
    const refresh = vi.spyOn(axios, 'post').mockResolvedValue({ data: { data: { accessToken: 'new-token' } } })
    await request.get('/products')
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(adapter).toHaveBeenCalledTimes(2)
  })

  it.each(['{bad-json', 'null', '{}', '[null]'])('ignores corrupt storage %s', async corrupt => {
    await request.get('/products')
    localStorage.setItem(cacheKeys()[0]!, corrupt)
    await expect(request.get('/products')).resolves.toEqual(data)
    expect(adapter).toHaveBeenCalledTimes(2)
  })

  it('falls back to network if cache storage is unavailable', async () => {
    const getItem = Storage.prototype.getItem
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(function (this: Storage, key) {
      if (key.startsWith(CACHE_PREFIX)) throw new Error('disabled')
      return getItem.call(this, key)
    })
    await expect(request.get('/products')).resolves.toEqual(data)
  })

  it('returns successful data when the storage quota is exhausted', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('Full', 'QuotaExceededError') })
    await expect(request.get('/products')).resolves.toEqual(data)
  })

  it('disables caching if a signed-in user identity cannot be read', async () => {
    localStorage.setItem('user', '{bad-json')
    await request.get('/products')
    await request.get('/products')
    expect(adapter).toHaveBeenCalledTimes(2)
    expect(cacheKeys()).toHaveLength(0)
  })

  it('evicts the least recently used entry after 50 query combinations', async () => {
    for (let page = 1; page <= 50; page++) {
      await request.get('/products', { params: { page } })
      vi.advanceTimersByTime(1)
    }
    await request.get('/products', { params: { page: 1 } })
    vi.advanceTimersByTime(1)
    await request.get('/products', { params: { page: 51 } })
    await request.get('/products', { params: { page: 1 } })
    expect(adapter).toHaveBeenCalledTimes(51)
    await request.get('/products', { params: { page: 2 } })
    expect(adapter).toHaveBeenCalledTimes(52)
  })

  it('bounds persisted payload size as well as entry count', async () => {
    adapter.mockImplementation(async config => response(config, { text: 'x'.repeat(600_000) }))
    await request.get('/products', { params: { page: 1 } })
    await request.get('/products', { params: { page: 2 } })
    expect(localStorage.getItem(cacheKeys()[0]!)!.length).toBeLessThanOrEqual(1_000_000)
    await request.get('/products', { params: { page: 1 } })
    expect(adapter).toHaveBeenCalledTimes(3)
  })
})

describe('hot content invalidation', () => {
  it.each(['post', 'put', 'del'] as const)('invalidates after successful %s mutations', async method => {
    await request.get('/products')
    await request[method]('/merchant/products/1')
    await request.get('/products')
    expect(adapter).toHaveBeenCalledTimes(3)
  })

  it('retains valid data after a failed write', async () => {
    await request.get('/products')
    adapter.mockRejectedValueOnce(new Error('write failed'))
    await expect(request.post('/merchant/products')).rejects.toThrow('write failed')
    await request.get('/products')
    expect(adapter).toHaveBeenCalledTimes(2)
  })

  it('removes the old user bucket on logout and account switch', async () => {
    const { createPinia, setActivePinia } = await import('pinia')
    setActivePinia(createPinia())
    const auth = (await import('@/stores/auth')).useAuthStore()
    await request.get('/products')
    auth.logoutLocal()
    expect(cacheKeys()).toHaveLength(0)
    auth.setAuth({ accessToken: 'next-token', user: { userId: 2, username: 'two', nickname: 'two', role: 'CUSTOMER' } })
    await request.get('/products')
    auth.setAuth({ accessToken: 'third-token', user: { userId: 3, username: 'three', nickname: 'three', role: 'CUSTOMER' } })
    expect(cacheKeys()).toHaveLength(0)
  })

  it('clears the cache when authentication expires', async () => {
    await request.get('/products')
    const axios = (await import('axios')).default
    adapter.mockImplementationOnce(async config => {
      throw new axios.AxiosError('unauthorized', 'ERR_BAD_RESPONSE', config, undefined, {
        status: 401, statusText: 'Unauthorized', data: { code: 1003 }, config, headers: {},
      })
    })
    await expect(request.get('/orders/my')).rejects.toBeDefined()
    expect(cacheKeys()).toHaveLength(0)
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('retains the cache after an HTTP-200 business error', async () => {
    await request.get('/products')
    adapter.mockImplementationOnce(async config => ({ ...response(config), data: { code: 2001, message: 'rejected' } }))
    await expect(request.post('/merchant/products')).rejects.toEqual({ code: 2001, message: 'rejected' })
    await request.get('/products')
    expect(adapter).toHaveBeenCalledTimes(2)
  })

  it('invalidates after a successful upload', async () => {
    await request.get('/products')
    await request.upload('/merchant/product-images', new FormData())
    await request.get('/products')
    expect(adapter).toHaveBeenCalledTimes(3)
  })

  it('does not refill a cleared cache after logout and re-login to the same account', async () => {
    const { createPinia, setActivePinia } = await import('pinia')
    setActivePinia(createPinia())
    const auth = (await import('@/stores/auth')).useAuthStore()
    let finish!: () => void
    adapter.mockImplementationOnce(config => new Promise(resolve => { finish = () => resolve(response(config)) }))
    const oldRead = request.get('/products')
    await flush()
    auth.logoutLocal()
    auth.setAuth({ accessToken: 'new-session', user: { userId: 1, username: 'one', nickname: 'one', role: 'CUSTOMER' } })
    finish()
    await oldRead
    expect(cacheKeys()).toHaveLength(0)
    await request.get('/products')
    expect(adapter).toHaveBeenCalledTimes(2)
  })

  it('does not refill or reuse an old in-flight read after invalidation', async () => {
    let finish!: () => void
    adapter.mockImplementationOnce(config => new Promise(resolve => { finish = () => resolve(response(config, { old: true })) }))
    const oldRead = request.get('/products')
    await flush()
    await request.post('/merchant/products/1')
    await expect(request.get('/products')).resolves.toEqual(data)
    finish()
    await oldRead
    await expect(request.get('/products')).resolves.toEqual(data)
    expect(adapter).toHaveBeenCalledTimes(3)
  })

  it('does not put a late response in another user cache', async () => {
    let finish!: () => void
    adapter.mockImplementationOnce(config => new Promise(resolve => { finish = () => resolve(response(config)) }))
    const oldRead = request.get('/products')
    await flush()
    session(2)
    finish()
    await oldRead
    expect(cacheKeys()).toHaveLength(0)
    await request.get('/products')
    expect(adapter).toHaveBeenCalledTimes(2)
  })
})
