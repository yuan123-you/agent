<template>
  <div class="chat-view">
    <!-- 移动端遮罩 -->
    <div v-if="showConvList" class="conv-mask" @click="showConvList = false"></div>
    <!-- 左侧会话列表（移动端为抽屉） -->
    <aside class="conv-panel" :class="{ 'mobile-open': showConvList }">
      <div class="conv-panel-header">
        <div class="cph-left">
          <el-icon :size="18"><ChatDotRound /></el-icon>
          <span class="cph-title">历史对话</span>
        </div>
        <button class="cph-close-btn mobile-only" title="关闭" @click="showConvList = false">✕</button>
      </div>
      <button class="new-conv-pill-btn" :disabled="creatingConversation" @click="handleCreateConv">{{ creatingConversation ? '正在创建…' : '+ 新建对话' }}</button>
      <div class="conv-list" :aria-busy="chat.loadingConversations">
        <el-skeleton v-if="chat.loadingConversations && !chat.conversations.length" :rows="4" animated />
        <div
          v-for="c in chat.conversations"
          :key="c.conversationId"
          class="conv-item"
          :class="{ active: chat.current?.conversationId === c.conversationId }"
          @click="handleSelectConv(c.conversationId)"
        >
          <div class="conv-title">
            <el-icon v-if="isStreaming(c.conversationId) || chat.loadingConversationId === c.conversationId" class="is-loading conv-spinner">
              <Loading />
            </el-icon>
            <span>{{ c.title || '新对话' }}</span>
          </div>
          <div class="conv-meta">
            <el-tag v-if="c.status !== 'ACTIVE'" size="small" :type="statusTag(c.status)">
              {{ statusText(c.status) }}
            </el-tag>
            <span class="time">{{ formatConvTime(c.updatedAt) }}</span>
          </div>
        </div>
        <el-empty v-if="!chat.loadingConversations && !initializing && chat.conversations.length === 0" description="暂无会话" :image-size="60" />
      </div>
    </aside>

    <!-- 右侧对话区 -->
    <section class="chat-panel" :aria-busy="initializing || chat.loadingConversationId != null">
      <template v-if="chat.current">
        <header class="chat-header">
          <button class="translucent-circle-back" title="返回" @click="goBack">
            <el-icon><ArrowLeft /></el-icon>
          </button>
          <el-button class="conv-toggle" size="small" @click="showConvList = true">
            <el-icon><Menu /></el-icon>
          </el-button>
          <span class="title">{{ chat.current.title || '新对话' }}</span>
          <!-- 联网搜索开关 -->
          <el-tooltip content="开启后 AI 将优先联网搜索最新信息" placement="bottom">
            <div class="web-search-switch" :class="{ on: chat.webSearchEnabled }"
              @click="chat.webSearchEnabled = !chat.webSearchEnabled">
              <el-icon :size="14"><Link /></el-icon>
              <span>联网搜索</span>
              <span class="switch-dot"></span>
            </div>
          </el-tooltip>
          <el-tag v-if="chat.current.status !== 'ACTIVE'" :type="statusTag(chat.current.status)">
            {{ statusText(chat.current.status) }}
          </el-tag>
          <div class="spacer" />
          <el-button v-if="chat.current.status === 'CLOSED'" size="small" @click="showRate = true">
            评价会话
          </el-button>
          <el-button
            v-else-if="chat.current.status === 'PENDING_HUMAN'"
            type="warning"
            plain
            size="small"
            :loading="cancellingHuman"
            @click="onCancelHuman"
          >
            取消转人工（{{ waitSeconds }}秒）
          </el-button>
          <el-button v-else size="small" @click="onClose">
            结束会话
          </el-button>
        </header>

        <div v-if="chat.loadingConversationId != null" class="conversation-loading" role="status">
          <el-icon class="is-loading"><Loading /></el-icon> 正在加载对话，当前内容会保留
        </div>
        <!-- 针对具体商品的智能客服咨询挂载条 -->
        <div v-if="consultProduct" class="consult-product-banner">
          <el-image :src="consultProduct.imageUrl" fit="cover" class="cpb-img">
            <template #error><div class="cpb-fallback">🛍️</div></template>
          </el-image>
          <div class="cpb-meta">
            <span class="cpb-name">{{ consultProduct.name }}</span>
            <span class="cpb-price">￥{{ consultProduct.price }}</span>
          </div>
          <el-button size="small" type="primary" round @click="sendProductConsult(consultProduct)">
            发送商品咨询
          </el-button>
          <button class="cpb-close" @click="consultProduct = null">×</button>
        </div>

        <div ref="msgList" class="msg-list" @scroll="onScroll">
          <div v-if="chat.messages.length === 0" class="empty-hero">
            <h3>想买什么？直接告诉我～</h3>
            <div class="chips">
              <el-button v-for="q in quickQuestions" :key="q" round size="small" @click="send(q)">
                {{ q }}
              </el-button>
            </div>
          </div>
          <div
            v-for="(msg, i) in chat.messages"
            :key="i"
            class="msg-row"
            :class="msg.role === 'USER' ? 'right' : 'left'"
          >
            <!-- AI/客服头像：仅在左侧展示 -->
            <el-avatar v-if="msg.role !== 'USER'" :size="34" class="avatar ai-avatar">
              {{ msg.role === 'AGENT' ? '客' : 'AI' }}
            </el-avatar>

            <!-- 消息气泡 -->
            <div class="bubble" :class="{ user: msg.role === 'USER', assistant: msg.role === 'AI', failed: msg.status === 'FAILED' }">
              <AiMessage v-if="msg.role === 'AI'" :msg="msg" :streaming="chat.streaming && i === chat.messages.length - 1" />
              <div v-else class="plain">{{ msg.content }}</div>
            </div>

            <!-- 用户买家头像：固定在最右侧展示 -->
            <el-avatar v-if="msg.role === 'USER'" :size="34" class="avatar user-avatar">
              {{ (auth.user?.nickname || '我').slice(0, 1) }}
            </el-avatar>
          </div>
        </div>

        <footer class="input-bar">
          <div class="input-box-wrapper">
            <el-input
              v-model="input"
              type="textarea"
              :rows="1"
              :autosize="{ minRows: 1, maxRows: 4 }"
              :disabled="chat.loadingConversationId != null || chat.streaming || chat.current.status === 'PENDING_HUMAN'"
              :placeholder="inputPlaceholder"
              resize="none"
              @keydown.ctrl.enter.prevent="send(input)"
            />
            <div class="input-actions">
              <div class="actions-left">
                <!-- 人工客服入口：触发 AI escalate 链路，客服工作台接入 -->
                <el-tooltip :content="chat.current.status === 'PENDING_HUMAN' ? '取消转人工，返回 AI 客服' : '转接人工客服（工作时间 9:00-22:00）'" placement="top">
                  <el-button
                    circle
                    :type="chat.current.status !== 'ACTIVE' ? 'success' : 'default'"
                    :disabled="cancellingHuman || (chat.streaming && chat.current.status !== 'PENDING_HUMAN')"
                    :aria-label="chat.current.status === 'PENDING_HUMAN' ? '取消转人工' : '转接人工客服'"
                    @click="transferHuman"
                  >
                    <el-icon><Service /></el-icon>
                  </el-button>
                </el-tooltip>
              </div>
              <div class="actions-right">
                <el-button v-if="chat.streaming" type="danger" round size="small" @click="chat.stopStream()">停止</el-button>
                <el-button v-else type="primary" round size="small" :disabled="chat.loadingConversationId != null || !input.trim() || chat.current.status === 'PENDING_HUMAN'"
                  @click="send(input)">
                  发送
                </el-button>
              </div>
            </div>
          </div>
        </footer>
      </template>
      <div v-else-if="initializing" class="chat-loading" role="status" aria-label="正在加载对话">
        <el-skeleton :rows="5" animated />
        <p>正在加载你的对话…</p>
      </div>
      <div v-else-if="initializationError" class="chat-load-error" role="alert">
        <p>对话加载失败，请检查网络后重试</p>
        <el-button type="primary" @click="initializeChat">重新加载</el-button>
      </div>
      <el-empty v-else description="点击左侧「新对话」开始" style="margin: auto" />
    </section>

    <!-- 满意度评价 -->
    <el-dialog v-model="showRate" title="会话满意度评价" width="320px">
      <div class="rate-body">
        <el-rate v-model="rateScore" show-text />
      </div>
      <template #footer>
        <el-button type="primary" @click="submitRate">提交评价</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, ChatDotRound, Link, Loading, Menu, Service } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useChatStore } from '@/stores/chat'
