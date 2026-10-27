import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import ElementPlus from 'element-plus'
import ProductManageView from './ProductManageView.vue'

const api = vi.hoisted(() => ({
  apiAdminProducts: vi.fn(), apiAdminSkus: vi.fn(), apiAdminCatalogCategories: vi.fn(),
  apiAdminBrands: vi.fn(), apiAdminCoupons: vi.fn(), apiAdminSeckills: vi.fn(),
}))
vi.mock('@/api', async importOriginal => ({ ...await importOriginal<object>(), ...api }))
const flush = async () => { for (let i = 0; i < 12; i++) await nextTick() }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(r => { resolve = r }); return { promise, resolve } }
let app: App | undefined
let host: HTMLDivElement
async function mount() {
  host = document.createElement('div'); document.body.appendChild(host)
  app = createApp(ProductManageView).use(ElementPlus); app.mount(host); await flush()
}
beforeEach(() => {
  vi.clearAllMocks()
  api.apiAdminProducts.mockResolvedValue({ records: [], total: 0 })
  for (const request of [api.apiAdminSkus, api.apiAdminCatalogCategories, api.apiAdminBrands, api.apiAdminCoupons, api.apiAdminSeckills]) request.mockResolvedValue([])
})
afterEach(() => { app?.unmount(); host?.remove(); document.body.innerHTML = '' })

describe('independently loaded admin panels', () => {
  it.each(['categories', 'brands'])('%s keeps a table skeleton until its catalog request settles', async tab => {
    const pending = deferred<any[]>(); api.apiAdminCatalogCategories.mockReturnValue(pending.promise)
    await mount(); host.querySelector<HTMLElement>(`#tab-${tab}`)!.click(); await flush()
    const panel = host.querySelector(`#pane-${tab}`)!
    expect(panel.querySelector('[data-loading-variant="table"]')).not.toBeNull()
    expect(panel.querySelector('.el-table__empty-text')).toBeNull()
    pending.resolve([]); await flush(); expect(panel.querySelector('[data-loading-variant]')).toBeNull()
  })

  it('both promotion tabs use table skeletons while their shared request is pending', async () => {
    const pending = deferred<any[]>(); api.apiAdminCoupons.mockReturnValue(pending.promise)
    await mount(); host.querySelector<HTMLElement>('#tab-promotions')!.click(); await flush()
    expect(host.querySelector('#pane-coupons [data-loading-variant="table"]')).not.toBeNull()
    host.querySelector<HTMLElement>('#tab-seckills')!.click(); await flush()
    expect(host.querySelector('#pane-seckills [data-loading-variant="table"]')).not.toBeNull()
    pending.resolve([]); await flush(); expect(host.querySelector('#pane-promotions [data-loading-variant]')).toBeNull()
  })

  it('shows a skeleton in the SKU dialog rather than reporting an empty specification list', async () => {
    api.apiAdminProducts.mockResolvedValue({ records: [{ id: 5, name: '真实商品', price: 20, stock: 2, category: 'PHONE', status: 'ON_SALE' }], total: 1 })
    await mount()
    const pending = deferred<any[]>(); api.apiAdminSkus.mockReturnValueOnce(pending.promise)
    Array.from(host.querySelectorAll<HTMLButtonElement>('button')).find(b => b.textContent?.trim() === '规格')!.click(); await flush()
    expect(document.querySelector('[role="dialog"] [data-loading-variant="table"]')).not.toBeNull()
    pending.resolve([]); await flush(); expect(document.querySelector('[role="dialog"] [data-loading-variant]')).toBeNull()
  })
})
