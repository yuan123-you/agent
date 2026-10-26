import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { subscribeOrderStatus } from './index'
const flush = async () => { for (let i = 0; i < 8; i++) await Promise.resolve() }
beforeEach(() => localStorage.setItem('token', 'test-token'))
afterEach(() => { vi.unstubAllGlobals(); localStorage.clear() })
describe('order status stream lifecycle', () => {
  it('cancels an established stream without aborting an already fulfilled fetch', async () => {
    let complete!: (v: any) => void
    const reader = { read: vi.fn(() => new Promise(r => { complete = r })), cancel: vi.fn(async () => complete({ done: true })), releaseLock: vi.fn() }
    const fetcher = vi.fn().mockResolvedValue({ ok: true, body: { getReader: () => reader } })
    vi.stubGlobal('fetch', fetcher)
    const listener = vi.fn(); const stream = subscribeOrderStatus(listener); await flush(); stream.stop(); stream.stop(); await flush()
    expect(reader.cancel).toHaveBeenCalledTimes(1)
    expect(reader.releaseLock).toHaveBeenCalledTimes(1)
    expect(fetcher.mock.calls[0][1].signal.aborted).toBe(false)
    expect(listener).not.toHaveBeenCalled()
  })
  it('aborts a still-pending connection attempt on teardown', async () => {
    const fetcher = vi.fn((_url, init) => new Promise((_resolve, reject) => init.signal.addEventListener('abort', () => reject(new DOMException('Cancelled', 'AbortError')))))
    vi.stubGlobal('fetch', fetcher); const stream = subscribeOrderStatus(vi.fn()); stream.stop(); await flush()
    expect(fetcher.mock.calls[0][1].signal.aborted).toBe(true)
  })
  it('does not deliver queued status events after stop', async () => {
    let complete!: (v: any) => void
    const reader = { read: vi.fn(() => new Promise(r => { complete = r })), cancel: vi.fn(async () => {}), releaseLock: vi.fn() }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, body: { getReader: () => reader } }))
    const listener = vi.fn(); const stream = subscribeOrderStatus(listener); await flush(); stream.stop()
    complete({ done: false, value: new TextEncoder().encode('event: order_status\ndata: {"orderId":5}\n\n') }); await flush()
    expect(listener).not.toHaveBeenCalled()
  })
})
