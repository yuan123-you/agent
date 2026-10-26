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
  app.component('ElTabs', defineComponent({ emits: ['update:modelValue', 'tab-change'], setup(_, { emit, slots }) { return () => h('div', [h('button', { class: 'test-change-tab', onClick: () => { emit('update:modelValue', 'PAID'); emit('tab-change') } }, '切换'), slots.default?.()]) } }))
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
