import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useChatStore } from './chat'
import type { ChatMessage, OrderAction } from '@/types/api'

const api = vi.hoisted(() => ({ confirmOrderAction: vi.fn() }))

vi.mock('@/api', () => ({
  apiCloseConversation: vi.fn(),
  apiConversationDetail: vi.fn(),
  apiConversationStatus: vi.fn(),
  apiConversations: vi.fn(),
  apiCreateConversation: vi.fn(),
  apiHumanMessage: vi.fn(),
  apiMessages: vi.fn(),
  apiMessagesAfter: vi.fn(),
  apiSatisfaction: vi.fn(),
  apiConfirmOrderAction: api.confirmOrderAction,
}))

vi.mock('element-plus', () => ({
  ElMessage: { error: vi.fn(), success: vi.fn() },
}))

function pendingAction(overrides: Partial<OrderAction> = {}): OrderAction {
  return {
    type: 'ORDER_CREATE',
    actionId: 'act_123',
    productName: '星云手机',
    quantity: 2,
    unitPrice: 2999,
    amount: 5998,
    receiverName: '张三',
    receiverPhone: '13800138000',
    receiverAddress: '浙江省杭州市西湖区文三路90号',
    expiresAt: '2099-08-23T09:10:00Z',
    status: 'PENDING',
    ...overrides,
  }
}

function withAction(action = pendingAction()) {
  const chat = useChatStore()
  const message: ChatMessage = { role: 'AI', content: '请确认', actions: [action] }
  chat.messages = [message]
  return { chat, action }
}

describe('chat order action state', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    api.confirmOrderAction.mockReset()
  })

  it('updates a repeated action event instead of rendering a duplicate card', () => {
    const { chat } = withAction()
    const message = chat.messages[0]

    chat.upsertOrderAction(message, pendingAction({ amount: 5798 }))

    expect(message.actions).toHaveLength(1)
    expect(message.actions?.[0].amount).toBe(5798)
    expect(message.actions?.[0].status).toBe('PENDING')
  })

  it('cancels a pending action locally and never calls the confirm endpoint', async () => {
    const { chat, action } = withAction()

    chat.cancelOrderAction(action.actionId)
    const result = await chat.confirmOrderAction(action.actionId)

    expect(action.status).toBe('CANCELLED')
    expect(result).toBeUndefined()
    expect(api.confirmOrderAction).not.toHaveBeenCalled()
  })

  it('marks an elapsed pending action expired and refuses confirmation', async () => {
    const { chat, action } = withAction(pendingAction({ expiresAt: '2026-08-23T08:00:00Z' }))

    chat.expireOrderActions(Date.parse('2026-08-23T08:00:01Z'))
    await chat.confirmOrderAction(action.actionId)

    expect(action.status).toBe('EXPIRED')
    expect(api.confirmOrderAction).not.toHaveBeenCalled()
  })

  it('keeps a failed confirmation retryable without leaking a rejected click handler', async () => {
    api.confirmOrderAction.mockRejectedValue({ code: 5001, message: '暂时失败' })
    const { chat, action } = withAction()

    await expect(chat.confirmOrderAction(action.actionId)).resolves.toBeUndefined()

    expect(action.status).toBe('FAILED')
  })

  it('coalesces rapid confirmation clicks into one order request', async () => {
    let resolveOrder!: (order: { orderId: number; orderNo: string; status: string; totalAmount: number }) => void
    api.confirmOrderAction.mockReturnValue(new Promise((resolve) => { resolveOrder = resolve }))
    const { chat, action } = withAction()

    const first = chat.confirmOrderAction(action.actionId)
    const second = chat.confirmOrderAction(action.actionId)

    expect(action.status).toBe('CONFIRMING')
    expect(api.confirmOrderAction).toHaveBeenCalledTimes(1)
    resolveOrder({ orderId: 88, orderNo: 'ORD-88', status: 'PENDING_PAYMENT', totalAmount: 5998 })

    await expect(first).resolves.toMatchObject({ orderId: 88, orderNo: 'ORD-88' })
    await expect(second).resolves.toBeUndefined()
    expect(action).toMatchObject({ status: 'CONFIRMED', orderId: 88, orderNo: 'ORD-88', amount: 5998 })
  })
})
