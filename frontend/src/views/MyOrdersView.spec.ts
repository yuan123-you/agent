import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, reactive, type App } from 'vue'
import MyOrdersView from './MyOrdersView.vue'

const mocks = vi.hoisted(() => ({
  list: vi.fn(), review: vi.fn(), replace: vi.fn(), stop: vi.fn(), success: vi.fn(),
  subscribe: vi.fn(), detail: vi.fn(), push: vi.fn(), back: vi.fn(),
}))
let route: any
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ replace: mocks.replace, push: mocks.push, back: mocks.back }) }))
vi.mock('element-plus', () => ({ ElMessage: { success: mocks.success, error: vi.fn() }, ElMessageBox: { confirm: vi.fn() } }))
vi.mock('@/api', () => ({
  apiMyOrders: mocks.list, apiOrderDetail: mocks.detail, apiReviewCreate: mocks.review, subscribeOrderStatus: mocks.subscribe,
  apiCancelOrder: vi.fn(), apiConfirmReceipt: vi.fn(), apiPayOrder: vi.fn(),
}))
const order = (reviewed = false, id = 5) => ({ orderId: id, orderNo: `ORD-${id}`, status: 'DELIVERED', totalAmount: 10,
  items: [{ orderItemId: 51, productId: 488, productName: '商品A', quantity: 1, price: 10, reviewed, canReview: !reviewed }] })
const deferred = <T,>() => { let resolve!: (v: T) => void; const promise = new Promise<T>(r => { resolve = r }); return { promise, resolve } }
const flush = async () => { for (let i = 0; i < 12; i++) await nextTick() }
let app: App | undefined
let host: HTMLDivElement
const passthrough = defineComponent({ setup(_, { slots }) { return () => h('div', slots.default?.()) } })
async function mount() {
  host = document.createElement('div'); document.body.appendChild(host)
  app = createApp(MyOrdersView)
  for (const name of ['ElScrollbar', 'ElCard', 'ElTag', 'ElIcon', 'ElTabPane', 'ElRate', 'ElCheckbox', 'ElSelect', 'ElOption', 'ArrowLeft']) app.component(name, passthrough)
  app.component('ElButton', defineComponent({ props: ['disabled', 'loading'], setup(p, { slots, attrs }) { return () => h('button', { ...attrs, disabled: !!p.disabled || !!p.loading }, slots.default?.()) } }))
  app.component('ElDialog', defineComponent({ props: ['modelValue'], setup(p, { slots }) { return () => p.modelValue ? h('section', { class: 'test-dialog' }, [slots.default?.(), slots.footer?.()]) : null } }))
  app.component('ElInput', defineComponent({ props: ['modelValue'], emits: ['update:modelValue'], setup(p, { emit }) { return () => h('textarea', { value: p.modelValue, onInput: (e: Event) => emit('update:modelValue', (e.target as HTMLTextAreaElement).value) }) } }))
  app.component('ElTabs', defineComponent({ emits: ['update:modelValue', 'tab-change'], setup(_, { emit, slots }) { return () => h('div', [h('button', { class: 'test-change-tab', onClick: () => { emit('update:modelValue', 'PAID'); emit('tab-change') } }, '切换'), h('button', { class: 'test-review-tab', onClick: () => { emit('update:modelValue', 'PENDING_REVIEW'); emit('tab-change') } }, '切换待评价'), slots.default?.()]) } }))
  app.component('ElImage', defineComponent({ props: ['src', 'alt'], setup(p) { return () => h('img', { src: p.src, alt: p.alt }) } }))
  app.component('ElEmpty', passthrough)
  app.mount(host); await flush()
}
function button(text: string) { return Array.from(host.querySelectorAll<HTMLButtonElement>('button')).find(b => b.textContent?.trim() === text) }
async function enterReview() {
  button('评价晒单')!.click(); await flush()
  const input = host.querySelector('textarea')!; input.value = '真实心得'; input.dispatchEvent(new Event('input')); await flush()
}
beforeEach(() => {
  vi.clearAllMocks(); route = reactive({ query: {}, params: {} })
  mocks.list.mockResolvedValue({ records: [order()], total: 1 }); mocks.review.mockResolvedValue(undefined)
  mocks.replace.mockImplementation(async ({ query }: any) => { route.query = query })
  mocks.subscribe.mockReturnValue({ stop: mocks.stop })
})
afterEach(() => { app?.unmount(); app = undefined; host?.remove() })

