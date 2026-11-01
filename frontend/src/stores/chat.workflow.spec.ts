import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { ElMessage } from 'element-plus'
import { useChatStore } from './chat'
import type { OrderAction } from '@/types/api'

const api = vi.hoisted(() => ({ confirm: vi.fn(), cancel: vi.fn(), recover: vi.fn(), status: vi.fn(), detail: vi.fn(), messages: vi.fn() }))
vi.mock('@/api', () => ({
  apiConfirmOrderAction: api.confirm, apiCancelOrderAction: api.cancel, apiRecoverOrderAction: api.recover,
  apiOrderActionStatus: api.status, apiConversationDetail: api.detail, apiMessages: api.messages,
  apiCloseConversation: vi.fn(), apiConversationStatus: vi.fn(), apiConversations: vi.fn(),
  apiCreateConversation: vi.fn(), apiHumanMessage: vi.fn(), apiCancelHuman: vi.fn(),
  apiMessagesAfter: vi.fn(), apiSatisfaction: vi.fn(),
}))
vi.mock('@/composables/useSseChat', () => ({ streamChat: vi.fn() }))
vi.mock('element-plus', () => ({ ElMessage: { success: vi.fn(), error: vi.fn() } }))

const delivery = { receiverName: '服务器收货人', receiverPhone: '13900139000', receiverAddress: '服务器已提交地址' }
const approved = { receiverName: '本地修改', receiverPhone: '13800138000', receiverAddress: '本地旧地址' }
const workflow = (workflowStatus = 'WAITING_APPROVAL', recoverable = true, error?: Record<string, unknown> | null) => ({
  actionId: 'native-1', workflowStatus, nativeInterrupt: true, interrupted: workflowStatus === 'WAITING_APPROVAL', recoverable, ...(error !== undefined ? { error } : {}),
})
const completed = () => ({
  type: 'ORDER_CREATE', actionStatus: 'CONFIRMED', orderId: 42, orderNo: 'ORDER-42', status: 'PENDING_PAYMENT',
  totalAmount: 80, ...delivery, workflow: workflow('COMPLETED', false),
})
function setup(overrides: Partial<OrderAction> = {}) {
  const chat = useChatStore()
  chat.messages = [{ role: 'AI', content: '', actions: [{
    type: 'ORDER_CREATE', actionId: 'native-1', expiresAt: '2099-01-01T00:00:00Z', status: 'PENDING',
    ...approved, ...overrides,
  }] }]
  return { chat, action: chat.messages[0].actions![0] }
}
beforeEach(() => { setActivePinia(createPinia()); vi.clearAllMocks(); api.confirm.mockReset(); api.recover.mockReset(); api.cancel.mockReset() })

