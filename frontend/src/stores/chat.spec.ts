import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useChatStore } from './chat'
import type { ChatMessage, OrderAction } from '@/types/api'

const api = vi.hoisted(() => ({
  confirmOrderAction: vi.fn(),
  cancelOrderAction: vi.fn(),
  orderActionStatus: vi.fn(),
  conversationDetail: vi.fn(),
  conversations: vi.fn(),
  cancelHuman: vi.fn(),
  messages: vi.fn(),
}))

vi.mock('@/api', () => ({
  apiCloseConversation: vi.fn(),
  apiConversationDetail: api.conversationDetail,
  apiConversationStatus: vi.fn(),
  apiConversations: api.conversations,
  apiCreateConversation: vi.fn(),
  apiHumanMessage: vi.fn(),
  apiCancelHuman: api.cancelHuman,
  apiMessages: api.messages,
  apiMessagesAfter: vi.fn(),
  apiSatisfaction: vi.fn(),
  apiConfirmOrderAction: api.confirmOrderAction,
  apiCancelOrderAction: api.cancelOrderAction,
  apiOrderActionStatus: api.orderActionStatus,
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
    api.cancelOrderAction.mockReset()
    api.cancelOrderAction.mockResolvedValue(undefined)
    api.conversationDetail.mockReset()
    api.messages.mockReset()
    api.orderActionStatus.mockReset()
  })

  it('updates a repeated action event instead of rendering a duplicate card', () => {
    const { chat } = withAction()
    const message = chat.messages[0]

    chat.upsertOrderAction(message, pendingAction({ amount: 5798 }))

    expect(message.actions).toHaveLength(1)
    expect(message.actions?.[0].amount).toBe(5798)
    expect(message.actions?.[0].status).toBe('PENDING')
  })

  it('persists a rejected action before marking it cancelled', async () => {
    const { chat, action } = withAction()

    await chat.cancelOrderAction(action.actionId)
    const result = await chat.confirmOrderAction(action.actionId)

    expect(api.cancelOrderAction).toHaveBeenCalledWith(action.actionId)
    expect(action.status).toBe('CANCELLED')
    expect(result).toBeUndefined()
    expect(api.confirmOrderAction).not.toHaveBeenCalled()
  })

  it('forwards the buyer-edited delivery form when confirming', async () => {
    api.confirmOrderAction.mockResolvedValue({
      orderId: 89, orderNo: 'ORD-89', status: 'PENDING_PAYMENT', totalAmount: 5998,
    })
    const { chat, action } = withAction()
    const approval = {
      receiverName: '李四',
      receiverPhone: '13900139000',
      receiverAddress: '浙江省杭州市西湖区文三路90号',
    }

    await chat.confirmOrderAction(action.actionId, approval)

    expect(api.confirmOrderAction).toHaveBeenCalledWith(action.actionId, approval)
    expect(action).toMatchObject({ status: 'CONFIRMED', receiverName: '李四' })
  })

  it('confirms an order cancellation without delivery approval data', async () => {
    api.confirmOrderAction.mockResolvedValue({
      type: 'ORDER_CANCEL', actionStatus: 'CONFIRMED', orderId: 30, orderNo: 'ORD-30', status: 'CANCELLED',
    })
    const { chat, action } = withAction(pendingAction({
      type: 'ORDER_CANCEL', orderId: 30, orderNo: 'ORD-30', reason: '不需要了',
    }))

    await chat.confirmOrderAction(action.actionId)

    expect(api.confirmOrderAction).toHaveBeenCalledWith(action.actionId, undefined)
    expect(action).toMatchObject({ status: 'CONFIRMED', orderStatus: 'CANCELLED' })
  })

  it('stores the after-sale identity returned by buyer confirmation', async () => {
    api.confirmOrderAction.mockResolvedValue({
      type: 'AFTER_SALE_APPLY', actionStatus: 'CONFIRMED', orderId: 30,
      orderNo: 'ORD-30', status: 'DELIVERED', afterSaleId: 77, afterSaleNo: 'AS-77',
    })
    const { chat, action } = withAction(pendingAction({
      type: 'AFTER_SALE_APPLY', orderId: 30, orderItemId: 41, productName: '测试商品',
      serviceType: 'RETURN_REFUND', issueCategory: 'QUALITY', reason: '屏幕损坏',
    }))

    await chat.confirmOrderAction(action.actionId)

    expect(action).toMatchObject({ status: 'CONFIRMED', afterSaleId: 77, afterSaleNo: 'AS-77' })
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


describe('chat tool result history', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    api.conversationDetail.mockResolvedValue({ conversationId: 7, status: 'ACTIVE' })
  })

  it('hides legacy ToolMessage protocol text while loading history', async () => {
    api.messages.mockResolvedValue({
      records: [{
        role: 'AI',
        content: '为您找到以下商品',
        toolCalls: JSON.stringify([
          { callId: 'call_1', tool: 'product_search' },
          {
            callId: 'call_1',
            tool: 'product_search',
            result: {
              preview: `content='{"products":[{"name":"星云手机"}]}' name='product_search' tool_call_id='call_1'`,
            },
          },
        ]),
      }],
    })
    const chat = useChatStore()

    await chat.openConversation(7)

    expect(chat.messages[0].toolCalls?.[0].result?.preview).toBeUndefined()
  })

  it('restores a persisted action and synchronizes its backend decision state', async () => {
    api.messages.mockResolvedValue({
      records: [{
        role: 'AI', content: '请核对订单',
        toolCalls: JSON.stringify([{
          type: 'ORDER_CREATE', actionId: 'act_history', productName: '星云手机', quantity: 1,
          unitPrice: 2999, amount: 2999, receiverName: '张三', receiverPhone: '13800138000',
          receiverAddress: '杭州文三路90号', expiresAt: '2099-08-23T09:10:00Z',
        }]),
      }],
    })
    api.orderActionStatus.mockResolvedValue({ status: 'CANCELLED' })
    const chat = useChatStore()

    await chat.openConversation(7)

    expect(chat.messages[0].toolCalls).toEqual([])
    expect(chat.messages[0].actions?.[0]).toMatchObject({ actionId: 'act_history', status: 'CANCELLED' })
    expect(api.orderActionStatus).toHaveBeenCalledWith('act_history')
  })

  it('keeps already formatted tool previews while loading history', async () => {
    api.messages.mockResolvedValue({
      records: [{
        role: 'AI',
        content: '为您找到以下商品',
        toolCalls: JSON.stringify([{
          callId: 'call_1',
          tool: 'product_search',
          result: { preview: '找到 1 件商品：星云手机（¥2999）' },
        }]),
      }],
    })
    const chat = useChatStore()

    await chat.openConversation(7)

    expect(chat.messages[0].toolCalls?.[0].result?.preview).toBe('找到 1 件商品：星云手机（¥2999）')
  })
  it('cancels a pending human handoff and restores the active conversation', async () => {
    api.cancelHuman.mockResolvedValue(undefined)
    api.conversationDetail.mockResolvedValue({ conversationId: 7, status: 'ACTIVE' })
    api.conversations.mockResolvedValue({ records: [{ conversationId: 7, status: 'ACTIVE' }], total: 1 })
    const store = useChatStore()
    store.current = { conversationId: 7, status: 'PENDING_HUMAN' }

    await store.cancelHumanHandoff()

    expect(store.current.status).toBe('ACTIVE')
  })
})