import AiMessage from '@/components/chat/AiMessage.vue'
import { remainingHumanWaitSeconds } from './humanHandoff'

const auth = useAuthStore()
const chat = useChatStore()
const route = useRoute()
const router = useRouter()
const initializing = ref(!chat.current)
const initializationError = ref(false)
const creatingConversation = ref(false)
let disposed = false

const input = ref('')
const showConvList = ref(false)
const msgList = ref<HTMLElement>()
const showRate = ref(false)
const rateScore = ref(5)
const waitSeconds = ref(0)
const cancellingHuman = ref(false)
const isMobile = ref(typeof window !== 'undefined' ? window.innerWidth <= 768 : false)
const consultProduct = ref<{ id: number; name: string; price: number; imageUrl: string } | null>(null)

function loadConsultProduct() {
  try {
    const raw = sessionStorage.getItem('aimall_cs_product')
    if (raw) {
      consultProduct.value = JSON.parse(raw)
    }
  } catch {}
}

function sendProductConsult(prod: { id: number; name: string; price: number; imageUrl: string }) {
  const text = `您好，我想了解【${prod.name}】（售价￥${prod.price}）的规格参数、发货时间及优惠情况。`
  send(text)
  consultProduct.value = null
  sessionStorage.removeItem('aimall_cs_product')
}
function updateMobile() {
  isMobile.value = window.innerWidth <= 768
}
const inputPlaceholder = computed(() => {
  if (chat.current?.status === 'PENDING_HUMAN') return '正在等待人工客服接入…'
  const sendHint = isMobile.value ? '' : '（Ctrl+Enter 发送）'
  if (chat.current?.status === 'SERVICING') return `人工客服服务中，直接输入消息即可${sendHint}`
  return `问点什么…${sendHint}`
})
const quickQuestions = ['推荐一款3000以内拍照好的手机', '我的订单到哪了', '支持7天无理由退货吗', '转人工客服']

