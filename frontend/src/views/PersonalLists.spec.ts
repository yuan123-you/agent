import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, type App } from 'vue'
import FavoritesView from './FavoritesView.vue'
import HistoryView from './HistoryView.vue'
const mocks = vi.hoisted(() => ({ back: vi.fn(), push: vi.fn(), favorites: vi.fn(), history: vi.fn() }))
vi.mock('vue-router', () => ({ useRouter: () => ({ back: mocks.back, push: mocks.push }) }))
vi.mock('@/api', () => ({ apiFavorites: mocks.favorites, apiHistory: mocks.history, apiFavoriteToggle: vi.fn(), apiHistoryClear: vi.fn() }))
vi.mock('element-plus', () => ({ ElMessage: { success: vi.fn() }, ElMessageBox: { confirm: vi.fn() } }))
let app: App; let host: HTMLDivElement
beforeEach(() => {
  vi.clearAllMocks(); localStorage.setItem('token', 'test'); window.history.pushState({}, '', '/')
  mocks.favorites.mockResolvedValue({ records: [], total: 0 }); mocks.history.mockResolvedValue({ records: [], total: 0 })
})
afterEach(() => { app?.unmount(); host?.remove(); localStorage.clear() })
describe('personal list navigation', () => {
  it.each([['favorites', FavoritesView, mocks.favorites, 'cards'], ['history', HistoryView, mocks.history, 'list']] as const)('%s shows a skeleton until its request settles', async (_name, component, request, variant) => {
    let resolve!: (value: any) => void
    request.mockReturnValueOnce(new Promise(r => { resolve = r }))
    host = document.createElement('div'); document.body.appendChild(host); app = createApp(component)
    const basic = defineComponent({ setup(_, { slots }) { return () => h('div', slots.default?.()) } })
    for (const name of ['ElScrollbar', 'ElIcon', 'ElEmpty', 'ElButton', 'ElImage']) app.component(name, basic)
    app.mount(host); await nextTick()
    expect(host.querySelector(`[data-loading-variant="${variant}"]`)).not.toBeNull()
    expect(host.textContent).not.toContain('加载中')
    resolve({ records: [], total: 0 }); for (let i = 0; i < 6; i++) await nextTick()
    expect(host.querySelector('[data-loading-variant]')).toBeNull()
  })

  it.each([['favorites', FavoritesView], ['history', HistoryView]] as const)('%s has a working back action', async (_name, component) => {
    host = document.createElement('div'); document.body.appendChild(host); app = createApp(component)
    const basic = defineComponent({ setup(_, { slots }) { return () => h('div', slots.default?.()) } })
    for (const name of ['ElScrollbar', 'ElIcon', 'ElEmpty', 'ElButton', 'ElImage', 'ArrowLeft']) app.component(name, basic)
    app.mount(host); await nextTick(); host.querySelector<HTMLButtonElement>('button[title="返回"]')!.click(); await nextTick()
    expect(mocks.back).toHaveBeenCalledTimes(1)
  })
})
