import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import ElementPlus, { ElMessage } from 'element-plus'
import ChatView from './ChatView.vue'
import chatViewSource from './ChatView.vue?raw'

const mocks = vi.hoisted(() => ({ getChat: vi.fn() }))
vi.mock('@/stores/chat', () => ({ useChatStore: () => mocks.getChat() }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ role: 'CUSTOMER' }) }))
vi.mock('vue-router', () => ({ useRoute: () => ({ params: {} }), useRouter: () => ({ push: vi.fn(), back: vi.fn() }) }))
vi.mock('@/components/chat/AiMessage.vue', () => ({ default: { template: '<div />' } }))

let app: App
let host: HTMLDivElement
const flush = async () => { for (let i = 0; i < 8; i++) await nextTick() }

function createChat() {
  return reactive({
    current: { conversationId: 7, status: 'PENDING_HUMAN', humanWaitExpiresAt: '2099-01-01T00:00:00' },
    conversations: [{ conversationId: 7, status: 'PENDING_HUMAN' }], messages: [],
    loadingConversations: false, loadingConversationId: null,
    pendingByConv: {}, streaming: false, webSearchEnabled: false,
    refreshCurrent: vi.fn().mockResolvedValue(undefined),
    expireOrderActions: vi.fn(), loadConversations: vi.fn(), openConversation: vi.fn(),
    pollNewMessages: vi.fn().mockResolvedValue(undefined), cancelHumanHandoff: vi.fn().mockResolvedValue(undefined),
    sendMessage: vi.fn(),
  })
}
let chat: ReturnType<typeof createChat>

beforeEach(async () => {
  chat = createChat()
  mocks.getChat.mockReturnValue(chat)
  host = document.createElement('div')
  document.body.appendChild(host)
  app = createApp(ChatView).use(ElementPlus)
  app.mount(host)
  await flush()
})
afterEach(() => { app.unmount(); host.remove(); ElMessage.closeAll() })

describe('human handoff controls', () => {
  it('keeps cancellation available while the AI handoff reply is still streaming', async () => {
    chat.streaming = true
    await flush()
    host.querySelector<HTMLButtonElement>('.input-actions .el-button.is-circle')!.click()
    await flush()
    expect(chat.cancelHumanHandoff).toHaveBeenCalledTimes(1)
  })

  it('restores the AI input after cancellation succeeds', async () => {
    chat.cancelHumanHandoff.mockImplementation(async () => { chat.current.status = 'ACTIVE' })
    host.querySelector<HTMLButtonElement>('.input-actions .el-button.is-circle')!.click()
    await flush()
    expect(host.querySelector<HTMLTextAreaElement>('textarea')!.disabled).toBe(false)
    expect(host.querySelector('.chat-header')!.textContent).not.toContain('取消转人工')
  })

  it('starts a handoff only from an active AI conversation', async () => {
    chat.current.status = 'ACTIVE'
    await flush()
    host.querySelector<HTMLButtonElement>('.input-actions .el-button.is-circle')!.click()
    await flush()
    expect(chat.sendMessage).toHaveBeenCalledWith('转人工客服')
    expect(chat.cancelHumanHandoff).not.toHaveBeenCalled()
  })

  it('does not cancel once an agent has joined', async () => {
    chat.current.status = 'SERVICING'
    await flush()
    host.querySelector<HTMLButtonElement>('.input-actions .el-button.is-circle')!.click()
    await flush()
    expect(chat.cancelHumanHandoff).not.toHaveBeenCalled()
    expect(chat.sendMessage).not.toHaveBeenCalled()
  })

  it('lets the buyer cancel from the same customer service button while waiting', async () => {
    host.querySelector<HTMLButtonElement>('.input-actions .el-button.is-circle')!.click()
    await flush()
    expect(chat.cancelHumanHandoff).toHaveBeenCalledTimes(1)
    expect(chat.sendMessage).not.toHaveBeenCalled()
  })

  it('does not submit duplicate cancellations from the header and footer', async () => {
    let complete!: () => void
    chat.cancelHumanHandoff.mockImplementation(() => new Promise<void>(resolve => { complete = resolve }))
    const cancel = [...host.querySelectorAll<HTMLButtonElement>('.chat-header button')]
      .find(button => button.textContent?.includes('取消转人工'))!
    cancel.click()
    cancel.click()
    host.querySelector<HTMLButtonElement>('.input-actions .el-button.is-circle')!.click()
    await flush()
    const calls = chat.cancelHumanHandoff.mock.calls.length
    complete()
    await flush()
    expect(calls).toBe(1)
  })
})