describe('order reviews and list lifecycle', () => {
  it('shows order skeletons while the initial page is pending, then renders actual orders', async () => {
    const pending = deferred<any>(); mocks.list.mockReturnValueOnce(pending.promise)
    await mount(); expect(host.querySelector('[data-loading-variant="list"]')).not.toBeNull()
    expect(host.textContent).not.toContain('加载中')
    pending.resolve({ records: [order()], total: 1 }); await flush()
    expect(host.querySelector('[data-loading-variant]')).toBeNull(); expect(host.textContent).toContain('ORD-5')
  })

  it('does not offer another review for a persisted reviewed product', async () => {
    mocks.list.mockResolvedValue({ records: [order(true)], total: 1 }); await mount()
    expect(button('评价晒单')).toBeUndefined()
    expect(host.textContent).toContain('已评价')
  })
  it('consumes review navigation intent once and does not replay it on SSE refresh', async () => {
    route.query = { reviewOrderId: '5', keep: 'yes' }; await mount()
    expect(mocks.replace).toHaveBeenCalledWith(expect.objectContaining({ query: { keep: 'yes' } }))
    expect(host.querySelector('.test-dialog')).not.toBeNull()
    const input = host.querySelector('textarea')!; input.value = '评价'; input.dispatchEvent(new Event('input')); await flush()
    button('发表评价')!.click(); await flush()
    mocks.subscribe.mock.calls[0][0]({ orderId: 5, orderNo: 'ORD-5', status: 'DELIVERED' }); await flush()
    expect(host.querySelector('.test-dialog')).toBeNull()
  })
  it('does not open an already-reviewed order from an old URL', async () => {
    route.query = { reviewOrderId: '5' }; mocks.list.mockResolvedValue({ records: [order(true)], total: 1 }); await mount()
    expect(host.querySelector('.test-dialog')).toBeNull()
    expect(route.query.reviewOrderId).toBeUndefined()
  })
  it('does not claim success or close the editor after a rejected submission', async () => {
    mocks.review.mockRejectedValue({ code: 2004, message: '已评价' }); await mount(); await enterReview()
    button('发表评价')!.click(); await flush()
    expect(mocks.success).not.toHaveBeenCalled()
    expect(host.querySelector('.test-dialog')).not.toBeNull()
  })
  it('guards in-flight repeat submission and includes purchase evidence', async () => {
    const pending = deferred<void>(); mocks.review.mockReturnValue(pending.promise); await mount(); await enterReview()
    button('发表评价')!.click(); button('发表评价')!.click(); await flush()
    expect(mocks.review).toHaveBeenCalledTimes(1)
    expect(mocks.review).toHaveBeenCalledWith(488, expect.objectContaining({ orderItemId: 51 }))
    pending.resolve(); await flush()
    expect(button('评价晒单')).toBeUndefined()
  })
  it('selects an unreviewed item rather than always reviewing the first product', async () => {
    const value = order(true); value.items.push({ ...value.items[0], orderItemId: 52, productId: 489, productName: '商品B', reviewed: false, canReview: true })
    mocks.list.mockResolvedValue({ records: [value], total: 1 }); await mount(); await enterReview(); button('发表评价')!.click(); await flush()
    expect(mocks.review).toHaveBeenCalledWith(489, expect.objectContaining({ orderItemId: 52 }))
  })
  it('never opens an empty order or submits a fabricated product id', async () => {
    mocks.list.mockResolvedValue({ records: [{ ...order(), items: [] }], total: 1 }); route.query = { reviewOrderId: '5' }; await mount()
    expect(host.querySelector('.test-dialog')).toBeNull(); expect(button('评价晒单')).toBeUndefined(); expect(mocks.review).not.toHaveBeenCalled()
  })
  it('ignores an old response and loads the new filter while the old request is pending', async () => {
    const old = deferred<any>(); const current = deferred<any>(); mocks.list.mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise)
    await mount(); host.querySelector<HTMLButtonElement>('.test-change-tab')!.click(); await flush()
    expect(mocks.list).toHaveBeenCalledTimes(2)
    current.resolve({ records: [{ ...order(false, 6), status: 'PAID' }], total: 1 }); await flush()
    old.resolve({ records: [order(false, 5)], total: 1 }); await flush()
    expect(host.textContent).toContain('ORD-6'); expect(host.textContent).not.toContain('ORD-5')
  })
  it('cleans up the status subscription when leaving the list', async () => {
    await mount(); app!.unmount(); app = undefined; expect(mocks.stop).toHaveBeenCalledTimes(1)
  })
  it('preserves an unresolved off-page review intent through an SSE reload', async () => {
    const target = deferred<any>(); route.query = { reviewOrderId: '50' }
    mocks.detail.mockReturnValue(target.promise); await mount()
    mocks.subscribe.mock.calls[0][0]({ orderId: 5, orderNo: 'ORD-5', status: 'DELIVERED' }); await flush()
    target.resolve(order(false, 50)); await flush()
    expect(host.querySelector('.test-dialog')?.textContent).toContain('ORD-50')
  })
  it('does not let an older off-page review response replace a newer intent or its draft', async () => {
    const old = deferred<any>(); const latest = deferred<any>(); await mount()
    mocks.detail.mockReturnValueOnce(old.promise).mockReturnValueOnce(latest.promise)
    route.query = { reviewOrderId: '50' }; await flush()
    route.query = { reviewOrderId: '60' }; await flush()
    latest.resolve(order(false, 60)); await flush()
    const input = host.querySelector('textarea')!; input.value = '保留新订单草稿'; input.dispatchEvent(new Event('input')); await flush()
    old.resolve(order(false, 50)); await flush()
    expect(host.querySelector('.test-dialog')?.textContent).toContain('ORD-60')
    expect(host.querySelector('textarea')?.value).toBe('保留新订单草稿')
  })
  it('does not re-enable a successful review from a list response captured before submission', async () => {
    const stale = deferred<any>(); const submitted = deferred<void>(); await mount(); await enterReview()
    mocks.review.mockReturnValue(submitted.promise); button('发表评价')!.click(); await flush()
    mocks.list.mockReturnValue(stale.promise)
    mocks.subscribe.mock.calls[0][0]({ orderId: 5, orderNo: 'ORD-5', status: 'DELIVERED' }); await flush()
    submitted.resolve(); await flush()
    stale.resolve({ records: [order(false)], total: 1 }); await flush()
    expect(button('评价晒单')).toBeUndefined(); expect(host.textContent).toContain('已评价')
  })

  it('processes a new review intent while the first page is waiting for an older detail', async () => {
    const old = deferred<any>(); const latest = deferred<any>()
    route.query = { reviewOrderId: '50' }
    mocks.detail.mockReturnValueOnce(old.promise).mockReturnValueOnce(latest.promise)
    await mount()
    route.query = { reviewOrderId: '60' }; await flush()
    expect(mocks.detail).toHaveBeenLastCalledWith(60)
    latest.resolve(order(false, 60)); await flush()
    old.resolve(order(false, 50)); await flush()
    expect(host.querySelector('.test-dialog')?.textContent).toContain('ORD-60')
  })

})


