<template>
  <div class="ai-message">
    <div v-if="msg.toolCalls && msg.toolCardsVisible !== false && msg.toolCalls.length" class="tool-cards">
      <ToolCallCard v-for="card in msg.toolCalls" :key="card.callId" :card="card" />
    </div>
    <div ref="el" class="md-content" v-html="html"></div>
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
    <span v-if="streaming" class="typing-cursor"></span>
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
</style>