describe('embedded input layout', () => {
  it('uses a compact single-row textarea without removing multiline entry', () => {
    const textarea = host.querySelector<HTMLTextAreaElement>('textarea')!
    expect(textarea.rows).toBe(1)
    expect(textarea.tagName).toBe('TEXTAREA')
  })

  it('embeds the customer service button and send button inside the input-box-wrapper', () => {
    const wrapper = host.querySelector('.input-box-wrapper')!
    expect(wrapper).not.toBeNull()
    const textarea = wrapper.querySelector('textarea')
    expect(textarea).not.toBeNull()
    const serviceBtn = wrapper.querySelector('.input-actions .actions-left .el-button.is-circle')
    expect(serviceBtn).not.toBeNull()
    const sendBtn = wrapper.querySelector('.input-actions .actions-right .el-button')
    expect(sendBtn).not.toBeNull()
  })
})


async function remount() {
  app.unmount()
  host.remove()
  host = document.createElement('div')
  document.body.appendChild(host)
  app = createApp(ChatView).use(ElementPlus)
  app.mount(host)
  await flush()
}

describe('conversation loading and scrolling experience', () => {
  it('reuses the current conversation on remount instead of clearing or reopening it', async () => {
    chat.openConversation.mockClear()
    await remount()
    expect(chat.openConversation).not.toHaveBeenCalled()
    expect(host.querySelector('.chat-header')).not.toBeNull()
  })

  it('shows a loading skeleton instead of empty history or welcome content during startup', async () => {
    chat.current = null as any
    chat.conversations = []
    chat.loadingConversations = true
    let complete!: () => void
    chat.loadConversations.mockImplementation(() => new Promise<void>(resolve => { complete = resolve }))
    await remount()
    expect(host.querySelector('.chat-loading')).not.toBeNull()
    expect(host.textContent).not.toContain('暂无会话')
    expect(host.textContent).not.toContain('点击左侧')
    complete()
    await flush()
  })

  it('offers retry after startup fails without creating an unhandled rejection', async () => {
    chat.current = null as any
    chat.conversations = []
    chat.loadConversations.mockRejectedValue(new Error('offline'))
    await remount()
    expect(host.querySelector('.chat-load-error')).not.toBeNull()
    expect(host.textContent).toContain('重试')
  })

  it('follows streamed content growth but does not pull a reader away from older messages', async () => {
    chat.current.status = 'ACTIVE'
    chat.messages = [{ role: 'AI', content: '第一段', status: 'PENDING' }] as any
    await flush()
    const list = host.querySelector<HTMLElement>('.msg-list')!
    let height = 500
    Object.defineProperty(list, 'scrollHeight', { get: () => height, configurable: true })
    Object.defineProperty(list, 'clientHeight', { value: 200, configurable: true })
    list.scrollTop = 500
    height = 600
    ;(chat.messages[0] as any).content += '第二段'
    await flush()
    expect(list.scrollTop).toBe(600)
    list.scrollTop = 0
    list.dispatchEvent(new Event('scroll'))
    height = 700
    ;(chat.messages[0] as any).content += '第三段'
    await flush()
    expect(list.scrollTop).toBe(0)
  })
})


describe('compact assistant composer', () => {
  it('starts at one row and autosizes long drafts to at most four rows', async () => {
    chat.current.status = 'ACTIVE'
    await flush()
    const textarea = host.querySelector<HTMLTextAreaElement>('textarea')!
    expect(textarea.rows).toBe(1)
    // jsdom has no line-height/layout metrics; verify the actual Element Plus contract.
    expect(chatViewSource).toContain(':autosize="{ minRows: 1, maxRows: 4 }"')
  })

  it('uses a short placeholder instead of a full recommendation example', async () => {
    chat.current.status = 'ACTIVE'
    await flush()
    const placeholder = host.querySelector<HTMLTextAreaElement>('textarea')!.placeholder
    expect(placeholder).toContain('问点什么')
    expect(placeholder).not.toContain('3000')
    expect(placeholder.length).toBeLessThan(32)
  })
})

describe('header actions layout', () => {
  it('does not render the back button in the header', () => {
    expect(host.querySelector('.chat-header .translucent-circle-back')).toBeNull()
  })

  it('places the end session button after the web search switch', async () => {
    chat.current.status = 'ACTIVE'
    await flush()
    const header = host.querySelector('.chat-header')!
    const searchSwitch = header.querySelector('.web-search-switch')!
    expect(searchSwitch).not.toBeNull()
    const closeBtn = [...header.querySelectorAll('button')].find(btn => btn.textContent?.includes('结束会话'))!
    expect(closeBtn).toBeDefined()
    expect(searchSwitch.compareDocumentPosition(closeBtn) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})