describe('mature order presentation', () => {
  it('shows product images, quantity totals and consistently formatted order amounts', async () => {
    const value = { ...order(), totalAmount: 39.9, source: 'AI', createdAt: '2026-10-28T10:20:00',
      items: [{ ...order().items[0], productImage: '/test-product.png', quantity: 2, price: 19.95 }] }
    mocks.list.mockResolvedValue({ records: [value], total: 1 }); await mount()
    expect(host.querySelector('.item-image')?.getAttribute('src')).toBe('/test-product.png')
    expect(host.querySelector('.item-image')?.getAttribute('alt')).toBe('商品A')
    expect(host.querySelector('.order-total')?.textContent).toContain('39.90')
    expect(host.querySelector('.order-total')?.textContent).toContain('共 2 件商品')
    expect(host.querySelector('.source')?.textContent).toContain('AI 下单')
    expect(host.querySelector('.time')?.textContent).toContain('2026-10-28 10:20')
  })
  it.each([
    ['PENDING_PAYMENT', '待付款', '去支付'], ['PAID', '待发货', undefined],
    ['SHIPPED', '待收货', '确认收货'], ['DELIVERED', '已完成', '评价晒单'], ['CANCELLED', '已取消', undefined],
  ])('gives %s its own customer-facing status and primary action', async (status, label, action) => {
    mocks.list.mockResolvedValue({ records: [{ ...order(), status }], total: 1 }); await mount()
    expect(host.querySelector('.order-status')?.textContent).toContain(label)
    if (action) expect(button(action)?.classList.contains('order-primary-action')).toBe(true)
    else expect(host.querySelector('.order-primary-action')).toBeNull()
    expect(button('查看详情')).toBeDefined()
  })
  it('opens the actual product and order rather than a placeholder target', async () => {
    await mount()
    host.querySelector<HTMLButtonElement>('.item-product-link')!.click(); await flush()
    expect(mocks.push).toHaveBeenCalledWith('/products/488')
    button('查看详情')!.click(); await flush()
    expect(mocks.push).toHaveBeenCalledWith('/orders/5')
  })
  it('does not fabricate shipping information when none was returned', async () => {
    mocks.list.mockResolvedValue({ records: [{ ...order(), status: 'SHIPPED' }], total: 1 }); await mount()
    expect(host.querySelector('.order-status-hint')?.textContent).toContain('商品已发出')
    expect(host.textContent).not.toMatch(/顺丰|今日送达|免运费|旗舰店/)
  })
  it('distinguishes failed loading from empty orders and offers a working retry', async () => {
    mocks.list.mockRejectedValueOnce(new Error('network')); await mount()
    expect(host.querySelector('.orders-error')).not.toBeNull()
    expect(host.querySelector('.orders-empty')).toBeNull()
    button('重新加载')!.click(); await flush()
    expect(mocks.list).toHaveBeenCalledTimes(2)
    expect(host.querySelector('.orders-error')).toBeNull()
    expect(host.textContent).toContain('ORD-5')
  })
  it('gives the empty list a real shopping entry point', async () => {
    mocks.list.mockResolvedValue({ records: [], total: 0 }); await mount()
    expect(host.querySelector('.orders-empty')?.textContent).toContain('暂无订单')
    button('去逛逛')!.click(); await flush()
    expect(mocks.push).toHaveBeenCalledWith('/products')
  })
})


