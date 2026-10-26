import { API_BASE } from '@/api/base'
/**
 * ⭐ SSE 流式对话核心（fetch + ReadableStream 解析，EventSource 不支持 POST+JWT）
 * 事件：token / tool_call / tool_result / action / error / done
 */
import type { OrderAction } from '@/types/api'

export interface SseHandlers {
  onToken(content: string): void
  onToolCall(evt: { callId: string; tool: string; args?: Record<string, unknown> }): void
  onToolResult(evt: { callId: string; tool: string; result?: { preview?: string } }): void
  onAction(evt: OrderAction): void
  onError(evt: { code: number; message: string }): void
  onDone(evt: { messageId?: number; content?: string; tokenUsage?: unknown; latencyMs?: number }): void
}

export interface SseStream {
  promise: Promise<void>
  stop(): void
}

export function streamChat(
  body: { conversationId: number; content: string; webSearchEnabled?: boolean },
  handlers: SseHandlers,
): SseStream {
  const controller = new AbortController()

  const promise = (async () => {
    const token = localStorage.getItem('token') || ''
    const resp = await fetch(`${API_BASE}/chat/messages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    })

    // 建流前错误（鉴权/参数/限流）：统一 JSON 错误体
    if (!resp.ok || !(resp.headers.get('content-type') || '').includes('event-stream')) {
      const errBody = await resp.json().catch(() => null)
      handlers.onError({
        code: errBody?.code || resp.status,
        message: errBody?.message || '请求失败',
      })
      return
    }

    const reader = resp.body?.getReader()
    if (!reader) {
      handlers.onError({ code: 5001, message: '浏览器不支持流式读取' })
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''
    let eventType = ''
    let dataLines: string[] = []
    let terminal = false

    const dispatch = () => {
      if (terminal) return
      if (dataLines.length === 0) { eventType = ''; return }
      const data = dataLines.join('\n')
      dataLines = []
      let payload: any = null
      try {
        payload = JSON.parse(data)
      } catch {
        payload = {}
      }
      switch (eventType) {
        case 'token':
          handlers.onToken(payload.content || '')
          break
        case 'tool_call':
          handlers.onToolCall({ callId: payload.callId, tool: payload.tool, args: payload.args })
          break
        case 'tool_result':
          handlers.onToolResult({ callId: payload.callId, tool: payload.tool, result: payload.result })
          break
        case 'action':
          handlers.onAction(payload as OrderAction)
          break
        case 'error':
          terminal = true
          handlers.onError({ code: payload.code || 5001, message: payload.message || 'AI 服务异常' })
          break
        case 'done':
          terminal = true
          handlers.onDone(payload)
          break
        default:
          break
      }
      eventType = ''
    }

    // Lines may cross UTF-8/network chunk boundaries, including the final EOF frame.
    const readLine = (line: string) => {
      line = line.replace(/\r$/, '')
      if (line === '') dispatch()
      else if (line.startsWith('event:')) eventType = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
      // Ignore heartbeat comments and unrecognized SSE fields.
    }
    try {
      while (!terminal) {
        const { done, value } = await reader.read()
        buffer += done ? decoder.decode() : decoder.decode(value, { stream: true })
        let newlineIdx: number
        while (!terminal && (newlineIdx = buffer.indexOf('\n')) >= 0) {
          readLine(buffer.slice(0, newlineIdx))
          buffer = buffer.slice(newlineIdx + 1)
        }
        if (done) {
          if (!terminal && buffer) readLine(buffer)
          if (!terminal) dispatch()
          if (!terminal) handlers.onError({ code: 5001, message: '连接已中断，回复未完成，请重试' })
          break
        }
      }
    } finally {
      await reader.cancel().catch(() => {})
      reader.releaseLock()
    }
  })()

  return { promise, stop: () => controller.abort() }
}

