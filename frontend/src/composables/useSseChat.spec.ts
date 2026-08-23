import { describe, expect, it, vi } from 'vitest'
import { streamChat } from './useSseChat'

function responseFrom(text: string): Response {
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(text))
      controller.close()
    },
  })
  return new Response(stream, { status: 200, headers: { 'content-type': 'text/event-stream' } })
}

describe('streamChat action events', () => {
  it('dispatches a structured order action independently from text and done', async () => {
    const action = {
      type: 'ORDER_CREATE' as const,
      actionId: 'act_123', productName: '云感枕', quantity: 2,
      unitPrice: 49.9, amount: 99.8, receiverName: '张三',
      receiverPhone: '13800138000', receiverAddress: '浙江省杭州市西湖区文三路90号',
      expiresAt: '2026-08-23T09:10:00Z',
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(responseFrom(
      `event: token\ndata: {"content":"请确认"}\n\nevent: action\ndata: ${JSON.stringify(action)}\n\nevent: done\ndata: {"content":"请确认"}\n\n`,
    )))
    const onAction = vi.fn()

    const stream = streamChat({ conversationId: 9, content: '买两个' }, {
      onToken: vi.fn(), onToolCall: vi.fn(), onToolResult: vi.fn(),
      onAction, onError: vi.fn(), onDone: vi.fn(),
    })
    await stream.promise

    expect(onAction).toHaveBeenCalledOnce()
    expect(onAction).toHaveBeenCalledWith(action)
    vi.unstubAllGlobals()
  })
})
