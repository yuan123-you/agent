<template>
  <div class="conv-page">
    <header class="head">
      <el-button size="small" @click="$router.push('/workbench')">返回列表</el-button>
      <span class="title">会话服务中</span>
      <div class="spacer" />
      <el-button type="danger" size="small" @click="finish">结束服务</el-button>
    </header>

    <div ref="msgList" class="msg-list">
      <!-- AI 摘要 -->
      <el-alert v-if="summary" :title="'AI 会话摘要：' + summary" type="info" :closable="false" class="summary" />
      <div v-for="(m, i) in messages" :key="i" class="msg-row" :class="m.role === 'AGENT' ? 'right' : 'left'">
        <el-avatar :size="30" class="avatar">{{ avatarText(m.role) }}</el-avatar>
        <div class="bubble" :class="{ agent: m.role === 'AGENT' }">
          <AiMessage v-if="m.role === 'AI'" :msg="m" />
          <div v-else class="plain">{{ m.content }}</div>
        </div>
      </div>
    </div>

    <footer class="input-bar">
      <el-input
        v-model="input"
        type="textarea"
        :rows="2"
        resize="none"
        placeholder="以人工客服身份回复买家（Ctrl+Enter 发送）"
        @keydown.ctrl.enter.prevent="send"
      />
      <el-button type="primary" :disabled="!input.trim()" :loading="sending" @click="send">发送</el-button>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiAgentMessage, apiFinish, apiWorkbenchMessages, apiWorkbenchStatus } from '@/api'
import AiMessage from '@/components/chat/AiMessage.vue'
import type { ChatMessage } from '@/types/api'

const route = useRoute()
const router = useRouter()

const conversationId = Number(route.params.id)
const messages = ref<ChatMessage[]>([])
const summary = ref('')
const input = ref('')
const sending = ref(false)
const msgList = ref<HTMLElement>()

let pollTimer: number | undefined

onMounted(async () => {
  const list = await apiWorkbenchMessages(conversationId)
  messages.value = list
  // 摘要取自第一条 AI 消息之前的会话信息（简化：从消息中不可得时留空）
  scrollToBottom()
  pollTimer = window.setInterval(async () => {
    try {
      const fresh = await apiWorkbenchMessages(conversationId)
      if (fresh.length !== messages.value.length) {
        messages.value = fresh
        scrollToBottom()
      }
      // 感知买家主动结束会话（CLOSED）→ 提示并返回列表
      const st = await apiWorkbenchStatus(conversationId)
      if (st.status === 'CLOSED') {
        ElMessage.warning('买家已结束会话')
        router.push('/workbench')
      }
    } catch {
      // 轮询失败忽略
    }
  }, 3000)
})

onUnmounted(() => {
  if (pollTimer) window.clearInterval(pollTimer)
})

async function send() {
  const content = input.value.trim()
  if (!content) return
  sending.value = true
  try {
    await apiAgentMessage(conversationId, content)
    input.value = ''
    messages.value = await apiWorkbenchMessages(conversationId)
    scrollToBottom()
  } catch {
    // 拦截器已提示
  } finally {
    sending.value = false
  }
}

async function finish() {
  await ElMessageBox.confirm('结束服务后会话将关闭，买家将收到评价邀请。', '提示', { type: 'warning' })
  await apiFinish(conversationId)
  ElMessage.success('服务已结束')
  router.push('/workbench')
}

function scrollToBottom() {
  nextTick(() => {
    if (msgList.value) msgList.value.scrollTop = msgList.value.scrollHeight
  })
}

function avatarText(role: string): string {
  return { USER: '买', AI: 'AI', AGENT: '我', SYSTEM: '系' }[role] || '?'
}
</script>

<style scoped>
.conv-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
  border-radius: 8px;
}

.head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid #ebeef5;
}

.title {
  font-weight: 600;
}

.spacer {
  flex: 1;
}

.summary {
  margin: 8px 0;
}

.msg-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.msg-row {
  display: flex;
  gap: 8px;
  max-width: 86%;
}

.msg-row.right {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.avatar {
  flex-shrink: 0;
  background: #909399;
  color: #fff;
  font-size: 12px;
}

.bubble {
  padding: 8px 12px;
  border-radius: 8px;
  background: #f5f7fa;
  font-size: 14px;
  white-space: pre-wrap;
  min-width: 0;
}

.bubble.agent {
  background: var(--el-color-primary);
  color: #fff;
}

.input-bar {
  display: flex;
  gap: 10px;
  align-items: flex-end;
  padding: 12px 16px;
  border-top: 1px solid #ebeef5;
}

.input-bar .el-button {
  height: 54px;
}
</style>
