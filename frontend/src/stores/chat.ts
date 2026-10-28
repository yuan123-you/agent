/** 对话状态（Pinia）：会话列表 + 消息 + SSE 流式发送 */
import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import {
  apiCloseConversation, apiConversationDetail, apiConversationStatus, apiConversations,
  apiCreateConversation, apiHumanMessage, apiCancelHuman, apiMessages, apiMessagesAfter, apiSatisfaction, apiConfirmOrderAction, apiCancelOrderAction, apiOrderActionStatus,
} from '@/api'
import { streamChat, type SseStream } from '@/composables/useSseChat'
import { StreamBuffer } from '@/components/mall/StreamBuffer'
import { loadRecovery, saveRecovery, clearRecovery } from './chatRecovery'
import { replyFeedback } from '@/components/chat/replyFeedback'
import type { ChatMessage, ConversationVO, OrderAction, OrderApprovalForm, ToolCard } from '@/types/api'

/** 单个会话的后台流式状态（切换会话/更换页面后恢复渲染用） */
interface PendingStream {
  aiMessage: ChatMessage
  stream: SseStream | null
  streaming: boolean
  flush?: () => void
}

const listLoads = new WeakMap<object, Promise<void>>()
const conversationLoads = new WeakMap<object, { id: number; promise: Promise<void> }>()

interface ChatState {
  loadingConversations: boolean
  loadingConversationId: number | null
  conversations: ConversationVO[]
  current: ConversationVO | null
  messages: ChatMessage[]
  /** 各会话的后台流式任务（key=conversationId）：切走会话/页面后继续生成，切回时恢复 */
  pendingByConv: Record<number, PendingStream>
  streaming: boolean
  webSearchEnabled: boolean
}

