import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import AiMessage from './AiMessage.vue'
import type { ChatMessage } from '@/types/api'

const mocks = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push }) }))
vi.mock('@/stores/chat', () => ({ useChatStore: () => ({ confirmOrderAction: vi.fn(), cancelOrderAction: vi.fn() }) }))
vi.mock('./ToolCallCard.vue', () => ({ default: { template: '<div class="tool-stub" />' } }))

let app: App | undefined
let host: HTMLDivElement
let props: { msg: ChatMessage; streaming: boolean }
const flush = async () => { await nextTick(); await nextTick() }
function mount(message: Partial<ChatMessage> = {}, streaming = true) {
  props = reactive({ msg: { role: 'AI' as const, content: '', status: 'PENDING', startedAt: Date.now(), ...message }, streaming })
  app = createApp(AiMessage, props)
  app.mount(host)
  return props
}
beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-10-26T04:00:00Z'))
  mocks.push.mockReset()
  host = document.createElement('div')
  document.body.appendChild(host)
})
afterEach(() => { app?.unmount(); app = undefined; host.remove(); vi.useRealTimers() })

describe('AI reply feedback', () => {
  it('starts with an accessible neutral thinking state rather than claiming a product search', () => {
    mount()
    expect(host.querySelector('[role="status"]')).not.toBeNull()
    expect(host.textContent).toContain('正在思考')
    expect(host.textContent).not.toContain('检索商品')
  })

  it('reports the actual running tool and the validation stage after retrieval finishes', async () => {
    mount({ toolCalls: [{ callId: 'kb1', tool: 'kb_search', status: 'running' }] })
    expect(host.textContent).toContain('正在检索相关资料')
    props.msg.toolCalls![0].status = 'done'
    await flush()
    expect(host.textContent).toContain('正在核对资料与引用')
  })

  it('shows elapsed time, a slow-request hint and releases its timer on completion', async () => {
    mount()
    await vi.advanceTimersByTimeAsync(12000)
    expect(host.textContent).toContain('12 秒')
    expect(host.textContent).toContain('可以随时停止')
    props.streaming = false
    props.msg.status = 'SUCCESS'
    props.msg.content = '完成'
    await flush()
    expect(host.querySelector('[role="status"]')).toBeNull()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('keeps the Markdown container stable when the first token arrives', async () => {
    mount()
    const container = host.querySelector('.md-content')
    expect(container).not.toBeNull()
    props.msg.content = '第一段'
    await flush()
    expect(host.querySelector('.md-content')).toBe(container)
  })

  it('navigates links that appear after an initially empty streamed message', async () => {
    mount()
    props.msg.content = '[查看商品](mall://product/7)'
    await flush()
    host.querySelector<HTMLElement>('.ai-link')!.click()
    expect(mocks.push).toHaveBeenCalledWith('/products/7')
  })

  it('shows a distinct stopped state without a thinking animation', () => {
    mount({ content: '保留的回答', status: 'STOPPED' }, false)
    expect(host.textContent).toContain('已停止生成')
    expect(host.querySelector('.ai-thinking-state')).toBeNull()
  })

  it('shows interruption feedback next to retained partial output', () => {
    mount({ content: '部分回答', status: 'FAILED', error: '网络中断，请重试' }, false)
    expect(host.textContent).toContain('部分回答')
    expect(host.querySelector('.reply-status')?.textContent).toContain('网络中断')
  })
})
