import type { ChatMessage } from '@/types/api'

export function replyFeedback(msg: ChatMessage): { title: string; detail: string; action?: 'recover' | 'retry' } | null {
  if (msg.status === 'INTERRUPTED') return { title: '连接暂时断开', detail: msg.content ? '当前内容已保留，恢复后接回这次回复，不会重复提交。' : '恢复连接后接回这次回复，不会重复提交问题。', action: msg.requestId ? 'recover' : undefined }
  if (msg.status === 'STOPPED') return { title: '已暂停接收回复', detail: '服务端可能仍在处理，可恢复接收这次回复，不会重新执行操作。', action: msg.requestId ? 'recover' : undefined }
  if (msg.status === 'DEGRADED') return { title: '部分服务暂不可用', detail: '以上为目前可提供的信息，暂未核实的内容请稍后再查询。' }
  if (msg.status !== 'FAILED') return null
  if (msg.actions?.length || msg.toolCalls?.some(c => ['order_create', 'order_cancel_prepare', 'after_sale_prepare', 'escalate_to_human'].includes(c.tool))) {
    return { title: '回复未完成，操作信息已保留', detail: '请先查看已有确认卡片或订单状态，避免重复提交。' }
  }
  if (msg.errorCode === 2006) return { title: '上一条回复仍在处理中', detail: '请等待上一条回复结束后，再重试当前问题。', action: 'retry' }
  if ([401, 403, 1002, 1003, 1004, 2003].includes(msg.errorCode || 0)) return { title: '暂时无法继续对话', detail: '请确认登录状态和会话权限后再继续。' }
  if (msg.errorCode === 2004) return { title: '当前会话已结束或已转人工', detail: '请在当前服务入口继续，或新建一个 AI 会话。' }
  if ([2005, 2010, 2011].includes(msg.errorCode || 0)) return { title: '这次回复已无法恢复', detail: '恢复记录已失效或会话已有新消息，请重新提问。' }
  if ([429, 1005].includes(msg.errorCode || 0)) return { title: '发送得有点快', detail: '请稍等片刻，再点击重试。', action: 'retry' }
  if (msg.errorCode === 5003) return { title: '暂时无法恢复连接', detail: '当前内容已保留，请稍后再恢复。', action: 'recover' }
  if (!msg.messageId && !msg.id) return { title: '回复暂时未完成', detail: '暂时无法确认请求结果，请稍后查看会话记录，避免重复提交。' }
  return { title: msg.errorCode === 5002 ? '回复等待超时' : '回复暂时未完成', detail: msg.content ? '当前内容已保留，可以重新生成，无需再发一次问题。' : '这次未能收到完整回复，可以重新生成，无需再发一次问题。', action: 'retry' }
}

export function visibleReplyContent(msg: ChatMessage): string {
  if (msg.status === 'FAILED' && (msg.content === msg.error || ['(无内容)', '生成中断，请重试', '连接已中断，请重试'].includes(msg.content))) return ''
  return msg.content
}