describe('native workflow receipts and explicit recovery', () => {
  it.each(['WAITING_APPROVAL', 'EXECUTING', 'FAILED', 'EXPIRED'])('does not confirm on HTTP 200 %s workflow', async status => {
    api.confirm.mockResolvedValue({ workflow: workflow(status, status === 'EXECUTING') })
    const { chat, action } = setup()
    await chat.confirmOrderAction(action.actionId, approved)
    expect(action.status).not.toBe('CONFIRMED')
    expect(action.orderId).toBeUndefined()
    expect(ElMessage.success).not.toHaveBeenCalled()
    expect(api.recover).not.toHaveBeenCalled()
    if (status !== 'WAITING_APPROVAL') {
      await chat.confirmOrderAction(action.actionId, approved)
      expect(api.confirm).toHaveBeenCalledTimes(1)
    }
  })

  it('recovers WAITING_APPROVAL without approving, cancelling, or scheduling execution', async () => {
    api.recover.mockResolvedValue({ workflow: workflow() })
    const { chat, action } = setup({ workflow: workflow() })
    await chat.recoverOrderAction(action.actionId)
    expect(api.recover).toHaveBeenCalledExactlyOnceWith(action.actionId)
    expect(api.confirm).not.toHaveBeenCalled()
    expect(api.cancel).not.toHaveBeenCalled()
    expect(action.status).toBe('PENDING')
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('does not resend approval after a recoverable gateway timeout', async () => {
    api.confirm.mockRejectedValue({ code: 5002, data: { actionId: 'native-1', recoverable: true } })
    const { chat, action } = setup()
    await chat.confirmOrderAction(action.actionId, approved)
    await chat.confirmOrderAction(action.actionId, approved)
    await chat.cancelOrderAction(action.actionId)
    expect(api.confirm).toHaveBeenCalledTimes(1)
    expect(api.cancel).not.toHaveBeenCalled()
    expect(api.recover).not.toHaveBeenCalled()
    api.recover.mockResolvedValue(completed())
    await chat.recoverOrderAction(action.actionId)
    expect(action).toMatchObject({ status: 'CONFIRMED', ...delivery, orderId: 42, amount: 80 })
    expect(action.receiverAddress).not.toBe(approved.receiverAddress)
  })

  it('does not resend a native decision after a transport timeout without a receipt', async () => {
    api.confirm.mockRejectedValue(new Error('timeout without receipt'))
    const { chat, action } = setup({ workflow: workflow() })
    await chat.confirmOrderAction(action.actionId, approved)
    await chat.confirmOrderAction(action.actionId, approved)
    expect(api.confirm).toHaveBeenCalledTimes(1)
    expect(action.status).toBe('RECOVERY_REQUIRED')
    expect(api.recover).not.toHaveBeenCalled()
  })

  it('keeps EXECUTING recoverable even after the original approval expiry', async () => {
    api.recover.mockResolvedValue({ workflow: workflow('EXECUTING') })
    const { chat, action } = setup({ workflow: workflow('EXECUTING'), status: 'EXECUTING', expiresAt: '2020-01-01T00:00:00Z' })
    chat.expireOrderActions()
    await chat.recoverOrderAction(action.actionId)
    expect(api.recover).toHaveBeenCalledTimes(1)
    expect(action.status).toBe('EXECUTING')
    await chat.confirmOrderAction(action.actionId)
    expect(api.confirm).not.toHaveBeenCalled()
  })

  it('coalesces manual recovery and blocks concurrent approval/rejection', async () => {
    let resolve!: (value: unknown) => void
    api.recover.mockReturnValue(new Promise(r => { resolve = r }))
    const { chat, action } = setup({ workflow: workflow() })
    const first = chat.recoverOrderAction(action.actionId)
    const second = chat.recoverOrderAction(action.actionId)
    await chat.confirmOrderAction(action.actionId, approved)
    await chat.cancelOrderAction(action.actionId)
    expect(action.status).toBe('RECOVERING')
    expect(api.recover).toHaveBeenCalledTimes(1)
    expect(api.confirm).not.toHaveBeenCalled()
    expect(api.cancel).not.toHaveBeenCalled()
    resolve({ workflow: workflow() })
    await Promise.all([first, second])
    expect(action.status).toBe('PENDING')
  })

  it.each(['FAILED', 'EXPIRED', 'CANCELLED'])('keeps %s terminal with no approval retry', async status => {
    api.recover.mockResolvedValue({ ...(status === 'CANCELLED' ? { type: 'ORDER_CREATE', actionStatus: 'CANCELLED' } : {}), workflow: workflow(status, false) })
    const { chat, action } = setup({ workflow: workflow('EXECUTING'), status: 'EXECUTING' })
    await chat.recoverOrderAction(action.actionId)
    expect(action.status).toBe(status)
    await chat.confirmOrderAction(action.actionId, approved)
    expect(api.confirm).not.toHaveBeenCalled()
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it.each([
    () => ({ ...completed(), workflow: workflow('COMPLETED', true, { code: 'RETRYABLE' }) }),
    () => ({ ...completed(), workflow: { ...workflow('COMPLETED'), actionId: 'other-action' } }),
    () => ({ workflow: workflow('COMPLETED', true) }),
    () => ({ ...completed(), receiverAddress: undefined }),
    () => ({ ...completed(), actionStatus: 'PENDING' }),
    () => ({ ...completed(), workflow: { ...workflow('COMPLETED'), nativeInterrupt: false } }),
    () => ({ ...completed(), workflow: undefined }),
  ])('rejects inconsistent or erroneous recovery receipts', async receipt => {
    api.recover.mockResolvedValue(receipt())
    const { chat, action } = setup({ workflow: workflow('EXECUTING'), status: 'EXECUTING' })
    await chat.recoverOrderAction(action.actionId)
    expect(action.status).not.toBe('CONFIRMED')
    expect(action.orderId).toBeUndefined()
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('does not mark a nonterminal native cancellation as cancelled', async () => {
    api.cancel.mockResolvedValue({ workflow: workflow('EXECUTING') })
    const { chat, action } = setup({ workflow: workflow() })
    await chat.cancelOrderAction(action.actionId)
    expect(action.status).toBe('EXECUTING')
    expect(api.recover).not.toHaveBeenCalled()
  })

  it('never falls back to legacy approval when recovery is unavailable or disabled', async () => {
    api.recover.mockRejectedValue({ code: 5002, message: '原生工作流未启用' })
    const { chat, action } = setup({ workflow: workflow('EXECUTING'), status: 'EXECUTING' })
    await chat.recoverOrderAction(action.actionId)
    await chat.confirmOrderAction(action.actionId, approved)
    expect(action.status).not.toBe('CONFIRMED')
    expect(api.confirm).not.toHaveBeenCalled()
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('preserves disabled/legacy confirmation and cancellation without native receipts', async () => {
    api.confirm.mockResolvedValue({ orderId: 5, orderNo: 'LEGACY-5', status: 'PENDING_PAYMENT', totalAmount: 10 })
    const { chat, action } = setup()
    await chat.confirmOrderAction(action.actionId, approved)
    expect(action).toMatchObject({ status: 'CONFIRMED', ...approved, orderId: 5 })
    const legacy = setup({ actionId: 'legacy-cancel' })
    api.cancel.mockResolvedValue(undefined)
    await legacy.chat.cancelOrderAction(legacy.action.actionId)
    expect(legacy.action.status).toBe('CANCELLED')
    await legacy.chat.recoverOrderAction(legacy.action.actionId)
    expect(api.recover).not.toHaveBeenCalled()
  })
})

it('uses server delivery even when the local confirmation form differs', async () => {
  api.confirm.mockResolvedValue(completed())
  const { chat, action } = setup()
  await chat.confirmOrderAction(action.actionId, approved)
  expect(action).toMatchObject({ status: 'CONFIRMED', ...delivery })
})

it('does not overwrite canonical recovered delivery with a replayed preparation event', async () => {
  api.recover.mockResolvedValue(completed())
  const { chat, action } = setup({ workflow: workflow('EXECUTING'), status: 'EXECUTING' })
  await chat.recoverOrderAction(action.actionId)
  chat.upsertOrderAction(chat.messages[0], { ...action, ...approved, workflow: workflow() })
  expect(action).toMatchObject({ status: 'CONFIRMED', ...delivery, workflow: workflow('COMPLETED', false) })
})

it('ignores recovery that completes after the account session was reset', async () => {
  let resolve!: (value: unknown) => void
  api.recover.mockReturnValue(new Promise(r => { resolve = r }))
  const { chat, action } = setup({ workflow: workflow('EXECUTING'), status: 'EXECUTING' })
  const request = chat.recoverOrderAction(action.actionId)
  chat.resetSession()
  resolve(completed())
  await request
  expect(chat.messages).toEqual([])
  expect(ElMessage.success).not.toHaveBeenCalled()
  expect(action.status).not.toBe('CONFIRMED')
})

it('never treats native status-only history hydration as a canonical completion receipt', async () => {
  api.detail.mockResolvedValue({ conversationId: 7, status: 'ACTIVE' })
  api.messages.mockResolvedValue({ records: [{ role: 'AI', content: '', toolCalls: JSON.stringify([{
    type: 'ORDER_CREATE', actionId: 'native-1', status: 'EXECUTING', workflow: workflow('EXECUTING'),
    expiresAt: '2099-01-01T00:00:00Z', ...approved,
  }]) }] })
  api.status.mockResolvedValue({ status: 'CONFIRMED', orderId: 42 })
  const chat = useChatStore()
  await chat.openConversation(7)
  expect(chat.messages[0].actions![0].status).toBe('RECOVERY_REQUIRED')
  expect(api.recover).not.toHaveBeenCalled()
  expect(api.confirm).not.toHaveBeenCalled()
})

it.each([
  ['EXPIRED', { code: 2011, message: 'action is no longer awaiting approval' }],
  ['CANCELLED', { code: 409, message: 'action is no longer awaiting approval' }],
])('preserves canonical %s from waiting reconciliation even with diagnostic error and no result', async (status, error) => {
  api.recover.mockResolvedValue({ workflow: workflow(status, false, error) })
  const { chat, action } = setup({ workflow: workflow(), recoveryRequired: true, status: 'RECOVERY_REQUIRED' })
  await chat.recoverOrderAction(action.actionId)
  expect(action.status).toBe(status)
  expect(action.recoveryRequired).toBe(false)
  expect(action.orderId).toBeUndefined()
  await chat.confirmOrderAction(action.actionId, approved)
  await chat.cancelOrderAction(action.actionId)
  await chat.recoverOrderAction(action.actionId)
  expect(api.recover).toHaveBeenCalledTimes(1)
  expect(api.confirm).not.toHaveBeenCalled()
  expect(api.cancel).not.toHaveBeenCalled()
  expect(ElMessage.success).not.toHaveBeenCalled()
})

it('honors an EXPIRED confirm receipt carrying error 2011 instead of painting a retryable failure', async () => {
  api.confirm.mockResolvedValue({ workflow: workflow('EXPIRED', false, { code: 2011, message: 'expired' }) })
  const { chat, action } = setup()
  await chat.confirmOrderAction(action.actionId, approved)
  expect(action.status).toBe('EXPIRED')
  await chat.confirmOrderAction(action.actionId, approved)
  expect(api.confirm).toHaveBeenCalledTimes(1)
  expect(ElMessage.success).not.toHaveBeenCalled()
})

it('accepts a backwards-compatible old cleared-error empty map, not the normal success contract', async () => {
  api.recover.mockResolvedValue({ ...completed(), workflow: workflow('COMPLETED', false, {}) })
  const { chat, action } = setup({ workflow: workflow('EXECUTING'), status: 'EXECUTING' })
  await chat.recoverOrderAction(action.actionId)
  expect(action).toMatchObject({ status: 'CONFIRMED', ...delivery, orderId: 42 })
})

it('accepts explicit rejection result as CANCELLED, not a fabricated execution completion', async () => {
  api.cancel.mockResolvedValue({ type: 'ORDER_CREATE', actionStatus: 'CANCELLED', workflow: workflow('CANCELLED', false) })
  const { chat, action } = setup({ workflow: workflow() })
  await chat.cancelOrderAction(action.actionId)
  expect(action.status).toBe('CANCELLED')
  expect(action.orderId).toBeUndefined()
  expect(ElMessage.success).not.toHaveBeenCalled()
})

it('preserves disabled legacy manual retry after a transport error, without blind success or recovery', async () => {
  api.confirm.mockRejectedValue(new Error('legacy transport timeout'))
  const { chat, action } = setup() // Disabled preparation has the exact legacy shape, no workflow.
  await chat.confirmOrderAction(action.actionId, approved)
  expect(action.status).toBe('FAILED')
  expect(action.orderId).toBeUndefined()
  expect(ElMessage.success).not.toHaveBeenCalled()
  await chat.recoverOrderAction(action.actionId)
  expect(api.recover).not.toHaveBeenCalled()
  expect(api.confirm).toHaveBeenCalledTimes(1) // No automatic approval retry.
  api.confirm.mockResolvedValue({ orderId: 5, orderNo: 'LEGACY-5', status: 'PENDING_PAYMENT', totalAmount: 10 })
  await chat.confirmOrderAction(action.actionId, approved) // A new explicit legacy click.
  expect(api.confirm).toHaveBeenCalledTimes(2)
  expect(action).toMatchObject({ status: 'CONFIRMED', orderId: 5 })
})

it('requires recovery for 5002 even if workflow provenance was absent', async () => {
  api.confirm.mockRejectedValue({ code: 5002, message: 'Native gateway unavailable' })
  const { chat, action } = setup()
  await chat.confirmOrderAction(action.actionId, approved)
  await chat.confirmOrderAction(action.actionId, approved)
  await chat.cancelOrderAction(action.actionId)
  expect(action.status).toBe('RECOVERY_REQUIRED')
  expect(api.confirm).toHaveBeenCalledTimes(1)
  expect(api.cancel).not.toHaveBeenCalled()
  expect(api.recover).not.toHaveBeenCalled()
})

it.each(['ORDER_CREATE', 'ORDER_CANCEL', 'AFTER_SALE_APPLY'] as const)(
  'retains initial native preparation workflow provenance for %s and never retries its timed-out decision', async type => {
    api.confirm.mockRejectedValue(new Error('native transport timeout'))
    const { chat } = setup()
    chat.messages[0].actions = []
    const action = chat.upsertOrderAction(chat.messages[0], {
      type, actionId: 'native-1', expiresAt: '2099-01-01T00:00:00Z', workflow: workflow(),
    })
    expect(action.workflow).toEqual(workflow())
    await chat.confirmOrderAction(action.actionId, approved)
    await chat.confirmOrderAction(action.actionId, approved)
    expect(action.status).toBe('RECOVERY_REQUIRED')
    expect(api.confirm).toHaveBeenCalledTimes(1)
    expect(api.recover).not.toHaveBeenCalled()
  })

it.each([
  ['ORDER_CANCEL', { type: 'ORDER_CANCEL', actionStatus: 'CONFIRMED', orderId: 30, orderNo: 'ORDER-30', status: 'CANCELLED' }],
  ['AFTER_SALE_APPLY', { type: 'AFTER_SALE_APPLY', actionStatus: 'CONFIRMED', orderId: 30, orderNo: 'ORDER-30',
    status: 'DELIVERED', afterSaleId: 77, afterSaleNo: 'AS-77' }],
] as const)('accepts canonical native %s completion without requiring create-only delivery', async (type, result) => {
  api.recover.mockResolvedValue({ ...result, workflow: workflow('COMPLETED', false) })
  const { chat, action } = setup({ type, workflow: workflow('EXECUTING'), status: 'EXECUTING' })
  await chat.recoverOrderAction(action.actionId)
  expect(action).toMatchObject({ status: 'CONFIRMED', orderId: 30, orderNo: 'ORDER-30' })
  if (type === 'AFTER_SALE_APPLY') expect(action).toMatchObject({ afterSaleId: 77, afterSaleNo: 'AS-77' })
  else expect(action.orderStatus).toBe('CANCELLED')
  expect(api.confirm).not.toHaveBeenCalled()
  expect(api.cancel).not.toHaveBeenCalled()
})

async function reopenHistory(statusReceipt: Record<string, unknown>) {
  api.detail.mockResolvedValue({ conversationId: 7, status: 'ACTIVE' })
  api.messages.mockResolvedValue({ records: [{ role: 'AI', content: '', toolCalls: JSON.stringify([{
    type: 'ORDER_CREATE', actionId: 'native-1', expiresAt: '2099-01-01T00:00:00Z',
    receiverName: '原始收货人A', receiverPhone: '13800138000', receiverAddress: '原始地址A',
  }]) }] })
  api.status.mockResolvedValue(statusReceipt)
  const chat = useChatStore()
  await chat.openConversation(7)
  return { chat, action: chat.messages[0].actions![0] }
}

it('requires canonical native recovery when reopened domain status is confirmed, replacing address A with committed B', async () => {
  const { chat, action } = await reopenHistory({ status: 'CONFIRMED', nativeManaged: true, orderId: 42, orderNo: 'ORDER-42' })
  expect(action.status).toBe('RECOVERY_REQUIRED')
  expect(action.nativeManaged).toBe(true)
  expect(api.recover).not.toHaveBeenCalled() // Reading history never resumes a graph.
  await chat.confirmOrderAction(action.actionId, approved)
  expect(api.confirm).not.toHaveBeenCalled()
  api.recover.mockResolvedValue(completed())
  await chat.recoverOrderAction(action.actionId)
  expect(api.recover).toHaveBeenCalledExactlyOnceWith(action.actionId)
  expect(action).toMatchObject({ status: 'CONFIRMED', ...delivery })
  expect(action.receiverAddress).not.toBe('原始地址A')
})

it.each(['PENDING', 'CONFIRMED', 'FAILED'])('never interprets a missing historical native marker as legacy %s', async status => {
  const { chat, action } = await reopenHistory({ status, orderId: 42 })
  expect(action.status).toBe('RECOVERY_REQUIRED')
  await chat.confirmOrderAction(action.actionId, approved)
  await chat.cancelOrderAction(action.actionId)
  expect(api.confirm).not.toHaveBeenCalled()
  expect(api.cancel).not.toHaveBeenCalled()
  expect(api.recover).not.toHaveBeenCalled()
})

it.each(['PENDING', 'CONFIRMED', 'CANCELLED', 'EXPIRED'])('retains explicitly legacy historical domain status %s', async status => {
  const { action } = await reopenHistory({ status, nativeManaged: false, orderId: 42 })
  expect(action.status).toBe(status)
  expect(action.nativeManaged).toBe(false)
  expect(action.recoveryRequired).toBe(false)
  expect(api.recover).not.toHaveBeenCalled()
})

it('does not allow late legacy-looking status hydration to overwrite newer native recovery provenance', async () => {
  let resolve!: (value: unknown) => void
  const snapshot = new Promise(r => { resolve = r })
  api.detail.mockResolvedValue({ conversationId: 7, status: 'ACTIVE' })
  api.messages.mockResolvedValue({ records: [{ role: 'AI', content: '', toolCalls: JSON.stringify([{
    type: 'ORDER_CREATE', actionId: 'native-1', expiresAt: '2099-01-01T00:00:00Z',
  }]) }] })
  api.status.mockReturnValue(snapshot)
  const chat = useChatStore()
  await chat.openConversation(7)
  const action = chat.messages[0].actions![0]
  api.recover.mockRejectedValue({ code: 5002, message: 'Native gateway unavailable' })
  await chat.recoverOrderAction(action.actionId)
  resolve({ status: 'PENDING', nativeManaged: false })
  await Promise.resolve(); await Promise.resolve()
  expect(action.status).toBe('RECOVERY_REQUIRED')
  await chat.confirmOrderAction(action.actionId, approved)
  expect(api.confirm).not.toHaveBeenCalled()
})

it('accepts the exact successful native receipt with an explicit null Python error', async () => {
  api.recover.mockResolvedValue({ ...completed(), workflow: workflow('COMPLETED', false, null) })
  const { chat, action } = setup({ workflow: workflow('EXECUTING'), status: 'EXECUTING' })
  await chat.recoverOrderAction(action.actionId)
  expect(action).toMatchObject({ status: 'CONFIRMED', ...delivery, orderId: 42 })
  expect(api.confirm).not.toHaveBeenCalled()
})

it('requires recovery for a native-managed PENDING domain snapshot without a workflow receipt', async () => {
  const { chat, action } = setup({ nativeManaged: true, status: 'PENDING' })
  await expect(chat.confirmOrderAction(action.actionId, approved)).resolves.toBeUndefined()
  await expect(chat.cancelOrderAction(action.actionId)).resolves.toBeUndefined()
  expect(api.confirm).not.toHaveBeenCalled()
  expect(api.cancel).not.toHaveBeenCalled()
  api.recover.mockResolvedValue({ workflow: workflow() })
  await chat.recoverOrderAction(action.actionId)
  expect(action).toMatchObject({ status: 'PENDING', nativeManaged: true, workflow: workflow() })
})
