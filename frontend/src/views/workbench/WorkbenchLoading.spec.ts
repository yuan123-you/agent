import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import ElementPlus from 'element-plus'
import WorkbenchView from './WorkbenchView.vue'

const api = vi.hoisted(() => ({ apiPending: vi.fn(), apiServicing: vi.fn(), apiWorkbenchSla: vi.fn(), apiClaim: vi.fn() }))
vi.mock('@/api', () => api)
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
const flush = async () => { for (let i = 0; i < 12; i++) await nextTick() }
const conversation = { conversationId: 8, userNickname: '真实买家', title: '待接入咨询', summary: '需要人工协助' }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(r => { resolve = r }); return { promise, resolve } }
let app: App | undefined
let host: HTMLDivElement
async function mount() {
  host = document.createElement('div'); document.body.appendChild(host)
  app = createApp(WorkbenchView).use(ElementPlus); app.mount(host); await flush()
}
beforeEach(() => {
  vi.useFakeTimers(); vi.clearAllMocks()
  api.apiPending.mockResolvedValue([conversation]); api.apiServicing.mockResolvedValue([])
  api.apiWorkbenchSla.mockResolvedValue({ pendingCount: 1, servicingCount: 0, todayNewCount: 1, todayHandledCount: 0, avgFirstResponseSeconds: 0 })
})
afterEach(() => { app?.unmount(); host?.remove(); vi.clearAllTimers(); vi.useRealTimers() })

describe('support workload loading', () => {
  it('shows skeletons before its first response instead of an empty workload', async () => {
    const pending = deferred<any[]>(); api.apiPending.mockReturnValueOnce(pending.promise)
    await mount(); expect(host.querySelector('[data-loading-variant="stats"]')).not.toBeNull()
    expect(host.querySelector('[data-loading-variant="text"]')).not.toBeNull()
    pending.resolve([conversation]); await flush()
    expect(host.querySelector('[data-loading-variant]')).toBeNull(); expect(host.textContent).toContain('真实买家')
  })

  it('keeps existing cards and their expanded state mounted during background polling', async () => {
    await mount(); const card = host.querySelector('.conv-card')!
    const pending = deferred<any[]>(); api.apiPending.mockReturnValueOnce(pending.promise)
    vi.advanceTimersByTime(10000); await flush()
    expect(host.querySelector('.conv-card')).toBe(card)
    expect(host.querySelector('[data-loading-variant]')).toBeNull()
    pending.resolve([conversation]); await flush()
    expect(host.querySelector('.conv-card')).toBe(card)
  })
})
