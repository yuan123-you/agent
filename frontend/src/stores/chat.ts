/** 对话状态（Pinia）：会话列表 + 消息 + SSE 流式发送 */
import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import {
  apiCloseConversation, apiConversationDetail, apiConversationStatus, apiConversations,
  apiCreateConversation, apiHumanMessage, apiCancelHuman, apiMessages, apiMessagesAfter, apiSatisfaction, apiConfirmOrderAction, apiCancelOrderAction, apiOrderActionStatus,
} from '@/api'
import { streamChat, type SseStream } from '@/composables/useSseChat'
import { StreamBuffer } from '@/components/mall/StreamBuffer'
import type { ChatMessage, ConversationVO, OrderAction, OrderApprovalForm, ToolCard } from '@/types/api'

interface ChatState {
  conversations: ConversationVO[]
  current: ConversationVO | null
  messages: ChatMessage[]
  streaming: boolean
  webSearchEnabled: boolean
}

export const useChatStore = defineStore('chat', {
  state: (): ChatState => ({
    conversations: [],
    current: null,
    messages: [],
    streaming: false,
    webSearchEnabled: false,
  }),
  actions: {
    async loadConversations() {
      const page = await apiConversations({ page: 1, size: 50 })
      this.conversations = page.records
    },

    async createConversation() {
      const data = await apiCreateConversation()
      await this.loadConversations()
      await this.openConversation(data.conversationId)
    },

    async openConversation(id: number) {
      this.current = await apiConversationDetail(id)
      const page = await apiMessages(id, { page: 1, size: 100 })
      // 接口倒序返回 → 反转为时间正序
      this.messages = page.records.slice().reverse().map((m) => ({
        ...m,
        toolCalls: parseToolCalls(m as unknown as { toolCalls?: unknown }),
        actions: parseOrderActions(m as unknown as { toolCalls?: unknown }),
      }))
      await Promise.all(this.messages.flatMap((message) => message.actions || []).map(async (action) => {
        try {
          Object.assign(action, await apiOrderActionStatus(action.actionId))
        } catch {
          if (Date.parse(action.expiresAt) <= Date.now()) action.status = 'EXPIRED'
        }
      }))
    },

    /** 转人工后轮询：新消息（含 AGENT 消息）+ 会话状态（感知客服接入/服务结束） */
    async pollNewMessages() {
      if (!this.current) return
      const convId = this.current.conversationId
      const lastId = this.messages.reduce((max, m) => Math.max(max, m.messageId || m.id || 0), 0)
      if (lastId > 0) {
        const fresh = await apiMessagesAfter(convId, lastId)
        for (const m of fresh) {
          this.messages.push({
            ...m,
            toolCalls: parseToolCalls(m as unknown as { toolCalls?: unknown }),
            actions: parseOrderActions(m as unknown as { toolCalls?: unknown }),
          })
        }
      }
      // 状态轮询：客服接入(SERVICING)/买家或客服结束(CLOSED) 时刷新会话详情
      const st = await apiConversationStatus(convId)
      if (st.status !== this.current.status) {
        this.current = await apiConversationDetail(convId)
      } else {
        this.current.humanWaitExpiresAt = st.humanWaitExpiresAt
      }
    },

    /** ⭐ 发送消息（SSE 流式）：乐观插入 + StreamBuffer 缓冲渲染 + 工具卡片 */
    async sendMessage(content: string): Promise<void> {
      if (!this.current || this.streaming || !content.trim()) return
      const conversationId = this.current.conversationId

      // 乐观插入用户消息与流式 AI 消息
      this.messages.push({ role: 'USER', content })
      this.messages.push({ role: 'AI', content: '', toolCalls: [], status: 'PENDING' })
      // ⚡ 必须通过响应式数组重新取引用：直接持有 push 前的原始对象会被 Vue 深响应式
      // 包装成副本，后续对其 content 的修改不会触发视图更新（"要刷新才显示"根因）
      const aiMsg = this.messages[this.messages.length - 1] as ChatMessage
      this.streaming = true

      const buffer = new StreamBuffer()
      const toolCards = aiMsg.toolCalls as ToolCard[]
      let stream: SseStream | null = null

      try {
        stream = streamChat({ conversationId, content, webSearchEnabled: this.webSearchEnabled }, {
          onToken: (t) => {
            buffer.push(t)
            aiMsg.content = buffer.renderable
          },
          onToolCall: (evt) => {
            toolCards.push({
              callId: evt.callId, tool: evt.tool, args: evt.args, status: 'running',
            })
          },
          onToolResult: (evt) => {
            const card = toolCards.find((c) => c.callId === evt.callId)
            if (card) {
              card.status = 'done'
              card.result = sanitizeToolResult(evt.result)
            } else {
              toolCards.push({ callId: evt.callId, tool: evt.tool, result: sanitizeToolResult(evt.result), status: 'done' })
            }
          },
          onAction: (action) => {
            this.upsertOrderAction(aiMsg, action)
          },
          onError: (evt) => {
            aiMsg.status = 'FAILED'
            if (!aiMsg.content) aiMsg.content = evt.message
            ElMessage.error(evt.message)
          },
          onDone: (evt) => {
            // 终态：渲染完整文本（含闭合链接）
            aiMsg.content = evt.content || buffer.full
            aiMsg.messageId = evt.messageId
            aiMsg.status = 'SUCCESS'
          },
        })
        await stream.promise
      } catch {
        aiMsg.status = 'FAILED'
        if (!aiMsg.content) aiMsg.content = '生成中断，请重试'
      } finally {
        this.streaming = false
        // 刷新会话列表与状态（可能已转人工/建单）
        this.loadConversations().catch(() => {})
        if (this.current?.conversationId === conversationId) {
          apiConversationDetail(conversationId)
            .then((c) => (this.current = c))
            .catch(() => {})
        }
      }
    },

    async cancelHumanHandoff(): Promise<void> {
      if (!this.current || this.current.status !== 'PENDING_HUMAN') return
      const conversationId = this.current.conversationId
      await apiCancelHuman(conversationId)
      this.current = await apiConversationDetail(conversationId)
      await this.loadConversations()
    },
    /** 人工客服服务中：买家消息直达客服（不经过 AI） */
    async sendHumanMessage(content: string): Promise<void> {
      if (!this.current || !content.trim()) return
      const conversationId = this.current.conversationId
      this.messages.push({ role: 'USER', content })
      await apiHumanMessage(conversationId, content)
      // 同步会话最新状态与消息
      this.current = await apiConversationDetail(conversationId)
    },


    /** 插入 action SSE；重放同一 actionId 时只更新卡片数据，不重置终态。 */
    upsertOrderAction(message: ChatMessage, incoming: OrderAction) {
      if (!message.actions) message.actions = []
      const existing = message.actions.find((action) => action.actionId === incoming.actionId)
      if (existing) {
        const status = existing.status || 'PENDING'
        Object.assign(existing, incoming, { status })
        return existing
      }
      const action: OrderAction = { ...incoming, status: 'PENDING' }
      message.actions.push(action)
      return action
    },

    /** 将到期且未结算的 action 推进到 EXPIRED 终态。 */
    expireOrderActions(now = Date.now()) {
      for (const message of this.messages) {
        for (const action of message.actions || []) {
          if ((action.status === 'PENDING' || action.status === 'FAILED')
              && Date.parse(action.expiresAt) <= now) {
            action.status = 'EXPIRED'
          }
        }
      }
    },

    /** 持久化买家的拒绝决定；只有后端接受后才进入 CANCELLED 终态。 */
    async cancelOrderAction(actionId: string) {
      const action = findOrderAction(this.messages, actionId)
      if (!action || (action.status !== 'PENDING' && action.status !== 'FAILED')) return
      action.status = 'CANCELLING'
      try {
        await apiCancelOrderAction(actionId)
        action.status = 'CANCELLED'
      } catch {
        action.status = Date.parse(action.expiresAt) <= Date.now() ? 'EXPIRED' : 'FAILED'
      }
    },

    /** 提交买家核对后的表单。同步锁定状态，使双击与并发调用最多发出一个请求。 */
    async confirmOrderAction(actionId: string, approval?: OrderApprovalForm) {
      const action = findOrderAction(this.messages, actionId)
      if (!action || (action.status !== 'PENDING' && action.status !== 'FAILED')) return
      if (Date.parse(action.expiresAt) <= Date.now()) {
        action.status = 'EXPIRED'
        return
      }

      const approved = approval || {
        receiverName: action.receiverName,
        receiverPhone: action.receiverPhone,
        receiverAddress: action.receiverAddress,
      }
      action.status = 'CONFIRMING'
      try {
        const order = await apiConfirmOrderAction(actionId, approved)
        Object.assign(action, approved, {
          status: 'CONFIRMED',
          orderId: order.orderId,
          orderNo: order.orderNo,
          amount: order.totalAmount,
          orderStatus: order.status,
        })
        ElMessage.success('订单创建成功')
        return order
      } catch {
        action.status = Date.parse(action.expiresAt) <= Date.now() ? 'EXPIRED' : 'FAILED'
        return undefined
      }
    },

    stopStream() {
      // 中止后 finally 兜底复位 streaming
      this.streaming = false
    },

    async closeCurrent() {
      if (!this.current) return
      await apiCloseConversation(this.current.conversationId)
      this.current = await apiConversationDetail(this.current.conversationId)
      await this.loadConversations()
    },

    async rateCurrent(score: number) {
      if (!this.current) return
      await apiSatisfaction(this.current.conversationId, score)
      this.current = await apiConversationDetail(this.current.conversationId)
    },
  },
})