describe('order card edge cases', () => {
  it('counts units across multiple products instead of counting product rows', async () => {
    const value = order()
    value.items[0].quantity = 2
    value.items.push({ ...value.items[0], orderItemId: 52, productId: 489, quantity: 3 })
    mocks.list.mockResolvedValue({ records: [value], total: 1 }); await mount()
    expect(host.querySelectorAll('.item')).toHaveLength(2)
    expect(host.querySelector('.order-total')?.textContent).toContain('共 5 件商品')
  })
  it('shows the returned carrier and tracking number without inventing a delivery promise', async () => {
    mocks.list.mockResolvedValue({ records: [{ ...order(), status: 'SHIPPED', deliveryCompany: '测试物流', logisticsNo: 'TEST123' }], total: 1 }); await mount()
    expect(host.querySelector('.order-status-hint')?.textContent).toContain('测试物流 · TEST123')
    expect(host.querySelector('.order-status-hint')?.textContent).not.toContain('预计')
  })
  it('uses the selected status in its empty-state explanation and server total', async () => {
    await mount()
    mocks.list.mockResolvedValueOnce({ records: [], total: 0 })
    host.querySelector<HTMLButtonElement>('.test-change-tab')!.click(); await flush()
    expect(host.querySelector('.orders-empty')?.textContent).toContain('暂无待发货订单')
    expect(host.querySelector('.order-count')?.textContent).toContain('共 0 笔')
  })
  it('keeps loaded orders and retries the failed next page without duplicating the first page', async () => {
    mocks.list.mockResolvedValueOnce({ records: [order()], total: 2 }); await mount()
    mocks.list.mockRejectedValueOnce(new Error('network'))
    button('加载更多订单')!.click(); await flush()
    expect(host.querySelectorAll('.order-card')).toHaveLength(1)
    expect(host.querySelector('.orders-error')).not.toBeNull()
    mocks.list.mockResolvedValueOnce({ records: [order(false, 6)], total: 2 })
    button('重新加载')!.click(); await flush()
    expect(mocks.list).toHaveBeenLastCalledWith({ page: 2, size: 10 })
    expect(host.querySelectorAll('.order-card')).toHaveLength(2)
    expect(host.querySelector('.orders-error')).toBeNull()
  })
})