let pollTimer: number | undefined
let actionExpiryTimer: number | undefined
let stickBottom = true

onMounted(async () => {
  window.addEventListener('resize', updateMobile)
  // 角色防护：非买家（如客服/管理员标签页）不加载会话，避免 /chat 接口 403 刷屏
  if (auth.role !== 'CUSTOMER') {
    ElMessage.warning('请使用买家账号访问 AI 助手')
    return
  }
  chat.expireOrderActions()
  updateHumanWaitCountdown()
  loadConsultProduct()
  actionExpiryTimer = window.setInterval(() => {
    chat.expireOrderActions()
    updateHumanWaitCountdown()
  }, 1000)
  await initializeChat()
  if (!disposed) startPollingIfNeeded()
})

async function initializeChat() {
  initializing.value = true
  initializationError.value = false
  try {
    const routeId = Number(route.params.conversationId)
    if (chat.current && (!routeId || routeId === chat.current.conversationId)) {
      // Keep cached messages/background streams mounted while revalidating metadata.
      void Promise.resolve(chat.loadConversations()).catch(() => {})
      void chat.refreshCurrent().catch(() => {})
      await nextTick()
      if (!disposed) scrollToBottom()
    } else if (routeId) {
      void Promise.resolve(chat.loadConversations()).catch(() => {})
      await openConv(routeId)
    } else {
      await chat.loadConversations()
      if (disposed) return
      if (chat.conversations.length > 0) await openConv(chat.conversations[0].conversationId)
      else await chat.createConversation()
    }
  } catch {
    initializationError.value = true
  } finally {
    initializing.value = false
  }
}

