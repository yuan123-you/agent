import type { ChatMessage } from '@/types/api'

// Per-tab, account-scoped, one bounded request descriptor per conversation. No transcript/token stored.
function storageKey(conversationId: number): string | null {
  const token = localStorage.getItem('token')
  if (!token) return null
  let hash = 2166136261
  for (const char of token) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619)
  return `chat-recovery:${hash >>> 0}:${conversationId}`
}
export function saveRecovery(conversationId: number, msg: ChatMessage) {
  try {
    const key = storageKey(conversationId)
    if (!key || !msg.requestId) return
    msg.recoveryScope ??= key
    if (msg.recoveryScope !== key) return
    sessionStorage.setItem(key, JSON.stringify({
      requestId: msg.requestId, requestContent: msg.requestContent, requestWebSearch: msg.requestWebSearch,
      retryMessageId: msg.retryMessageId, recoveryAfterId: msg.recoveryAfterId,
      startedAt: msg.startedAt, status: msg.status, errorCode: msg.errorCode,
    }))
  } catch { /* Disabled/full browser storage must not interrupt a live reply. */ }
}
export function loadRecovery(conversationId: number): ChatMessage | undefined {
  try {
    const key = storageKey(conversationId)
    if (!key) return
    const raw = sessionStorage.getItem(key)
    if (!raw) return
    const data = JSON.parse(raw)
    if (typeof data.requestId !== 'string' || !/^[\w-]{8,80}$/.test(data.requestId)
        || typeof data.requestContent !== 'string' || data.requestContent.length > 4000
        || typeof data.startedAt !== 'number' || Date.now() - data.startedAt > 24 * 60 * 60 * 1000) {
      sessionStorage.removeItem(key); return
    }
    return { ...data, recoveryScope: key, role: 'AI', content: '', toolCalls: [], status: data.status === 'STOPPED' ? 'STOPPED' : data.status === 'FAILED' ? 'FAILED' : 'INTERRUPTED' }
  } catch { return }
}
export function clearRecovery(conversationId: number, requestId?: string) {
  try {
    const key = storageKey(conversationId)
    if (key && (!requestId || loadRecovery(conversationId)?.requestId === requestId)) sessionStorage.removeItem(key)
  } catch { /* best effort */ }
}
