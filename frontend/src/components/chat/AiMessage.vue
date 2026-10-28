<template>
  <div class="ai-message" @click="onClick">
    <!-- 工具/技能调用卡片 -->
    <div v-if="msg.toolCalls && msg.toolCardsVisible !== false && msg.toolCalls.length" class="tool-cards">
      <ToolCallCard v-for="card in msg.toolCalls" :key="card.callId" :card="card" />
    </div>

    <!-- 1. 等待输出效果：首字未到达或思考检索时展示优雅波纹 -->
    <div v-if="streaming && !msg.content?.trim()" class="ai-thinking-state" role="status" aria-live="polite">
      <div class="thinking-dots" aria-hidden="true">
        <span class="t-dot" />
        <span class="t-dot" />
        <span class="t-dot" />
      </div>
      <div class="thinking-copy">
        <span class="thinking-label">{{ waitingLabel }}…</span>
        <span v-if="elapsedSeconds >= 12" class="thinking-hint">等待时间较长，你可以先暂停接收，稍后恢复回复。</span>
      </div>
      <span class="thinking-elapsed" aria-hidden="true">已等待 {{ elapsedSeconds }} 秒</span>
    </div>

    <!-- 2. 正文流式 Markdown 输出 -->
    <div v-show="answerContent.trim()" class="md-content" v-html="html"></div>

    <!-- 3. 流式打字呼吸光标 -->
    <span v-if="streaming && msg.content?.trim()" class="typing-cursor" />

    <div v-if="!streaming && feedback" class="reply-status" :class="{ 'has-answer': answerContent.trim() }" role="status" aria-live="polite">
      <svg class="status-icon" viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <circle cx="10" cy="10" r="7.25" stroke="currentColor" stroke-width="1.5" />
        <path d="M10 6.5v4M10 13.4v.1" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
      </svg>
      <div class="status-copy">
        <span class="status-title">{{ feedback.title }}</span>
        <span class="status-detail">{{ feedbackDetail }}</span>
        <button v-if="retryAvailable" class="reply-retry" type="button" @click.stop="chat.retryMessage(msg)">
          <svg viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M13 5.5A5.2 5.2 0 1 0 13 10M13 2v3.5H9.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" /></svg>
          {{ feedback.action === 'recover' ? '恢复回复' : '重新生成' }}
        </button>
      </div>
    </div>

    <!-- 4. 订单动作确认卡片 -->
    <div v-if="msg.actions?.length" class="action-cards">
      <ToolCallCard
        v-for="action in msg.actions"
        :key="action.actionId"
        :action="action"
        @confirm="chat.confirmOrderAction"
        @cancel="chat.cancelOrderAction"
        @view-order="viewOrder"
        @view-after-sale="id => router.push('/after-sales/'+id)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { renderMarkdown } from '@/components/mall/link'
import { useChatStore } from '@/stores/chat'
import ToolCallCard from './ToolCallCard.vue'
import type { ChatMessage } from '@/types/api'
import { replyFeedback, visibleReplyContent } from './replyFeedback'

const props = defineProps<{ msg: ChatMessage; streaming?: boolean }>()
const router = useRouter()
const chat = useChatStore()
const answerContent = computed(() => visibleReplyContent(props.msg))
const html = computed(() => renderMarkdown(answerContent.value))
const feedback = computed(() => replyFeedback(props.msg))
const retryAvailable = computed(() => !!feedback.value?.action && chat.canRetryMessage(props.msg))
const feedbackDetail = computed(() => feedback.value?.action && !retryAvailable.value
  ? '此条回复未完成，可参考后续回复，或在下方继续提问。' : feedback.value?.detail)
const now = ref(Date.now())
const localStartedAt = ref(Date.now())
const elapsedSeconds = computed(() => Math.max(0, Math.floor((now.value - (props.msg.startedAt ?? localStartedAt.value)) / 1000)))
const toolLabels: Record<string, string> = {
  product_search: '正在查找符合条件的商品', product_detail: '正在读取商品详情',
  order_query: '正在查询订单信息', kb_search: '正在检索相关资料', web_search: '正在搜索网络信息',
  order_create: '正在准备待确认订单', order_cancel_prepare: '正在准备取消确认',
  after_sale_prepare: '正在准备售后确认', escalate_to_human: '正在联系人工客服',
}
const waitingLabel = computed(() => {
  const cards = props.msg.toolCalls || []
  const running = [...cards].reverse().find((card) => card.status === 'running')
  if (running) return toolLabels[running.tool] || '正在处理你的请求'
  if (cards.some((card) => card.tool === 'kb_search' && card.status === 'done')) return '正在核对资料与引用'
  if (cards.length) return '正在整理回答'
  return elapsedSeconds.value >= 12 ? '仍在思考，请稍候' : '正在思考你的问题'
})
let waitTimer: ReturnType<typeof setInterval> | undefined
function clearWaitTimer() {
  if (waitTimer !== undefined) clearInterval(waitTimer)
  waitTimer = undefined
}
watch(() => props.streaming && !props.msg.content?.trim(), (waiting) => {
  clearWaitTimer()
  if (waiting) {
    localStartedAt.value = props.msg.startedAt ?? Date.now()
    now.value = Date.now()
    waitTimer = setInterval(() => { now.value = Date.now() }, 1000)
  }
}, { immediate: true })
onBeforeUnmount(clearWaitTimer)