watch(
  () => {
    const last = chat.messages[chat.messages.length - 1]
    return [chat.messages.length, last?.content, last?.status,
      last?.toolCalls?.map((card) => card.status).join(','), last?.actions?.length]
  },
  async () => {
    if (stickBottom) {
      await nextTick()
      scrollToBottom()
    }
  },
)

watch(
  () => chat.current?.status,
  () => {
    startPollingIfNeeded()
    updateHumanWaitCountdown()
  },
)

onBeforeUnmount(() => {
  disposed = true
  window.removeEventListener('resize', updateMobile)
  if (pollTimer) window.clearInterval(pollTimer)
  if (actionExpiryTimer) window.clearInterval(actionExpiryTimer)
})

function startPollingIfNeeded() {
  const need = chat.current && chat.current.status !== 'ACTIVE' && chat.current.status !== 'CLOSED'
  if (need && !pollTimer) {
    pollTimer = window.setInterval(async () => {
      try {
        await chat.pollNewMessages()
      } catch {
        // 轮询失败忽略
      }
    }, 3000)
  } else if (!need && pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = undefined
  }
}

async function openConv(id: number) {
  stickBottom = true
  showConvList.value = false
  await chat.openConversation(id)
  await nextTick()
  scrollToBottom()
}

async function send(content: string) {
  const text = (content || '').trim()
  if (!text || chat.streaming || chat.loadingConversationId != null) return
  input.value = ''
  stickBottom = true
  // 人工客服服务中：消息直达客服（不经过 AI）
  if (chat.current?.status === 'SERVICING') {
    try {
      await chat.sendHumanMessage(text)
    } catch {
      // 拦截器已提示（如会话已结束）
    }
    return
  }
  await chat.sendMessage(text)
}

/** 转人工客服：直接发送"转人工"消息，AI 调用 escalate 工具后会话进入 PENDING_HUMAN，客服工作台接入 */
function transferHuman() {
  if (chat.current?.status === 'PENDING_HUMAN') {
    void onCancelHuman()
    return
  }
  if (chat.streaming) return
  // 已转人工/服务中/已结束时给用户提示
  if (chat.current && chat.current.status !== 'ACTIVE') {
    ElMessage.info(
      chat.current.status === 'PENDING_HUMAN'
        ? '已提交转人工申请，请耐心等待客服接入'
        : chat.current.status === 'SERVICING'
          ? '人工客服正在服务中'
          : '会话已结束，请新建会话再转人工',
    )
    return
  }
  send('转人工客服')
}

let refreshingExpiredHandoff = false

function updateHumanWaitCountdown() {
  waitSeconds.value = chat.current?.status === 'PENDING_HUMAN'
    ? remainingHumanWaitSeconds(chat.current.humanWaitExpiresAt)
    : 0
  if (chat.current?.status === 'PENDING_HUMAN' && waitSeconds.value === 0 && !refreshingExpiredHandoff) {
    refreshingExpiredHandoff = true
    chat.pollNewMessages()
      .then(() => {
        if (chat.current?.status === 'ACTIVE') ElMessage.warning('等待人工客服超时，已恢复 AI 客服')
      })
      .finally(() => { refreshingExpiredHandoff = false })
  }
}