/** 历史消息的 toolCalls JSON 字符串 → 卡片数组 */
function parseToolCalls(msg: { toolCalls?: unknown }): ToolCard[] {
  const raw = msg.toolCalls
  if (!raw) return []
  try {
    const arr = typeof raw === 'string' ? JSON.parse(raw) : raw
    if (!Array.isArray(arr)) return []
    const cards: ToolCard[] = []
    for (const t of arr) {
      if (!t || typeof t !== 'object' || t.type === 'ORDER_CREATE') continue
      const callId = String(t.callId || `${t.tool}-${cards.length}`)
      const exists = cards.find((c) => c.callId === callId)
      if (t.result !== undefined) {
        // tool_result 事件
        if (exists) {
          exists.status = 'done'
          exists.result = sanitizeToolResult(t.result)
        } else {
          cards.push({ callId, tool: String(t.tool || ''), result: sanitizeToolResult(t.result), status: 'done' })
        }
      } else {
        // tool_call 事件
        cards.push({ callId, tool: String(t.tool || ''), args: t.args, status: 'done' })
      }
    }
    return cards
  } catch {
    return []
  }
}


/** 从历史消息保存的 SSE 事件中恢复待人工决策动作。 */
function parseOrderActions(msg: { toolCalls?: unknown }): OrderAction[] {
  if (!msg.toolCalls) return []
  try {
    const events = typeof msg.toolCalls === 'string' ? JSON.parse(msg.toolCalls) : msg.toolCalls
    if (!Array.isArray(events)) return []
    return events
      .filter((event): event is OrderAction => event?.type === 'ORDER_CREATE' && typeof event.actionId === 'string')
      .map((event) => ({ ...event, status: event.status || 'PENDING' }))
  } catch {
    return []
  }
}


/** 旧消息可能持久化了 LangChain ToolMessage 的字符串表示；此类协议内容不展示。 */
function sanitizeToolResult(result: ToolCard['result']): ToolCard['result'] {
  const preview = result?.preview
  if (typeof preview === 'string'
      && /^\s*["']?content=/.test(preview)
      && /\btool_call_id=/.test(preview)) {
    return {}
  }
  return result
}

function findOrderAction(messages: ChatMessage[], actionId: string): OrderAction | undefined {
  for (const message of messages) {
    const action = message.actions?.find((candidate) => candidate.actionId === actionId)
    if (action) return action
  }
  return undefined
}
