import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from './auth'
import { useChatStore } from './chat'
const api = vi.hoisted(() => ({ list: vi.fn(), create: vi.fn(), detail: vi.fn(), history: vi.fn(), stream: vi.fn() }))
vi.mock('@/api', () => ({
  apiLogin: vi.fn(), apiLogout: vi.fn(), apiMe: vi.fn(), apiRegister: vi.fn(), apiRegisterCustomer: vi.fn(), apiRegisterMerchant: vi.fn(),
  apiConversations: api.list, apiCreateConversation: api.create, apiConversationDetail: api.detail, apiMessages: api.history,
  apiCloseConversation: vi.fn(), apiConversationStatus: vi.fn(), apiHumanMessage: vi.fn(), apiCancelHuman: vi.fn(),
  apiMessagesAfter: vi.fn(), apiSatisfaction: vi.fn(), apiConfirmOrderAction: vi.fn(), apiCancelOrderAction: vi.fn(), apiOrderActionStatus: vi.fn(),
}))
vi.mock('@/composables/useSseChat', () => ({ streamChat: api.stream }))
vi.mock('element-plus', () => ({ ElMessage: { error: vi.fn(), success: vi.fn() } }))
const account = (id: number) => ({ accessToken: 'token-' + id, refreshToken: 'refresh-' + id,
  user: { userId: id, username: 'buyer' + id, nickname: 'Buyer ' + id, role: 'CUSTOMER' as const } })
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes }); return { promise, resolve } }
beforeEach(() => { vi.resetAllMocks(); localStorage.clear(); sessionStorage.clear(); setActivePinia(createPinia()); api.list.mockResolvedValue({ records: [] }) })
describe('chat account isolation', () => {
  it('clears prior transcripts and detaches all background streams on logout, ignoring late callbacks', async () => {
    const auth = useAuthStore(); auth.setAuth(account(1)); const chat = useChatStore()
    chat.current = { conversationId: 7, status: 'ACTIVE' }; chat.conversations = [chat.current]
    const finish = deferred<void>(); const stop = vi.fn(); let handlers: any
    api.stream.mockImplementation((_body, h) => { handlers = h; return { promise: finish.promise, stop } })
    const sending = chat.sendMessage('private question')
    auth.logoutLocal(); auth.setAuth(account(2))
    expect(stop).toHaveBeenCalledOnce(); expect(chat.current).toBeNull(); expect(chat.messages).toEqual([])
    expect(chat.conversations).toEqual([]); expect(chat.pendingByConv).toEqual({}); expect(chat.streaming).toBe(false)
    handlers.onToken('private answer'); handlers.onDone({ content: 'private answer', messageId: 42 }); finish.resolve(); await sending
    expect(chat.messages).toEqual([]); expect(chat.current).toBeNull(); expect(api.list).not.toHaveBeenCalled()
  })
  it('preserves same-account token refresh but clears a direct account switch', () => {
    const auth = useAuthStore(); auth.setAuth(account(1)); const chat = useChatStore()
    chat.current = { conversationId: 7, status: 'ACTIVE' }; chat.messages = [{ role: 'AI', content: 'private answer' }]
    auth.setAuth({ ...account(1), accessToken: 'refreshed' }); expect(chat.messages).toHaveLength(1)
    auth.setAuth(account(2)); expect(chat.messages).toEqual([]); expect(chat.current).toBeNull()
  })
  it.each(['list', 'create', 'history'])('discards a previous account pending %s response after switching accounts', async kind => {
    const auth = useAuthStore(); auth.setAuth(account(1)); const chat = useChatStore()
    const pending = deferred<any>(); let request: Promise<void>
    if (kind === 'list') { api.list.mockReturnValue(pending.promise); request = chat.loadConversations() }
    else if (kind === 'create') { api.create.mockReturnValue(pending.promise); request = chat.createConversation() }
    else { api.detail.mockResolvedValue({ conversationId: 7, status: 'ACTIVE' }); api.history.mockReturnValue(pending.promise); request = chat.openConversation(7) }
    auth.setAuth(account(2))
    pending.resolve(kind === 'list' ? { records: [{ conversationId: 7, status: 'ACTIVE' }] } : kind === 'create' ? { conversationId: 7, status: 'ACTIVE' } : { records: [{ role: 'AI', content: 'private' }] })
    await request; expect(chat.current).toBeNull(); expect(chat.messages).toEqual([]); expect(chat.conversations).toEqual([])
  })
})