async function onCancelHuman() {
  if (cancellingHuman.value || chat.current?.status !== 'PENDING_HUMAN') return
  cancellingHuman.value = true
  try {
    await chat.cancelHumanHandoff()
    ElMessage.success('已取消转人工，恢复 AI 客服')
  } catch {
    await chat.pollNewMessages().catch(() => {})
  } finally {
    cancellingHuman.value = false
  }
}
async function onClose() {
  try {
    await ElMessageBox.confirm('确定结束当前会话吗？', '提示', { type: 'warning' })
    await chat.closeCurrent()
    showRate.value = true
  } catch {
    // 取消
  }
}

async function submitRate() {
  await chat.rateCurrent(rateScore.value)
  showRate.value = false
}

function scrollToBottom() {
  if (msgList.value) {
    msgList.value.scrollTop = msgList.value.scrollHeight
  }
}

function onScroll() {
  if (!msgList.value) return
  const el = msgList.value
  stickBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60
}

function statusText(status: string): string {
  return { ACTIVE: 'AI 服务中', PENDING_HUMAN: '等待人工', SERVICING: '人工服务中', CLOSED: '已结束' }[status] || status
}

/** 该会话是否正在后台流式生成（用于列表指示） */
function isStreaming(conversationId: number): boolean {
  return !!chat.pendingByConv[conversationId]?.streaming
}

function statusTag(status: string): 'warning' | 'success' | 'info' {
  return { PENDING_HUMAN: 'warning', SERVICING: 'success', CLOSED: 'info' }[status] as never || 'info'
}

function shortTime(t?: string): string {
  return (t || '').slice(5, 16).replace('T', ' ')
}

