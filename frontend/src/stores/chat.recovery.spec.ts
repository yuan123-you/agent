import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useChatStore } from './chat'
const mocks = vi.hoisted(() => ({ stream: vi.fn(), detail: vi.fn(), messages: vi.fn() }))
vi.mock('@/composables/useSseChat', () => ({ streamChat: mocks.stream }))
vi.mock('@/api', () => ({
  apiConversationDetail: mocks.detail, apiMessages: mocks.messages,
  apiConversations: vi.fn().mockResolvedValue({ records: [] }),
  apiCloseConversation: vi.fn(), apiConversationStatus: vi.fn(), apiCreateConversation: vi.fn(),
  apiHumanMessage: vi.fn(), apiCancelHuman: vi.fn(), apiMessagesAfter: vi.fn(), apiSatisfaction: vi.fn(),
  apiConfirmOrderAction: vi.fn(), apiCancelOrderAction: vi.fn(), apiOrderActionStatus: vi.fn(),
}))
vi.mock('element-plus', () => ({ ElMessage: { error: vi.fn(), success: vi.fn() } }))

beforeEach(() => {
  setActivePinia(createPinia())
  sessionStorage.clear()
  localStorage.setItem('token', 'test-owner')
  vi.clearAllMocks()
  mocks.detail.mockResolvedValue({ conversationId: 7, status: 'ACTIVE' })
  mocks.messages.mockResolvedValue({ records: [] })
})
function chat() {
  const store = useChatStore()
  store.current = { conversationId: 7, status: 'ACTIVE' }
  return store
}
describe('chat retry and recovery', () => {
  it('does not insert error copy into the answer and retains the server failure id', async () => {
    mocks.stream.mockImplementation((_body, handlers) => ({ stop: vi.fn(), promise: Promise.resolve().then(() => handlers.onError({ code: 5002, message: 'raw timeout', messageId: 42 })) }))
    const store = chat()
    await store.sendMessage('hello')
    expect(store.messages[1]).toMatchObject({ content: '', status: 'FAILED', errorCode: 5002, messageId: 42 })
  })
  it('recovers an interrupted request with the same identity and preserves partial content', async () => {
    mocks.stream.mockImplementationOnce((_body, handlers) => ({ stop: vi.fn(), promise: Promise.resolve().then(() => { handlers.onToken('部分回答'); throw new TypeError('network') }) }))
    const store = chat()
    await store.sendMessage('hello')
    const message = store.messages[1]
    expect(message.status).toBe('INTERRUPTED')
    const request = mocks.stream.mock.calls[0][0]
    expect(request.requestId).toBeTruthy()
    let done!: () => void
    mocks.stream.mockImplementation((body, handlers) => ({ stop: vi.fn(), promise: new Promise<void>(r => { done = () => { handlers.onToken('完整回答'); handlers.onDone({ content: '完整回答', messageId: 42 }); r() } }) }))
    const retry = store.retryMessage(message)
    expect(message.content).toBe('部分回答')
    expect(mocks.stream.mock.calls[1][0]).toMatchObject({ requestId: request.requestId, resumeOnly: true })
    expect(store.messages.filter(m => m.role === 'USER')).toHaveLength(1)
    done(); await retry
    expect(message.content).toBe('完整回答')
  })
  it('regenerates only a confirmed failed latest reply and coalesces repeated clicks', async () => {
    mocks.stream.mockImplementationOnce((_body, h) => ({ stop: vi.fn(), promise: Promise.resolve().then(() => h.onError({ code: 5001, message: 'failure', messageId: 42 })) }))
    const store = chat()
    await store.sendMessage('hello')
    const message = store.messages[1]
    let finish!: () => void
    mocks.stream.mockImplementation((_body, h) => ({ stop: vi.fn(), promise: new Promise<void>(r => { finish = () => { h.onDone({ content: '成功', messageId: 43 }); r() } }) }))
    const first = store.retryMessage(message), second = store.retryMessage(message)
    expect(mocks.stream).toHaveBeenCalledTimes(2)
    expect(mocks.stream.mock.calls[1][0]).toMatchObject({ retryMessageId: 42, content: 'hello' })
    expect(store.messages).toHaveLength(2)
    finish(); await Promise.all([first, second])
  })
  it('restores an unfinished request after a store recreation without persisting a transcript', async () => {
    mocks.stream.mockImplementation((_body, h) => ({ stop: vi.fn(), promise: Promise.resolve().then(() => { h.onToken('partial'); throw new TypeError('offline') }) }))
    const store = chat()
    await store.sendMessage('hello')
    const requestId = mocks.stream.mock.calls[0][0].requestId
    setActivePinia(createPinia())
    const restored = useChatStore()
    mocks.messages.mockResolvedValue({ records: [{ role: 'USER', content: 'hello' }] })
    await restored.openConversation(7)
    expect(restored.messages.at(-1)).toMatchObject({ status: 'INTERRUPTED', requestId })
    expect(restored.canRetryMessage(restored.messages.at(-1)!)).toBe(true)
  })
})