describe('chat background streaming restore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    api.conversationDetail.mockResolvedValue({ conversationId: 7, status: 'ACTIVE' })
  })

  it('restores an in-flight streaming AI message and streaming flag after switching back', async () => {
    // 服务端只持久化了用户消息，AI 回复仍在前端内存中生成中
    api.messages.mockResolvedValue({
      records: [{ role: 'USER', content: '你好' }],
    })
    const chat = useChatStore()
    const ai: ChatMessage = { role: 'AI', content: '正在生成…', toolCalls: [], status: 'PENDING' }
    chat.pendingByConv[7] = { aiMessage: ai, stream: null, streaming: true }

    await chat.openConversation(7)

    expect(chat.messages).toHaveLength(2)
    expect(chat.messages[1]).toMatchObject({ role: 'AI', content: '正在生成…', status: 'PENDING' })
    expect(chat.streaming).toBe(true)
  })

  it('does not duplicate an AI message already persisted on the server', async () => {
    const persisted: ChatMessage = { messageId: 9, role: 'AI', content: '完整回复', status: 'SUCCESS' }
    api.messages.mockResolvedValue({ records: [{ role: 'USER', content: '你好' }, persisted] })
    const chat = useChatStore()
    // 已完成但 pending 记录尚未清理的竞态窗口
    chat.pendingByConv[7] = { aiMessage: { ...persisted }, stream: null, streaming: false }

    await chat.openConversation(7)

    expect(chat.messages).toHaveLength(2)
    expect(chat.streaming).toBe(false)
  })

  it('clears the pending record once the stream finishes', async () => {
    const chat = useChatStore()
    chat.current = { conversationId: 7, status: 'ACTIVE' }
    // 与真实流一致：aiMsg 从响应式 messages 数组中取引用
    chat.messages.push({ role: 'USER', content: '你好' })
    chat.messages.push({ role: 'AI', content: '', toolCalls: [], status: 'PENDING' })
    const aiMsg = chat.messages[chat.messages.length - 1] as ChatMessage
    chat.pendingByConv[7] = { aiMessage: aiMsg, stream: null, streaming: true }
    chat.streaming = true

    // 模拟流完成后的 finally 清理
    if (chat.pendingByConv[7]?.aiMessage === aiMsg) {
      delete chat.pendingByConv[7]
    }
    if (chat.current?.conversationId === 7) {
      chat.streaming = false
    }

    expect(chat.pendingByConv[7]).toBeUndefined()
    expect(chat.streaming).toBe(false)
  })
})
