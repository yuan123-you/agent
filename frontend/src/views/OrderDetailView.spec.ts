import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, reactive, type App } from 'vue'
import OrderDetailView from './OrderDetailView.vue'
const mocks = vi.hoisted(() => ({ detail: vi.fn(), replace: vi.fn(), push: vi.fn(), confirm: vi.fn(), receipt: vi.fn() }))
let route: any
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ replace: mocks.replace, push: mocks.push, back: vi.fn() }) }))
vi.mock('element-plus', () => ({ ElMessage: { success: vi.fn(), error: vi.fn() }, ElMessageBox: { confirm: mocks.confirm } }))
vi.mock('@/api', () => ({ apiOrderDetail: mocks.detail, apiCancelOrder: vi.fn(), apiConfirmReceipt: mocks.receipt, apiOrderSimulateShip: vi.fn(), apiPayOrder: vi.fn() }))
const value = (id = 5, reviewed = true) => ({ orderId: id, orderNo: `ORD-${id}`, status: 'DELIVERED', totalAmount: 10, items: [{ orderItemId: 51, productId: 488, productName: '商品', reviewed, canReview: !reviewed, price: 10, quantity: 1 }] })
const flush = async () => { for (let i = 0; i < 10; i++) await nextTick() }
let app: App; let host: HTMLDivElement
async function mount() {
  host = document.createElement('div'); document.body.appendChild(host); app = createApp(OrderDetailView)
  const basic = defineComponent({ setup(_, { slots, attrs }) { return () => h('div', attrs, slots.default?.()) } })
  app.component('ElImage', basic); app.component('ElIcon', basic); app.component('ElButton', basic); app.mount(host); await flush()
}
beforeEach(() => { vi.clearAllMocks(); route = reactive({ params: { id: '5' } }); mocks.detail.mockResolvedValue(value()) })
afterEach(() => { app?.unmount(); host?.remove() })
describe('order detail state', () => {
  it('does not offer a review when all purchased products are already reviewed', async () => {
    await mount(); expect(host.querySelector('.osb-actions')?.textContent).not.toContain('评价晒单')
  })
  it('offers navigation only for an eligible unreviewed product', async () => {
    mocks.detail.mockResolvedValue(value(5, false)); await mount(); expect(host.querySelector('.osb-actions')?.textContent).toContain('评价晒单')
  })
  it('reloads when a reused detail component receives another order id', async () => {
    await mount(); mocks.detail.mockResolvedValue(value(6)); route.params.id = '6'; await flush()
    expect(mocks.detail).toHaveBeenLastCalledWith(6); expect(host.textContent).toContain('ORD-6'); expect(host.textContent).not.toContain('ORD-5')
  })
  it('ignores responses from a previous order after navigating to a new order', async () => {
    let resolve!: (v: any) => void; mocks.detail.mockReturnValueOnce(new Promise(r => { resolve = r })).mockResolvedValueOnce(value(6))
    await mount(); route.params.id = '6'; await flush(); resolve(value(5)); await flush()
    expect(host.textContent).toContain('ORD-6'); expect(host.textContent).not.toContain('ORD-5')
  })
  it('does not mislabel a server outage as an unknown order', async () => {
    mocks.detail.mockRejectedValue({ code: 9999 }); await mount(); expect(mocks.replace).not.toHaveBeenCalled()
  })
  it('does not confirm receipt for a different order after a pending confirmation dialog', async () => {
    let confirm!: () => void
    mocks.confirm.mockReturnValue(new Promise<void>(resolve => { confirm = resolve }))
    mocks.detail.mockResolvedValue({ ...value(), status: 'SHIPPED' })
    await mount(); host.querySelector<HTMLElement>('.osb-actions > div')!.click(); await flush()
    expect(mocks.confirm).toHaveBeenCalledTimes(1)
    mocks.detail.mockResolvedValue({ ...value(6), status: 'SHIPPED' }); route.params.id = '6'; await flush()
    confirm(); await flush()
    expect(mocks.receipt).not.toHaveBeenCalled()
  })

})
