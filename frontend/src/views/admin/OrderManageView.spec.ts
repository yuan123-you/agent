import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, inject, nextTick, provide, toRef, type App, type Ref } from 'vue'
import OrderManageView from './OrderManageView.vue'
const api = vi.hoisted(() => ({ list: vi.fn(), ship: vi.fn(), deliver: vi.fn(), error: vi.fn() }))
vi.mock('@/api', () => ({ apiAdminOrders: api.list, apiAdminShip: api.ship, apiAdminDeliver: api.deliver }))
vi.mock('element-plus', () => ({ ElMessage: { success: vi.fn(), error: api.error } }))
const flush = async () => { for (let i = 0; i < 8; i++) await nextTick() }
let app: App, host: HTMLDivElement
const order = (dispatchableQuantity = 1) => ({ orderId: 30, orderNo: 'ORDER', status: 'PAID', totalAmount: 20, items: [{ productId: 1, productName: '商品', quantity: 2, dispatchableQuantity }] })
async function mount(row = order()) {
  api.list.mockResolvedValue({ records: [row], total: 1 }); api.ship.mockResolvedValue(undefined)
  host = document.createElement('div'); document.body.append(host); app = createApp(OrderManageView)
  const basic = defineComponent({ setup(_, { slots, attrs }) { return () => h('div', attrs, [slots.default?.(), slots.footer?.()]) } })
  for (const name of ['ElScrollbar', 'ElSelect', 'ElOption', 'ElTag', 'ElForm', 'ElFormItem']) app.component(name, basic)
  app.component('ElTable', defineComponent({ props: ['data'], setup(props, { slots }) { provide('rows', toRef(props, 'data')); return () => h('div', slots.default?.()) } }))
  app.component('ElTableColumn', defineComponent({ setup(_, { slots }) { const rows = inject<Ref<any[]>>('rows')!; return () => h('div', rows.value.map(row => slots.default?.({ row }))) } }))
  app.component('ElButton', defineComponent({ props: { disabled: Boolean }, setup(props, { slots, attrs }) { return () => h('button', { ...attrs, disabled: props.disabled }, slots.default?.()) } }))
  app.component('ElDialog', defineComponent({ props: ['modelValue'], setup(props, { slots }) { return () => props.modelValue ? h('section', [slots.default?.(), slots.footer?.()]) : null } }))
  app.component('ElInput', defineComponent({ props: ['modelValue'], emits: ['update:modelValue'], setup(props, { emit, attrs }) { return () => h('input', { ...attrs, value: props.modelValue, onInput: (e: Event) => emit('update:modelValue', (e.target as HTMLInputElement).value) }) } }))
  app.mount(host); await flush()
}
async function click(label: string) { const button = [...host.querySelectorAll('button')].find(b => b.textContent === label)!; button.click(); await flush() }
async function enter(carrier: string, tracking: string) { const inputs = host.querySelectorAll('input'); for (const [i, value] of [carrier, tracking].entries()) { inputs[i].value = value; inputs[i].dispatchEvent(new Event('input', { bubbles: true })) }; await flush() }
beforeEach(() => vi.clearAllMocks())
afterEach(() => { app?.unmount(); host?.remove() })
describe('authoritative admin fulfillment', () => {
  it('shows dispatchable units without hiding original purchased quantity', async () => { await mount(); expect(host.textContent).toContain('待发1'); expect(host.textContent).toContain('购买2') })
  it('does not offer shipping when all fulfillment units were released', async () => { await mount(order(0)); const ship = [...host.querySelectorAll('button')].find(b => b.textContent === '发货'); expect(!ship || ship.disabled).toBe(true) })
  it('requires operator-entered tracking before submit', async () => { await mount(); await click('发货'); await click('确认发货'); expect(api.ship).not.toHaveBeenCalled(); expect(api.error).toHaveBeenCalled() })
  it('bounds tracking and carrier and sends trimmed operator input', async () => {
    await mount(); await click('发货'); await enter('', 'T'.repeat(101)); await click('确认发货'); expect(api.ship).not.toHaveBeenCalled()
    await enter('C'.repeat(81), 'REAL'); await click('确认发货'); expect(api.ship).not.toHaveBeenCalled()
    await enter(' Carrier ', ' REAL '); await click('确认发货'); expect(api.ship).toHaveBeenCalledWith(30, 'REAL', 'Carrier')
  })
})
