import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import ElementPlus, { ElMessage } from 'element-plus'
import ChatView from './ChatView.vue'

const mocks = vi.hoisted(() => ({ getChat: vi.fn() }))
vi.mock('@/stores/chat', () => ({ useChatStore: () => mocks.getChat() }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ role: 'CUSTOMER' }) }))
vi.mock('vue-router', () => ({ useRoute: () => ({ params: {} }) }))
vi.mock('@/components/chat/AiMessage.vue', () => ({ default: { template: '<div />' } }))

let app: App
let host: HTMLDivElement
const flush = async () => { for (let i = 0; i < 8; i++) await nextTick() }

function createChat() {
  return reactive({
    current: { conversationId: 7, status: 'PENDING_HUMAN', humanWaitExpiresAt: '2099-01-01T00:00:00' },
    conversations: [{ conversationId: 7, status: 'PENDING_HUMAN' }], messages: [],
    pendingByConv: {}, streaming: false, webSearchEnabled: false,
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
