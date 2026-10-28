import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useChatStore } from './chat'
import type { OrderAction } from '@/types/api'

const api = vi.hoisted(() => ({ detail: vi.fn(), list: vi.fn(), messages: vi.fn(), status: vi.fn(), create: vi.fn(), stream: vi.fn() }))
vi.mock('@/api', () => ({
  apiConversationDetail: api.detail, apiConversations: api.list, apiMessages: api.messages,
  apiOrderActionStatus: api.status, apiCreateConversation: api.create,
  apiCloseConversation: vi.fn(), apiConversationStatus: vi.fn(), apiHumanMessage: vi.fn(),
  apiCancelHuman: vi.fn(), apiMessagesAfter: vi.fn(), apiSatisfaction: vi.fn(),
  apiConfirmOrderAction: vi.fn(), apiCancelOrderAction: vi.fn(),
}))
vi.mock('@/composables/useSseChat', () => ({ streamChat: api.stream }))
vi.mock('element-plus', () => ({ ElMessage: { error: vi.fn(), success: vi.fn() } }))
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(yes => { resolve = yes })
  return { promise, resolve }
}
const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve() }
const conversation = (id: number) => ({ conversationId: id, status: 'ACTIVE' as const })
function action(): OrderAction {
  return { type: 'ORDER_CANCEL', actionId: 'act_1', orderId: 7, expiresAt: '2099-01-01T00:00:00Z', status: 'PENDING' }
}
beforeEach(() => {
  vi.resetAllMocks()
  setActivePinia(createPinia())
  api.list.mockResolvedValue({ records: [] })
  api.detail.mockImplementation(id => Promise.resolve(conversation(id)))
  api.messages.mockResolvedValue({ records: [] })
})
afterEach(() => vi.useRealTimers())

describe('conversation loading performance', () => {
  it('loads detail/history concurrently and commits them atomically', async () => {
    const chat = useChatStore()
    chat.current = conversation(7)
    chat.messages = [{ role: 'AI', content: '旧会话' }]
    const detail = deferred<any>(), history = deferred<any>()
    api.detail.mockReturnValue(detail.promise)
    api.messages.mockReturnValue(history.promise)
    const loading = chat.openConversation(8)
    expect(api.messages).toHaveBeenCalledWith(8, { page: 1, size: 100 })
    detail.resolve(conversation(8))
    await flush()
    expect(chat.current.conversationId).toBe(7)
    expect(chat.messages[0].content).toBe('旧会话')
    history.resolve({ records: [{ role: 'AI', content: '新会话' }] })
    await loading
    expect(chat.current.conversationId).toBe(8)
    expect(chat.messages[0].content).toBe('新会话')
  })

  it('keeps the latest selection when an old request finishes later', async () => {
    const chat = useChatStore(), old = deferred<any>()
    api.detail.mockImplementation(id => id === 7 ? old.promise : Promise.resolve(conversation(id)))
    api.messages.mockImplementation(id => Promise.resolve({ records: [{ role: 'AI', content: String(id) }] }))
    const first = chat.openConversation(7)
    await chat.openConversation(8)
    old.resolve(conversation(7))
    await first
    expect(chat.current?.conversationId).toBe(8)
    expect(chat.messages[0].content).toBe('8')
  })

  it('deduplicates simultaneous list and same-conversation loads', async () => {
    const chat = useChatStore(), list = deferred<any>(), detail = deferred<any>()
    api.list.mockReturnValue(list.promise)
    api.detail.mockReturnValue(detail.promise)
    const requests = [chat.loadConversations(), chat.loadConversations(), chat.openConversation(7), chat.openConversation(7)]
    expect(api.list).toHaveBeenCalledTimes(1)
    expect(api.detail).toHaveBeenCalledTimes(1)
    list.resolve({ records: [] }); detail.resolve(conversation(7))
    await Promise.all(requests)
    expect(chat.loadingConversations).toBe(false)
    expect(chat.loadingConversationId).toBeNull()
  })

  it('displays history without waiting for slow action-status hydration', async () => {
    const chat = useChatStore(), status = deferred<any>()
    api.messages.mockResolvedValue({ records: [{ role: 'AI', content: '历史', toolCalls: JSON.stringify([action()]) }] })
    api.status.mockReturnValue(status.promise)
    let completed = false
    const request = chat.openConversation(7).then(() => { completed = true })
    await flush()
    expect(completed).toBe(true)
    expect(chat.messages[0].content).toBe('历史')
    status.resolve({ status: 'CONFIRMED' })
    await request; await flush()
    expect(chat.messages[0].actions?.[0].status).toBe('CONFIRMED')
  })

  it('does not overwrite a new buyer decision with stale action hydration', async () => {
    const chat = useChatStore(), status = deferred<any>()
    api.messages.mockResolvedValue({ records: [{ role: 'AI', content: '历史', toolCalls: JSON.stringify([action()]) }] })
    api.status.mockReturnValue(status.promise)
    const request = chat.openConversation(7)
    await flush()
    chat.messages[0].actions![0].status = 'CONFIRMING'
    status.resolve({ status: 'PENDING' })
    await request; await flush()
    expect(chat.messages[0].actions![0].status).toBe('CONFIRMING')
  })

  it('refreshes cached conversation metadata without refetching or replacing history', async () => {
    const chat = useChatStore(), detail = deferred<any>()
    chat.current = conversation(7)
    chat.messages = [{ role: 'AI', content: '缓存的回答' }]
    api.detail.mockReturnValue(detail.promise)
    const refresh = chat.refreshCurrent()
    expect(chat.messages[0].content).toBe('缓存的回答')
    expect(api.messages).not.toHaveBeenCalled()
    detail.resolve({ ...conversation(7), status: 'CLOSED' })
    await refresh
    expect(chat.current.status).toBe('CLOSED')
    expect(chat.messages[0].content).toBe('缓存的回答')
  })

  it('retains the old view and clears loading on failure', async () => {
    const chat = useChatStore()
    chat.current = conversation(7)
    chat.messages = [{ role: 'AI', content: '保留内容' }]
    api.messages.mockRejectedValue(new Error('offline'))
    await expect(chat.openConversation(8)).rejects.toThrow('offline')
    expect(chat.current.conversationId).toBe(7)
    expect(chat.messages[0].content).toBe('保留内容')
    expect(chat.loadingConversationId).toBeNull()
  })

  it('opens a created conversation without waiting for a sidebar refresh', async () => {
    const chat = useChatStore(), list = deferred<any>()
    api.create.mockResolvedValue({ conversationId: 8 }); api.list.mockReturnValue(list.promise)
    let completed = false
    const request = chat.createConversation().then(() => { completed = true })
    await flush()
    expect(completed).toBe(true)
    expect(chat.current?.conversationId).toBe(8)
    list.resolve({ records: [] }); await request
  })
})