export const useChatStore = defineStore('chat', {
  state: (): ChatState => ({
    loadingConversations: false,
    loadingConversationId: null,
    conversations: [],
    current: null,
    messages: [],
    pendingByConv: {},
    streaming: false,
    webSearchEnabled: false,
  }),
  actions: {
    async loadConversations() {
      const existing = listLoads.get(this)
      if (existing) return existing
      this.loadingConversations = true
      const request = (async () => {
        try {
          const page = await apiConversations({ page: 1, size: 50 })
          this.conversations = page.records
        } finally {
          this.loadingConversations = false
          listLoads.delete(this)
        }
      })()
      listLoads.set(this, request)
      return request
    },

    async createConversation() {
      const data = await apiCreateConversation()
      // The create response is enough to display an empty conversation immediately.
      // Invalidate earlier history loads so they cannot replace the new selection.
      conversationLoads.delete(this)
      this.$patch((state) => {
        state.current = data
        state.messages = []
        state.streaming = false
        state.loadingConversationId = null
        state.conversations = [data, ...state.conversations.filter(c => c.conversationId !== data.conversationId)]
      })
      void this.loadConversations().catch(() => {})
    },

    async openConversation(id: number) {
      const existing = conversationLoads.get(this)
      if (existing?.id === id) return existing.promise
      this.loadingConversationId = id
      const load = { id, promise: Promise.resolve() }
      conversationLoads.set(this, load)
      load.promise = (async () => {
        try {
          const [conversation, page] = await Promise.all([
            apiConversationDetail(id), apiMessages(id, { page: 1, size: 100 }),
          ])
          if (conversationLoads.get(this) !== load) return
          const messages: ChatMessage[] = page.records.slice().reverse().map((m) => ({
            ...m,
            toolCalls: parseToolCalls(m as unknown as { toolCalls?: unknown }),
            actions: parseOrderActions(m as unknown as { toolCalls?: unknown }),
          }))
          const pending = this.pendingByConv[id]
          const recovery = !pending ? loadRecovery(id) : undefined
          if (recovery) {
            const last = messages[messages.length - 1]
            const user = [...messages].reverse().find(m => m.role === 'USER')
            const newerQuestion = user && (user.messageId || user.id || 0) > (recovery.recoveryAfterId || 0)
              && user.content !== recovery.requestContent
            if (newerQuestion || (last?.role === 'AI' && (last.messageId || last.id || 0) > (recovery.recoveryAfterId || 0)
                && user?.content === recovery.requestContent)) {
              clearRecovery(id, recovery.requestId)
            } else if (recovery.retryMessageId && (last?.messageId || last?.id) === recovery.retryMessageId) {
              const content = last.content
              Object.assign(last, recovery, { content })
            } else {
              if (user?.content !== recovery.requestContent) messages.push({ role: 'USER', content: recovery.requestContent || '' })
              messages.push(recovery)
            }
          }
          if (pending) {
            const ai = pending.aiMessage
            const loadedIndex = messages.findIndex((m) => ai.messageId != null && (m.messageId || m.id) === ai.messageId)
            if (ai.status === 'PENDING' && loadedIndex >= 0) messages[loadedIndex] = ai
            else if (loadedIndex < 0) messages.push(ai)
          }
          // Commit title, messages and stream state together; ignore stale selections.
          this.$patch((state) => {
            state.current = conversation
            state.messages = messages
            state.streaming = pending?.streaming ?? false
          })
          // Status hydration must not hold up history or overwrite a newer buyer decision.
          for (const action of this.messages.flatMap((message) => message.actions || [])) {
            const status = action.status
            void apiOrderActionStatus(action.actionId).then((fresh) => {
              if (action.status === status) Object.assign(action, fresh)
            }).catch(() => {
              if (action.status === status && Date.parse(action.expiresAt) <= Date.now()) action.status = 'EXPIRED'
            })
          }
        } finally {
          if (conversationLoads.get(this) === load) {
            this.loadingConversationId = null
            conversationLoads.delete(this)
          }
        }
      })()
      return load.promise
    },

    /** Revalidate cached metadata without blanking or refetching the displayed history. */
    async refreshCurrent() {
      const conversation = this.current
      if (!conversation) return
      const fresh = await apiConversationDetail(conversation.conversationId)
      if (this.current === conversation) this.current = fresh
    },

    /** 转人工后轮询：新消息（含 AGENT 消息）+ 会话状态（感知客服接入/服务结束） */
    async pollNewMessages() {
      if (!this.current) return
      const conversation = this.current
      const convId = conversation.conversationId
      const lastId = this.messages.reduce((max, m) => Math.max(max, m.messageId || m.id || 0), 0)
      if (lastId > 0) {
        const fresh = await apiMessagesAfter(convId, lastId)
        if (this.current !== conversation) return
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
      // 取消或切换会话后，丢弃旧轮询，避免恢复已经失效的等待状态。
      if (this.current !== conversation) return
      if (st.status !== conversation.status) {
        const detail = await apiConversationDetail(convId)
        if (this.current === conversation) this.current = detail
      } else {
        conversation.humanWaitExpiresAt = st.humanWaitExpiresAt
      }
    },

    canRetryMessage(message: ChatMessage): boolean {
      if (!this.current || this.pendingByConv[this.current.conversationId]?.streaming) return false
      const action = replyFeedback(message)?.action
      if (!action || this.messages[this.messages.length - 1] !== message) return false
      if (action === 'recover') return !!message.requestId
      return this.current.status === 'ACTIVE' && (message.status === 'FAILED')
        && !!(message.messageId || message.id || message.requestContent)
    },

    async retryMessage(message: ChatMessage): Promise<void> {
      if (!this.canRetryMessage(message)) return
      const question = message.requestContent || [...this.messages.slice(0, this.messages.indexOf(message))].reverse().find(m => m.role === 'USER')?.content
      if (!question) return
      await this.sendMessage(question, message)
    },

    /** ⭐ 发送消息（SSE 流式）：乐观插入 + StreamBuffer 缓冲渲染 + 工具卡片 */
    async sendMessage(content: string, retry?: ChatMessage): Promise<void> {
      if (!this.current) return
      const conversationId = this.current.conversationId
      // 按会话粒度拦截：仅阻止同一会话的重复发送，允许其他会话后台生成
      if (this.pendingByConv[conversationId]?.streaming || !content.trim()) return

      if (!retry) {
        this.messages.push({ role: 'USER', content })
        this.messages.push({ role: 'AI', content: '', toolCalls: [], status: 'PENDING', startedAt: Date.now(),
          requestId: crypto.randomUUID(), requestContent: content, requestWebSearch: this.webSearchEnabled,
          recoveryAfterId: Math.max(0, ...this.messages.map(m => m.messageId || m.id || 0)),
        })
      }
      const aiMsg = retry || this.messages[this.messages.length - 1]
      const resumeOnly = !!retry && (retry.status === 'INTERRUPTED' || retry.status === 'STOPPED' || retry.errorCode === 5003)
      if (retry && !resumeOnly) {
        aiMsg.retryMessageId = aiMsg.messageId || aiMsg.id
        aiMsg.requestId = crypto.randomUUID()
        aiMsg.recoveryAfterId = Math.max(0, ...this.messages.map(m => m.messageId || m.id || 0))
      }
      aiMsg.requestContent = content
      aiMsg.requestWebSearch ??= this.webSearchEnabled
      aiMsg.status = 'PENDING'
      aiMsg.error = undefined
      aiMsg.errorCode = undefined
      aiMsg.startedAt = Date.now()
      saveRecovery(conversationId, aiMsg)
      // 记录该会话的流式状态：切走会话/页面后后台继续生成，切回时恢复
      this.pendingByConv[conversationId] = { aiMessage: aiMsg, stream: null, streaming: true }
      const pending = this.pendingByConv[conversationId]
      const isCurrentStream = () => this.pendingByConv[conversationId] === pending
      this.streaming = true

      const buffer = new StreamBuffer()
      const toolCards = aiMsg.toolCalls ||= []
      let replaced = !retry
      const replaceOutput = () => {
        if (replaced) return
        replaced = true
        toolCards.splice(0)
        aiMsg.actions = []
      }
      let stream: SseStream | null = null
      let renderTimer: ReturnType<typeof setTimeout> | undefined
      const cancelRender = () => {
        if (renderTimer !== undefined) clearTimeout(renderTimer)
        renderTimer = undefined
      }
      const flushPartial = () => {
        cancelRender()
        if (buffer.full) aiMsg.content = buffer.full
      }

      pending.flush = flushPartial
      try {
        stream = streamChat({ conversationId, content, webSearchEnabled: aiMsg.requestWebSearch,
          requestId: aiMsg.requestId, resumeOnly, retryMessageId: aiMsg.retryMessageId }, {
          onToken: (t) => {
            if (!isCurrentStream() || aiMsg.status !== 'PENDING') return
            replaceOutput()
            buffer.push(t)
            if (renderTimer === undefined) {
              renderTimer = setTimeout(() => {
                renderTimer = undefined
                if (isCurrentStream()) aiMsg.content = buffer.renderable
              }, 32)
            }
          },
          onToolCall: (evt) => {
            if (!isCurrentStream() || aiMsg.status !== 'PENDING') return
            replaceOutput()
            toolCards.push({
              callId: evt.callId, tool: evt.tool, args: evt.args, status: 'running',
            })
          },
          onToolResult: (evt) => {
            if (!isCurrentStream() || aiMsg.status !== 'PENDING') return
            replaceOutput()
            const card = toolCards.find((c) => c.callId === evt.callId)
            if (card) {
              card.status = 'done'
              card.result = sanitizeToolResult(evt.result)
            } else {
              toolCards.push({ callId: evt.callId, tool: evt.tool, result: sanitizeToolResult(evt.result), status: 'done' })
            }
          },
          onAction: (action) => {
            if (!isCurrentStream() || aiMsg.status !== 'PENDING') return
            replaceOutput()
            this.upsertOrderAction(aiMsg, action)
          },
          onError: (evt) => {
            if (!isCurrentStream() || aiMsg.status !== 'PENDING') return
            flushPartial()
            aiMsg.status = evt.transport ? 'INTERRUPTED' : 'FAILED'
            aiMsg.errorCode = evt.code
            if (evt.messageId) aiMsg.messageId = evt.messageId
          },
          onDone: (evt) => {
            if (!isCurrentStream() || aiMsg.status !== 'PENDING') return
            cancelRender()
            replaceOutput()
            aiMsg.content = evt.content ?? buffer.full
            aiMsg.messageId = evt.messageId
            aiMsg.status = evt.timedOut ? 'FAILED' : evt.degraded ? 'DEGRADED' : 'SUCCESS'
            if (evt.timedOut) aiMsg.errorCode = 5002
          },
        })
        pending.stream = stream
        await stream.promise
      } catch {
        if (isCurrentStream()) {
          flushPartial()
          if (aiMsg.status === 'PENDING') aiMsg.status = 'INTERRUPTED'
        }
      } finally {
        cancelRender()
        if (!isCurrentStream()) return
        if (aiMsg.status === 'PENDING') {
          flushPartial()
          aiMsg.status = 'INTERRUPTED'
        } else if (aiMsg.status === 'STOPPED') {
          flushPartial()
        }
        if (aiMsg.status === 'INTERRUPTED' || aiMsg.status === 'STOPPED'
            || (aiMsg.status === 'FAILED' && !aiMsg.messageId)) saveRecovery(conversationId, aiMsg)
        else clearRecovery(conversationId, aiMsg.requestId)
        for (const card of toolCards) {
          if (card.status === 'running') card.status = 'interrupted'
        }
        // 清理流式状态：完成后服务端已落库，切回时走接口加载，不再依赖内存
        if (this.pendingByConv[conversationId]?.aiMessage === aiMsg) {
          delete this.pendingByConv[conversationId]
        }
        if (this.current?.conversationId === conversationId) {
          this.streaming = this.pendingByConv[conversationId]?.streaming ?? false
        }
        // 刷新会话列表与状态（可能已转人工/建单）
        this.loadConversations().catch(() => {})
        if (this.current?.conversationId === conversationId) {
          const conversation = this.current
          apiConversationDetail(conversationId)
            .then((c) => { if (this.current === conversation) this.current = c })
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

      const approved = action.type === 'ORDER_CREATE' ? (approval || {
        receiverName: action.receiverName || '',
        receiverPhone: action.receiverPhone || '',
        receiverAddress: action.receiverAddress || '',
      }) : undefined
      action.status = 'CONFIRMING'
      try {
        const result = await apiConfirmOrderAction(actionId, approved)
        Object.assign(action, approved || {}, {
          status: 'CONFIRMED',
          orderId: result.orderId,
          orderNo: result.orderNo,
          amount: result.totalAmount ?? action.amount,
          orderStatus: result.status,
          afterSaleId: result.afterSaleId,
          afterSaleNo: result.afterSaleNo,
        })
        ElMessage.success(action.type === 'ORDER_CREATE' ? '订单创建成功'
          : action.type === 'ORDER_CANCEL' ? '订单已取消' : '售后申请已提交')
        return result
      } catch {
        action.status = Date.parse(action.expiresAt) <= Date.now() ? 'EXPIRED' : 'FAILED'
        return undefined
      }
    },

    stopStream() {
      if (!this.current) return
      const pending = this.pendingByConv[this.current.conversationId]
      if (pending) {
        // 真正中断后台 SSE 流；fetch 中止后由 sendMessage 的 catch/finally 兜底复位
        pending.aiMessage.status = 'STOPPED'
        pending.stream?.stop()
        pending.streaming = false
      }
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
      .filter((event): event is OrderAction => ['ORDER_CREATE', 'ORDER_CANCEL', 'AFTER_SALE_APPLY'].includes(event?.type) && typeof event.actionId === 'string')
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
