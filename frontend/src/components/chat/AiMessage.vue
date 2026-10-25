<template>
  <div class="ai-message">
    <!-- 工具/技能调用卡片 -->
    <div v-if="msg.toolCalls && msg.toolCardsVisible !== false && msg.toolCalls.length" class="tool-cards">
      <ToolCallCard v-for="card in msg.toolCalls" :key="card.callId" :card="card" />
    </div>

    <!-- 1. 等待输出效果：首字未到达或思考检索时展示优雅波纹 -->
    <div v-if="streaming && !msg.content?.trim()" class="ai-thinking-state">
      <div class="thinking-dots">
        <span class="t-dot" />
        <span class="t-dot" />
        <span class="t-dot" />
      </div>
      <span class="thinking-label">AI 顾问正在检索商品并思考回答…</span>
    </div>

    <!-- 2. 正文流式 Markdown 输出 -->
    <div v-if="msg.content?.trim()" ref="el" class="md-content" v-html="html"></div>

    <!-- 3. 流式打字呼吸光标 -->
    <span v-if="streaming && msg.content?.trim()" class="typing-cursor" />

    <!-- 4. 订单动作确认卡片 -->
    <div v-if="msg.actions?.length" class="action-cards">
      <ToolCallCard
        v-for="action in msg.actions"
        :key="action.actionId"
        :action="action"
        @confirm="chat.confirmOrderAction"
        @cancel="chat.cancelOrderAction"
        @view-order="viewOrder"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { renderMarkdown } from '@/components/mall/link'
import { useChatStore } from '@/stores/chat'
import ToolCallCard from './ToolCallCard.vue'
import type { ChatMessage } from '@/types/api'

const props = defineProps<{ msg: ChatMessage; streaming?: boolean }>()
const router = useRouter()
const chat = useChatStore()
const el = ref<HTMLElement>()
const html = computed(() => renderMarkdown(props.msg.content))

function onClick(e: MouseEvent) {
  const target = (e.target as HTMLElement).closest('.ai-link') as HTMLElement | null
  if (target?.dataset.route) router.push(target.dataset.route)
}

function viewOrder(orderId?: number) {
  if (orderId) router.push(`/orders/${orderId}`)
}

onMounted(() => el.value?.addEventListener('click', onClick))
onBeforeUnmount(() => el.value?.removeEventListener('click', onClick))
</script>

<style scoped>
.ai-message { min-width: 0; }
.tool-cards, .action-cards { display: flex; flex-direction: column; gap: 6px; }
.tool-cards { margin-bottom: 6px; }
.action-cards { margin-top: 12px; }

/* AI 思考等待波纹动画 */
.ai-thinking-state {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: rgba(37, 99, 235, 0.08);
  border-radius: 9999px;
  color: var(--el-color-primary, #2563eb);
  font-size: 12px;
  margin: 2px 0;
}

html.dark .ai-thinking-state {
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