describe('stream rendering lifecycle', () => {
  function start() {
    vi.useFakeTimers()
    const chat = useChatStore()
    chat.current = conversation(7)
    const completion = deferred<void>()
    let handlers: any
    api.stream.mockImplementation((_body, callbacks) => {
      handlers = callbacks
      return { promise: completion.promise, stop: vi.fn(() => completion.resolve()) }
    })
    const sending = chat.sendMessage('你好')
    return { chat, completion, sending, handlers }
  }

  it('coalesces a token burst and flushes final content immediately', async () => {
    const { chat, completion, sending, handlers } = start()
    handlers.onToken('你'); handlers.onToken('好')
    expect(chat.messages[1].content).toBe('')
    await vi.advanceTimersByTimeAsync(32)
    expect(chat.messages[1].content).toBe('你好')
    handlers.onToken('！'); handlers.onDone({ content: '你好！', messageId: 12 })
    completion.resolve(); await sending
    expect(chat.messages[1]).toMatchObject({ content: '你好！', status: 'SUCCESS' })
    expect(vi.getTimerCount()).toBe(0)
  })

  it('preserves buffered partial output on error', async () => {
    const { chat, completion, sending, handlers } = start()
    handlers.onToken('已收到的部分'); handlers.onError({ code: 5001, message: '连接中断' })
    completion.resolve(); await sending
    expect(chat.messages[1]).toMatchObject({ content: '已收到的部分', status: 'FAILED' })
    expect(chat.streaming).toBe(false)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('marks a user stop distinctly and preserves an unfinished link', async () => {
    const { chat, sending, handlers } = start()
    handlers.onToken('部分 [商品'); chat.stopStream(); await sending
    expect(chat.messages[1]).toMatchObject({ content: '部分 [商品', status: 'STOPPED' })
    expect(chat.streaming).toBe(false)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('does not leave a message pending after a transport ends without done', async () => {
    const { chat, completion, sending } = start()
    completion.resolve(); await sending
    expect(chat.messages[1].status).toBe('INTERRUPTED')
    expect(chat.messages[1].content).toBe('')
  })

  it.each(['error', 'stop'])('ends running tool indicators on %s', async (reason) => {
    const { chat, completion, sending, handlers } = start()
    handlers.onToolCall({ callId: 'pending-tool', tool: 'product_search' })
    if (reason === 'stop') chat.stopStream()
    else { handlers.onError({ code: 5001, message: '中断' }); completion.resolve() }
    await sending
    expect(chat.messages[1].toolCalls?.[0].status).toBe('interrupted')
  })

  it('does not clear a newer stream when a stopped older stream finishes', async () => {
    const { chat, sending, handlers } = start()
    handlers.onToken('第一条'); chat.stopStream()
    const next = deferred<void>()
    api.stream.mockReturnValue({ promise: next.promise, stop: vi.fn() })
    const newer = chat.sendMessage('第二条')
    await sending
    expect(chat.streaming).toBe(true)
    expect(chat.pendingByConv[7].streaming).toBe(true)
    next.resolve(); await newer
  })
})

describe('new conversation startup performance', () => {
  it('makes a newly created empty conversation usable without detail/history requests', async () => {
    const chat = useChatStore()
    chat.current = conversation(7)
    chat.messages = [{ role: 'AI', content: '旧消息' }]
    chat.streaming = true
    const list = deferred<any>()
    api.list.mockReturnValue(list.promise)
    api.create.mockResolvedValue({ conversationId: 9, convNo: 'C9', status: 'ACTIVE' })
    await chat.createConversation()
    expect(api.detail).not.toHaveBeenCalled()
    expect(api.messages).not.toHaveBeenCalled()
    expect(chat.current).toEqual({ conversationId: 9, convNo: 'C9', status: 'ACTIVE' })
    expect(chat.messages).toEqual([])
    expect(chat.streaming).toBe(false)
    expect(chat.loadingConversationId).toBeNull()
    list.resolve({ records: [conversation(9)] })
    await flush()
  })

  it('does not let an older history request overwrite a newly created conversation', async () => {
    const chat = useChatStore()
    const old = deferred<any>()
    api.detail.mockImplementation(id => id === 7 ? old.promise : Promise.resolve(conversation(id)))
    const previous = chat.openConversation(7)
    api.create.mockResolvedValue({ conversationId: 9, status: 'ACTIVE' })
    await chat.createConversation()
    old.resolve(conversation(7))
    await previous
    expect(chat.current?.conversationId).toBe(9)
    expect(chat.messages).toEqual([])
    expect(chat.loadingConversationId).toBeNull()
  })
})
