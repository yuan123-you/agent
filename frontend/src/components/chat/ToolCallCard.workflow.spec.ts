import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import ElementPlus from 'element-plus'
import ToolCallCard from './ToolCallCard.vue'
import type { OrderAction } from '@/types/api'

let app: App | undefined
let host: HTMLDivElement
const confirm = vi.fn(), cancel = vi.fn(), recover = vi.fn()
const workflow = (workflowStatus: string, recoverable = true) => ({
  actionId: 'a', workflowStatus, recoverable, nativeInterrupt: true, interrupted: workflowStatus === 'WAITING_APPROVAL',
})
function mount(overrides: Partial<OrderAction> = {}) {
  const action = reactive<OrderAction>({ type: 'ORDER_CREATE', actionId: 'a', expiresAt: '2099-01-01', status: 'PENDING', ...overrides })
  app = createApp(ToolCallCard, { action, onConfirm: confirm, onCancel: cancel, onRecover: recover }).use(ElementPlus)
  app.mount(host)
  return action
}
const button = (text: string) => [...host.querySelectorAll<HTMLButtonElement>('button')].find(b => b.textContent?.includes(text))
beforeEach(() => { vi.clearAllMocks(); host = document.createElement('div'); document.body.appendChild(host) })
afterEach(() => { app?.unmount(); app = undefined; host.remove() })

describe('manual native workflow recovery card', () => {
  it('offers manual recovery while waiting without automatically sending any decision', async () => {
    mount({ workflow: workflow('WAITING_APPROVAL') })
    await nextTick()
    expect(recover).not.toHaveBeenCalled()
    expect(confirm).not.toHaveBeenCalled()
    expect(button('核对并确认')).toBeDefined()
    expect(button('恢复操作')).toBeDefined()
    button('恢复操作')!.click()
    await nextTick()
    expect(recover).toHaveBeenCalledExactlyOnceWith('a')
    expect(confirm).not.toHaveBeenCalled()
    expect(cancel).not.toHaveBeenCalled()
  })

  it('shows executing/retryable as incomplete and hides approval controls', () => {
    mount({ status: 'EXECUTING', workflow: workflow('EXECUTING') })
    expect(host.textContent).toContain('执行中')
    expect(button('恢复操作')).toBeDefined()
    expect(button('核对并确认')).toBeUndefined()
    expect(button('放弃')).toBeUndefined()
    expect(button('查看订单')).toBeUndefined()
  })

  it('locks manual recovery during a request and returns to the canonical completion receipt', async () => {
    const action = mount({ status: 'RECOVERING', workflow: workflow('EXECUTING') })
    expect(button('恢复操作')?.disabled).toBe(true)
    button('恢复操作')!.click()
    expect(recover).not.toHaveBeenCalled()
    Object.assign(action, { status: 'CONFIRMED', workflow: workflow('COMPLETED', false), orderId: 42,
      orderNo: 'ORDER-42', receiverName: '服务器收货人', receiverAddress: '服务器地址' })
    await nextTick()
    expect(host.textContent).toContain('服务器地址')
    expect(host.textContent).toContain('ORDER-42')
    expect(button('查看订单')).toBeDefined()
    expect(button('恢复操作')).toBeUndefined()
    expect(button('核对并确认')).toBeUndefined()
  })

  it.each(['FAILED', 'EXPIRED'])('does not offer approval or success for terminal %s', status => {
    mount({ status: status as OrderAction['status'], workflow: workflow(status, false) })
    expect(button('核对并确认')).toBeUndefined()
    expect(button('恢复操作')).toBeUndefined()
    expect(button('查看订单')).toBeUndefined()
    expect(host.textContent).not.toContain('可重试')
  })

  it('allows only recovery for a retryable workflow error, not approval', () => {
    mount({ status: 'FAILED', workflow: { ...workflow('FAILED'), error: { code: 'RETRYABLE' } } })
    expect(button('恢复操作')).toBeDefined()
    expect(button('核对并确认')).toBeUndefined()
  })

  it('keeps legacy retry UI and omits recovery when workflow support is absent', () => {
    mount({ status: 'FAILED' })
    expect(button('核对并确认')).toBeDefined()
    expect(button('恢复操作')).toBeUndefined()
  })
})

it.each(['EXECUTING', 'FAILED', 'EXPIRED'])('does not display stale local success over a %s workflow', status => {
  mount({ status: 'CONFIRMED', orderId: 42, orderNo: 'STALE', workflow: workflow(status, status === 'EXECUTING') })
  expect(button('查看订单')).toBeUndefined()
  expect(host.querySelector('.order-no')).toBeNull()
  if (status === 'EXECUTING') expect(button('恢复操作')).toBeDefined()
})

it('does not render success for an erroneous completed workflow', () => {
  mount({ status: 'CONFIRMED', orderId: 42,
    workflow: { ...workflow('COMPLETED'), error: { code: 'RETRYABLE' } } })
  expect(button('查看订单')).toBeUndefined()
  expect(button('恢复操作')).toBeDefined()
})

it.each([
  ['EXPIRED', { code: 2011, message: 'action is no longer awaiting approval' }],
  ['CANCELLED', { code: 409, message: 'action is no longer awaiting approval' }],
])('shows canonical %s despite its terminal diagnostic error', (status, error) => {
  mount({ status: status as OrderAction['status'], workflow: { ...workflow(status, false), error } })
  expect(host.textContent).toContain(status === 'EXPIRED' ? '已过期' : '已放弃')
  expect(button('核对并确认')).toBeUndefined()
  expect(button('放弃')).toBeUndefined()
  expect(button('恢复操作')).toBeUndefined()
  expect(button('查看订单')).toBeUndefined()
})

it('renders a backwards-compatible old cleared-error empty map as completed', () => {
  mount({ status: 'CONFIRMED', orderId: 42, orderNo: 'ORDER-42', workflow: { ...workflow('COMPLETED', false), error: {} } })
  expect(host.textContent).toContain('已确认')
  expect(button('查看订单')).toBeDefined()
})

it('offers recovery rather than stale success when native provenance arrives from history status alone', () => {
  mount({ nativeManaged: true, status: 'CONFIRMED', orderId: 42, receiverAddress: '原始地址A' })
  expect(button('查看订单')).toBeUndefined()
  expect(button('核对并确认')).toBeUndefined()
  expect(button('恢复操作')).toBeDefined()
})
