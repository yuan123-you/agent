import { afterEach, describe, expect, it, vi } from 'vitest'
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


describe('streamChat transport lifecycle', () => {
  afterEach(() => vi.unstubAllGlobals())
  const handlers = () => ({ onToken: vi.fn(), onToolCall: vi.fn(), onToolResult: vi.fn(), onAction: vi.fn(), onError: vi.fn(), onDone: vi.fn() })

  it('parses a final frame even when EOF has no trailing newline', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(responseFrom('event: done\ndata: {"content":"完成"}')))
    const callbacks = handlers()
    await streamChat({ conversationId: 1, content: '你好' }, callbacks).promise
    expect(callbacks.onDone).toHaveBeenCalledWith({ content: '完成' })
    expect(callbacks.onError).not.toHaveBeenCalled()
  })

  it('reports truncated streams instead of silently accepting an unfinished answer', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(responseFrom('event: token\ndata: {"content":"部分内容"}\n\n')))
    const callbacks = handlers()
    await streamChat({ conversationId: 1, content: '你好' }, callbacks).promise
    expect(callbacks.onToken).toHaveBeenCalledWith('部分内容')
    expect(callbacks.onError).toHaveBeenCalledOnce()
    expect(callbacks.onDone).not.toHaveBeenCalled()
  })

  it('finishes and cancels the reader after done without waiting for the server to close', async () => {
    const cancel = vi.fn()
    const body = new ReadableStream({ start(controller) {
      controller.enqueue(new TextEncoder().encode('event: done\ndata: {"content":"完成"}\n\nevent: token\ndata: {"content":"不应追加"}\n\n'))
    }, cancel })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, { headers: { 'content-type': 'text/event-stream' } })))
    const callbacks = handlers()
    await streamChat({ conversationId: 1, content: '你好' }, callbacks).promise
    expect(callbacks.onDone).toHaveBeenCalledOnce()
    expect(callbacks.onToken).not.toHaveBeenCalled()
    expect(cancel).toHaveBeenCalledOnce()
    expect(body.locked).toBe(false)
  })

  it('handles CRLF, heartbeat comments and a UTF-8 character split across chunks', async () => {
    const data = new TextEncoder().encode(': ping\r\nevent: token\r\ndata: {"content":"你"}\r\n\r\nevent: done\r\ndata: {"content":"你"}\r\n\r\n')
    const body = new ReadableStream({ start(controller) { for (const byte of data) controller.enqueue(Uint8Array.of(byte)); controller.close() } })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, { headers: { 'content-type': 'text/event-stream' } })))
    const callbacks = handlers()
    await streamChat({ conversationId: 1, content: '你好' }, callbacks).promise
    expect(callbacks.onToken).toHaveBeenCalledExactlyOnceWith('你')
    expect(callbacks.onDone).toHaveBeenCalledOnce()
  })
})

it('preserves server failure identity and distinguishes interrupted transport from model failure', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(responseFrom('event: error\ndata: {"code":5002,"message":"timeout","messageId":42}\n\n')))
  const callbacks = { onToken: vi.fn(), onToolCall: vi.fn(), onToolResult: vi.fn(), onAction: vi.fn(), onError: vi.fn(), onDone: vi.fn() }
  await streamChat({ conversationId: 1, content: 'hello', requestId: 'run-1', resumeOnly: true }, callbacks).promise
  expect(callbacks.onError).toHaveBeenCalledWith(expect.objectContaining({ code: 5002, messageId: 42 }))
  vi.unstubAllGlobals()
})

it('bounds a stalled connection and clears its idle timer after failure', async () => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', vi.fn((_url, init) => new Promise((_resolve, reject) => {
    init.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
  })))
  const h = { onToken: vi.fn(), onToolCall: vi.fn(), onToolResult: vi.fn(), onAction: vi.fn(), onError: vi.fn(), onDone: vi.fn() }
  const stream = streamChat({ conversationId: 1, content: 'hello' }, h)
  const rejected = expect(stream.promise).rejects.toMatchObject({ name: 'AbortError' })
  await vi.advanceTimersByTimeAsync(45000)
  await rejected
  expect(vi.getTimerCount()).toBe(0)
  vi.useRealTimers(); vi.unstubAllGlobals()
})