function onClick(e: MouseEvent) {
  const target = (e.target as HTMLElement).closest('.ai-link') as HTMLElement | null
  if (target?.dataset.route) router.push(target.dataset.route)
}

function viewOrder(orderId?: number) {
  if (orderId) router.push(`/orders/${orderId}`)
}

</script>

<style scoped>
.ai-message { min-width: 0; }
.tool-cards, .action-cards { display: flex; flex-direction: column; gap: 6px; }
.tool-cards { margin-bottom: 6px; }
.action-cards { margin-top: 12px; }

/* AI 思考等待波纹动画 */
.ai-thinking-state {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  padding: 6px 12px;
  background: rgba(37, 99, 235, 0.08);
  border-radius: 12px;
  color: var(--el-color-primary, #2563eb);
  font-size: 12px;
  margin: 2px 0;
}

:global(html.dark) .ai-thinking-state {
  background: rgba(37, 99, 235, 0.18);
  color: #93c5fd;
}

.thinking-dots {
  display: flex;
  align-items: center;
  gap: 3px;
}

.t-dot {
  width: 5px;
  height: 5px;
  border-radius: 9999px;
  background: currentColor;
  animation: thinkingWave 1.4s infinite ease-in-out both;
}

.t-dot:nth-child(1) { animation-delay: -0.32s; }
.t-dot:nth-child(2) { animation-delay: -0.16s; }
.t-dot:nth-child(3) { animation-delay: 0s; }

@keyframes thinkingWave {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.4;
  }
  40% {
    transform: scale(1.15);
    opacity: 1;
  }
}

.thinking-label {
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.2px;
}

.thinking-copy { display: flex; flex-direction: column; gap: 4px; }
.thinking-hint { color: var(--el-text-color-secondary); font-size: 11px; line-height: 1.5; }
.thinking-elapsed { color: var(--el-text-color-secondary); font-size: 11px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.reply-status {
  display: flex; align-items: flex-start; gap: 10px; padding: 12px 14px;
  max-width: 480px; box-sizing: border-box; border: 1px solid var(--el-border-color-lighter, #e8ebef);
  border-radius: 12px; background: var(--el-fill-color-extra-light, #fafbfc);
  color: var(--el-text-color-regular, #515862); font-size: 13px; line-height: 1.6;
}
.reply-status.has-answer { margin-top: 12px; }
.status-icon { width: 18px; height: 18px; flex: 0 0 18px; margin-top: 2px; color: var(--el-text-color-secondary, #87909c); }
.status-copy { display: flex; flex-direction: column; align-items: flex-start; gap: 3px; min-width: 0; }
.status-title { font-weight: 500; color: var(--el-text-color-primary, #303640); }
.status-detail { color: var(--el-text-color-regular, #606875); font-size: 12px; overflow-wrap: anywhere; }
.reply-retry {
  display: inline-flex; align-items: center; justify-content: center; gap: 6px; min-height: 36px;
  margin-top: 7px; padding: 5px 12px; border: 1px solid var(--el-border-color, #dce1e7);
  border-radius: 7px; background: var(--el-bg-color, #fff); color: var(--el-color-primary, #2563eb);
  font: inherit; font-size: 12px; cursor: pointer;
}
.reply-retry svg { width: 14px; height: 14px; }
.reply-retry:hover { background: var(--el-color-primary-light-9, #eff6ff); border-color: var(--el-color-primary-light-5, #9ec4ff); }
.reply-retry:focus-visible { outline: 2px solid var(--el-color-primary, #2563eb); outline-offset: 3px; }
@media (pointer: coarse) { .reply-retry { min-height: 44px; } }
@media (prefers-reduced-motion: reduce) {
  .t-dot, .typing-cursor { animation: none; }
}

/* 现代流式输出光标 */
.typing-cursor {
  display: inline-block;
  width: 3px;
  height: 15px;
  background: var(--el-color-primary, #2563eb);
  margin-left: 3px;
  vertical-align: -2px;
  border-radius: 1px;
  animation: cursorPulse 0.9s infinite cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes cursorPulse {
  0%, 100% { opacity: 1; transform: scaleY(1); }
  50% { opacity: 0.15; transform: scaleY(0.75); }
}
</style>