function formatConvTime(t?: string): string {
  if (!t) return ''
  const d = new Date(t)
  if (isNaN(d.getTime())) return t.slice(5, 16).replace('T', ' ')
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${m}-${day} ${h}:${min}`
}

function goBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/')
  }
}

function handleSelectConv(id: number) {
  if (chat.current?.conversationId === id && chat.loadingConversationId == null) return
  void openConv(id).catch(() => ElMessage.error('加载对话失败，请重试'))
  showConvList.value = false
}

async function handleCreateConv() {
  if (creatingConversation.value) return
  creatingConversation.value = true
  try {
    await chat.createConversation()
    showConvList.value = false
    stickBottom = true
    await nextTick()
    scrollToBottom()
  } catch {
    ElMessage.error('创建对话失败，请重试')
  } finally {
    creatingConversation.value = false
  }
}
</script>

<style scoped>
.chat-loading, .chat-load-error { width: min(480px, 85%); margin: auto; padding: 32px 20px; color: var(--el-text-color-secondary); }
.chat-load-error { text-align: center; }
.conversation-loading { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 8px 16px; font-size: 12px; color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.new-conv-pill-btn:disabled { opacity: .6; cursor: wait; }
@media (prefers-reduced-motion: reduce) {
  .chat-view :deep(.el-skeleton__item), .chat-view :deep(.is-loading) { animation: none !important; }
}

.chat-view {
  display: flex;
  height: calc(100vh - 56px - env(safe-area-inset-bottom));
  height: calc(100dvh - 56px - env(safe-area-inset-bottom));
  overflow: hidden;
  position: relative;
  background: var(--mall-surface, #fff);
}

@media (min-width: 769px) {
  .chat-view {
    height: 100vh;
    height: 100dvh;
  }
}

.conv-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--mall-border-light, #f4f4f5);
}

.cph-left {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 700;
  color: #18181b;
}

html.dark .cph-left {
  color: #f4f4f5;
}

.cph-close-btn {
  border: none;
  background: transparent;
  color: #71717a;
  font-size: 16px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
}

.new-conv-pill-btn {
  width: 100%;
  height: 38px;
  border: none;
  background: linear-gradient(135deg, #18181b 0%, #27272a 100%);
  color: #ffffff;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

html.dark .new-conv-pill-btn {
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
}

.new-conv-pill-btn:hover {
  opacity: 0.9;
}

.conv-panel {
  width: 260px;
  border-right: 1px solid var(--el-border-color, #e4e7ed);
  display: flex;
  flex-direction: column;
  padding: 12px;
  gap: 12px;
}

.new-btn {
  width: 100%;
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.conv-item {
  padding: 10px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid transparent;
}

.conv-item:hover {
  background: var(--mall-surface-2, #f5f7fa);
}

.conv-item.active {
  background: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary-light-7);
}

.conv-title {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
}

.conv-title > span {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-spinner {
  flex-shrink: 0;
  color: var(--el-color-primary);
}

.conv-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
}

.time {
  font-size: 12px;
  color: var(--el-text-color-placeholder, #c0c4cc);
}

.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  overflow: hidden;
  position: relative;
}

.chat-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
}

.chat-header .title {
  font-weight: 600;
  max-width: 400px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 联网搜索开关 */
.web-search-switch {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
  border: 1px solid #dcdfe6;
  border-radius: 12px;
  padding: 3px 8px 3px 6px;
  cursor: pointer;
  user-select: none;
  transition: all 0.2s;
}

.web-search-switch.on {
  color: var(--el-color-primary);
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.switch-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--el-text-color-placeholder, #c0c4cc);
}

.web-search-switch.on .switch-dot {
  background: var(--el-color-primary);
}

.spacer {
  flex: 1;
}

.msg-list {
  flex: 1 1 0%;
  min-height: 0;
  overflow-y: auto;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.empty-hero {
  margin: auto;
  text-align: center;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  margin-top: 12px;
}

.msg-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  max-width: 86%;
}

.msg-row.left {
  align-self: flex-start;
  margin-right: auto;
  flex-direction: row;
}

.msg-row.right {
  align-self: flex-end;
  margin-left: auto;
  flex-direction: row;
  justify-content: flex-end;
}

.bubble {
  padding: 10px 14px;
  border-radius: 14px 14px 14px 2px;
  background: var(--mall-surface, #ffffff);
  border: 1px solid var(--mall-border-light, #f4f4f5);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  font-size: 14px;
  line-height: 1.6;
  min-width: 0;
  word-break: break-word;
}

html.dark .bubble {
  background: var(--mall-surface-2, #18181b);
  border-color: var(--mall-border, #27272a);
}

/* Compact assistant: unboxed replies, one-line composer; existing mall tokens. */
.bubble.assistant,
html.dark .bubble.assistant {
  padding: 4px 0;
  background: transparent;
  border: none;
  border-radius: 0;
  box-shadow: none;
}

.bubble.user {
  background: linear-gradient(135deg, #18181b 0%, #27272a 100%);
  color: #ffffff;
  border: none;
  border-radius: 14px 14px 2px 14px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  white-space: pre-wrap;
}

html.dark .bubble.user {
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
}

.bubble.failed {
  border: 1px solid var(--el-color-danger-light-5);
}

.avatar {
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 700;
}

.ai-avatar {
  background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%);
  color: #ffffff;
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.25);
}

.user-avatar {
  background: linear-gradient(135deg, #475569 0%, #334155 100%);
  color: #ffffff;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
}

/* 手机：会话列表抽屉化 */
@media (max-width: 768px) {
  .conv-toggle {
    display: inline-flex;
  }

  .conv-mask {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.35);
    z-index: 30;
  }

  .conv-panel {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 56px;
    width: 78%;
    max-width: 320px;
    background: var(--mall-surface, #fff);
    z-index: 31;
    transform: translateX(-100%);
    transition: transform 0.2s ease;
    box-shadow: 2px 0 12px rgba(0, 0, 0, 0.12);
  }

  .conv-panel.mobile-open {
    transform: translateX(0);
  }

  .chat-header .title {
    max-width: 150px;
  }

  .msg-row {
    max-width: 94%;
  }

  .empty-hero h3 {
    font-size: 16px;
  }

  .chips {
    flex-direction: column;
  }
}

.input-bar {
  display: flex;
  flex-direction: column;
  padding: 10px 14px calc(10px + env(safe-area-inset-bottom));
  border-top: 1px solid var(--mall-border-light, #f4f4f5);
  background: var(--mall-surface, #ffffff);
  flex-shrink: 0;
  z-index: 10;
}

.input-box-wrapper {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  background: var(--mall-surface-2, #f4f4f5);
  border: 1px solid var(--mall-border, #e4e4e7);
  border-radius: 14px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
  overflow: hidden;
}

.input-box-wrapper:focus-within {
  border-color: var(--el-color-primary, #2563eb);
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12);
  background: var(--mall-surface, #ffffff);
}

html.dark .input-box-wrapper {
  background: var(--mall-surface-2, #18181b);
  border-color: var(--mall-border, #27272a);
}

html.dark .input-box-wrapper:focus-within {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
  background: var(--mall-surface, #121215);
}

.input-box-wrapper :deep(.el-textarea) {
  width: 100%;
  min-width: 0;
}

.input-box-wrapper :deep(.el-textarea__inner) {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
  padding: 10px 4px 10px 12px;
  font-size: 14px;
  line-height: 1.5;
  color: inherit;
  resize: none;
}

.input-box-wrapper :deep(.el-textarea__inner:focus) {
  box-shadow: none !important;
}

.input-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 5px 8px 5px 4px;
  gap: 8px;
}

.actions-left,
.actions-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.actions-left .el-button.is-circle {
  width: 32px;
  height: 32px;
  min-width: 32px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  border: 1px solid var(--mall-border, #e4e4e7);
  background: var(--mall-surface, #ffffff);
  color: #52525b;
  transition: all 0.2s ease;
}

.actions-left .el-button.is-circle:not(.is-disabled):hover {
  border-color: #2563eb;
  color: #2563eb;
  background: rgba(37, 99, 235, 0.06);
}

html.dark .actions-left .el-button.is-circle {
  background: #27272a;
  border-color: #3f3f46;
  color: #a1a1aa;
}

html.dark .actions-left .el-button.is-circle:not(.is-disabled):hover {
  border-color: #3b82f6;
  color: #60a5fa;
  background: rgba(59, 130, 246, 0.15);
}

.actions-left .el-button.el-button--success.is-circle {
  background: #10b981 !important;
  color: #ffffff !important;
  border-color: #10b981 !important;
}

.actions-right .el-button {
  height: 32px;
  padding: 0 16px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.chat-header {
  flex-wrap: wrap;
}

@media (max-width: 768px) {
  .chat-header {
    padding: 8px 10px;
    gap: 6px;
  }

  .chat-header .title {
    max-width: 120px;
    font-size: 14px;
  }

  .web-search-switch {
    padding: 2px 6px;
    font-size: 11px;
  }

  .msg-list {
    padding: 10px;
    gap: 10px;
  }

  .input-bar {
    /* The navigation below already includes the bottom safe area. */
    padding: 8px 10px 0;
  }
}

.consult-product-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--mall-surface, #ffffff);
  border-bottom: 1px solid var(--mall-border-light, #f4f4f5);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.cpb-img {
  width: 36px;
  height: 36px;
  border-radius: 6px;
  flex-shrink: 0;
}

.cpb-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f4f4f5;
  font-size: 16px;
}

.cpb-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.cpb-name {
  font-size: 12px;
  font-weight: 600;
  color: #18181b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

html.dark .cpb-name {
  color: #f4f4f5;
}

.cpb-price {
  font-size: 12px;
  font-weight: 700;
  color: var(--mall-price, #e11d48);
}

.cpb-close {
  border: none;
  background: transparent;
  color: #a1a1aa;
  font-size: 16px;
  cursor: pointer;
  padding: 0 4px;
}
</style>