describe('consumer shopping order cards', () => {
  it('puts totals and horizontal actions after products rather than in management-table columns', async () => {
    await mount()
    expect(host.querySelector('.orders-column-head')).toBeNull()
    const card = host.querySelector('.order-card')!
    expect(card.querySelector('.order-card-footer .order-total')).not.toBeNull()
    expect(card.querySelector('.order-card-footer .actions')).not.toBeNull()
    expect(card.querySelector('.item-code')).toBeNull()
    expect(card.querySelector('.order-store')?.textContent).toContain('AI Mall')
  })
  it('makes repeat purchase and support actual navigation rather than decorative buttons', async () => {
    await mount()
    button('再次购买')!.click(); await flush()
    expect(mocks.push).toHaveBeenCalledWith('/products/488')
    host.querySelector<HTMLButtonElement>('.order-support')!.click(); await flush()
    expect(mocks.push).toHaveBeenCalledWith('/assistant')
  })
  it('does not offer single-product repurchase for a multi-product or unavailable-product order', async () => {
    const value = order(); value.items.push({ ...value.items[0], productId: 489 })
    mocks.list.mockResolvedValueOnce({ records: [value, { ...order(false, 6), items: [] }], total: 2 }); await mount()
    expect(button('再次购买')).toBeUndefined()
  })
  it('queries completed orders for the review tab, skips reviewed pages and counts only eligible orders', async () => {
    await mount()
    mocks.list.mockResolvedValueOnce({ records: [order(true)], total: 2 })
      .mockResolvedValueOnce({ records: [order(false, 6)], total: 2 })
    host.querySelector<HTMLButtonElement>('.test-review-tab')!.click(); await flush()
    expect(mocks.list).toHaveBeenLastCalledWith({ page: 2, size: 10, status: 'DELIVERED' })
    expect(host.querySelectorAll('.order-card')).toHaveLength(1)
    expect(host.textContent).toContain('ORD-6')
    expect(host.textContent).not.toContain('ORD-5')
    expect(host.querySelector('.order-count')?.textContent).toContain('共 1 笔')
  })
  it('removes a fully reviewed order from the review tab after submission', async () => {
    await mount()
    host.querySelector<HTMLButtonElement>('.test-review-tab')!.click(); await flush()
    await enterReview(); button('发表评价')!.click(); await flush()
    expect(host.querySelectorAll('.order-card')).toHaveLength(0)
    expect(host.querySelector('.orders-empty')?.textContent).toContain('暂无待评价订单')
  })
})


describe('pending-review pagination accuracy', () => {
  it('does not claim a completed-order total is the pending-review total before all pages are examined', async () => {
    await mount()
    mocks.list.mockResolvedValueOnce({ records: [order(false, 6)], total: 2 })
    host.querySelector<HTMLButtonElement>('.test-review-tab')!.click(); await flush()
    expect(host.querySelector('.order-count')?.textContent).toContain('已找到 1 笔')
    mocks.list.mockResolvedValueOnce({ records: [order(true, 7)], total: 2 })
    button('加载更多订单')!.click(); await flush()
    expect(host.querySelectorAll('.order-card')).toHaveLength(1)
    expect(host.querySelector('.order-count')?.textContent).toContain('共 1 笔')
    expect(button('加载更多订单')).toBeUndefined()
  })
  it('reaches a genuine empty state only after all completed orders are checked', async () => {
    await mount()
    mocks.list.mockResolvedValueOnce({ records: [order(true, 6)], total: 2 })
      .mockResolvedValueOnce({ records: [order(true, 7)], total: 2 })
    host.querySelector<HTMLButtonElement>('.test-review-tab')!.click(); await flush()
    expect(host.querySelector('.orders-empty')?.textContent).toContain('暂无待评价订单')
    expect(host.querySelector('.order-count')?.textContent).toContain('共 0 笔')
  })
  it('does not scan another review page after a newer filter replaces its pending request', async () => {
    await mount(); const old = deferred<any>()
    mocks.list.mockReturnValueOnce(old.promise)
    host.querySelector<HTMLButtonElement>('.test-review-tab')!.click(); await flush()
    mocks.list.mockResolvedValueOnce({ records: [{ ...order(false, 9), status: 'PAID' }], total: 1 })
    host.querySelector<HTMLButtonElement>('.test-change-tab')!.click(); await flush()
    old.resolve({ records: [order(true, 6)], total: 10 }); await flush()
    expect(mocks.list).toHaveBeenCalledTimes(3)
    expect(host.textContent).toContain('ORD-9')
    expect(host.textContent).not.toContain('ORD-6')
  })
})


it('shows already-refunded money separately from the original paid amount',async()=>{
  mocks.list.mockResolvedValue({records:[{...order(),refundedAmount:4.5}],total:1});await mount()
  expect(host.querySelector('.order-refund-amount')?.textContent).toContain('4.50')
  expect(host.querySelector('.order-total')?.textContent).toContain('10.00')
})