it('ignores an old stopped stream finishing after recovery starts on the same message', async () => {
  let rejectOld!: (error: Error) => void
  mocks.stream.mockImplementationOnce((_body, h) => ({ stop: vi.fn(), promise: new Promise<void>((_r, reject) => { rejectOld = reject; h.onToken('old') }) }))
  const store = chat()
  const old = store.sendMessage('hello')
  const msg = store.messages[1]
  store.stopStream()
  let finish!: () => void
  mocks.stream.mockImplementation((_body, h) => ({ stop: vi.fn(), promise: new Promise<void>(r => { finish = () => { h.onDone({ content: 'recovered', messageId: 42 }); r() } }) }))
  const recovered = store.retryMessage(msg)
  rejectOld(new Error('aborted')); await old
  expect(msg.status).toBe('PENDING')
  expect(store.streaming).toBe(true)
  finish(); await recovered
  expect(msg.content).toBe('recovered')
})

it('does not expose one account recovery descriptor to another account', async () => {
  mocks.stream.mockImplementation(() => ({ stop: vi.fn(), promise: Promise.reject(new Error('offline')) }))
  await chat().sendMessage('private question')
  localStorage.setItem('token', 'other-owner')
  setActivePinia(createPinia())
  const store = useChatStore()
  await store.openConversation(7)
  expect(store.messages).toHaveLength(0)
})

it('does not resurrect an old interruption after newer messages have been persisted', async () => {
  mocks.stream.mockImplementation(() => ({ stop: vi.fn(), promise: Promise.reject(new Error('offline')) }))
  await chat().sendMessage('old question')
  setActivePinia(createPinia())
  mocks.messages.mockResolvedValue({ records: [
    { role: 'AI', content: 'new answer', messageId: 50, status: 'SUCCESS' },
    { role: 'USER', content: 'new question', messageId: 49 },
  ] })
  const store = useChatStore(); await store.openConversation(7)
  expect(store.messages.at(-1)?.content).toBe('new answer')
  expect(store.messages).toHaveLength(2)
})

it('does not save an old account request under a new account after a late disconnect', async () => {
  let reject!: (error: Error) => void
  mocks.stream.mockImplementation(() => ({ stop: vi.fn(), promise: new Promise<void>((_r, no) => { reject = no }) }))
  const store = chat(); const pending = store.sendMessage('private question')
  localStorage.setItem('token', 'other-owner')
  reject(new Error('offline')); await pending
  setActivePinia(createPinia())
  const other = useChatStore(); await other.openConversation(7)
  expect(other.messages).toHaveLength(0)
})

it('does not mistake the previous failed attempt for the result of an interrupted regeneration', async () => {
  mocks.stream.mockImplementationOnce((_body, h) => ({ stop: vi.fn(), promise: Promise.resolve().then(() => h.onError({ code: 5001, message: 'failure', messageId: 42 })) }))
  const store = chat(); await store.sendMessage('hello')
  mocks.stream.mockImplementationOnce(() => ({ stop: vi.fn(), promise: Promise.reject(new Error('offline')) }))
  await store.retryMessage(store.messages[1])
  const requestId = mocks.stream.mock.calls[1][0].requestId
  setActivePinia(createPinia())
  mocks.messages.mockResolvedValue({ records: [
    { role: 'AI', content: 'old partial', messageId: 42, status: 'FAILED' },
    { role: 'USER', content: 'hello', messageId: 41 },
  ] })
  const restored = useChatStore(); await restored.openConversation(7)
  expect(restored.messages.at(-1)).toMatchObject({ requestId, status: 'INTERRUPTED', content: 'old partial' })
  expect(restored.messages).toHaveLength(2)
})

it('replaces rather than duplicates a persisted failed reply while its regeneration is streaming', async () => {
  const store = chat()
  const ai = { role: 'AI' as const, content: 'retained', messageId: 42, status: 'PENDING' }
  store.pendingByConv[7] = { aiMessage: ai, stream: null, streaming: true }
  mocks.messages.mockResolvedValue({ records: [
    { role: 'AI', content: 'old failure', messageId: 42, status: 'FAILED' },
    { role: 'USER', content: 'hello', messageId: 41 },
  ] })
  await store.openConversation(7)
  expect(store.messages).toHaveLength(2)
  expect(store.messages[1]).toMatchObject({ content: 'retained', status: 'PENDING' })
})
