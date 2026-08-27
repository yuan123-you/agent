<template>
  <div class="chat-view">
    <!-- 移动端遮罩 -->
    <div v-if="showConvList" class="conv-mask" @click="showConvList = false"></div>
    <!-- 左侧会话列表（移动端为抽屉） -->
    <aside class="conv-panel" :class="{ 'mobile-open': showConvList }">
      <el-button type="primary" class="new-btn" @click="chat.createConversation()">+ 新对话</el-button>
      <div class="conv-list">
        <div
          v-for="c in chat.conversations"
          :key="c.conversationId"
          class="conv-item"
          :class="{ active: chat.current?.conversationId === c.conversationId }"
          @click="openConv(c.conversationId)"
        >
          <div class="conv-title">
            <el-icon v-if="isStreaming(c.conversationId)" class="is-loading conv-spinner">
              <Loading />
            </el-icon>
            <span>{{ c.title || '新对话' }}</span>
          </div>
          <div class="conv-meta">
            <el-tag v-if="c.status !== 'ACTIVE'" size="small" :type="statusTag(c.status)">
              {{ statusText(c.status) }}
            </el-tag>
            <span class="time">{{ shortTime(c.updatedAt) }}</span>
          </div>
        </div>
        <el-empty v-if="chat.conversations.length === 0" description="暂无会话" :image-size="60" />
      </div>
    </aside>

    <!-- 右侧对话区 -->
    <section class="chat-panel">
      <template v-if="chat.current">
        <header class="chat-header">
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
            v-else-if="chat.current.status !== 'PENDING_HUMAN'"
            size="small"
            @click="onClose"
          >
            结束会话
          </el-button>
        </header>

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
            <el-avatar v-if="msg.role !== 'USER'" :size="32" class="avatar">
              {{ msg.role === 'AGENT' ? '客' : 'AI' }}
            </el-avatar>
            <div class="bubble" :class="{ user: msg.role === 'USER', failed: msg.status === 'FAILED' }">
              <AiMessage v-if="msg.role === 'AI'" :msg="msg" :streaming="chat.streaming && i === chat.messages.length - 1" />
              <div v-else class="plain">{{ msg.content }}</div>
            </div>
            <el-avatar v-if="msg.role === 'USER'" :size="32" class="avatar user-avatar">
              {{ (auth.user?.nickname || '我').slice(0, 1) }}
            </el-avatar>
          </div>
        </div>

        <footer class="input-bar">
          <el-input
            v-model="input"
            type="textarea"
            :rows="2"
            :disabled="chat.streaming || chat.current.status === 'PENDING_HUMAN'"
            :placeholder="
              chat.current.status === 'PENDING_HUMAN'
                ? '正在等待人工客服接入…'
                : chat.current.status === 'SERVICING'
                  ? '人工客服服务中，直接输入消息即可（Ctrl+Enter 发送）'
                  : '描述你的需求，如：推荐一款3000以内拍照好的手机（Ctrl+Enter 发送）'
            "
            resize="none"
            @keydown.ctrl.enter.prevent="send(input)"
          />
          <div class="input-actions">
            <!-- 人工客服入口：触发 AI escalate 链路，客服工作台接入 -->
            <el-tooltip content="转接人工客服（工作时间 9:00-22:00）" placement="top">
              <el-button
                circle
                :type="chat.current.status !== 'ACTIVE' ? 'success' : 'default'"
                :disabled="chat.streaming"
                @click="transferHuman"
              >
                <el-icon><Service /></el-icon>
              </el-button>
            </el-tooltip>
            <el-button v-if="chat.streaming" type="danger" @click="chat.stopStream()">停止</el-button>
            <el-button v-else type="primary" :disabled="!input.trim() || chat.current.status === 'PENDING_HUMAN'"
              @click="send(input)">
              发送
            </el-button>
          </div>
        </footer>
      </template>
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
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Link, Loading, Menu, Service } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useChatStore } from '@/stores/chat'
import AiMessage from '@/components/chat/AiMessage.vue'

const auth = useAuthStore()
const chat = useChatStore()
const route = useRoute()

const input = ref('')
const showConvList = ref(false)
const msgList = ref<HTMLElement>()
const showRate = ref(false)
const rateScore = ref(5)
const quickQuestions = ['推荐一款3000以内拍照好的手机', '我的订单到哪了', '支持7天无理由退货吗', '转人工客服']

let pollTimer: number | undefined
let actionExpiryTimer: number | undefined
let stickBottom = true

onMounted(async () => {
  // 角色防护：非买家（如客服/管理员标签页）不加载会话，避免 /chat 接口 403 刷屏
  if (auth.role !== 'CUSTOMER') {
    ElMessage.warning('请使用买家账号访问 AI 助手')
    return
  }
  chat.expireOrderActions()
  actionExpiryTimer = window.setInterval(() => chat.expireOrderActions(), 1000)
  await chat.loadConversations()
  const routeId = Number(route.params.conversationId)
  if (routeId) {
    await openConv(routeId)
  } else if (chat.conversations.length > 0) {
    await openConv(chat.conversations[0].conversationId)
  } else {
    await chat.createConversation()
  }
  startPollingIfNeeded()
})

watch(
  () => chat.messages.length,
  async () => {
    if (stickBottom) {
      await nextTick()
      scrollToBottom()
    }
  },
)

watch(
  () => chat.current?.status,
  () => startPollingIfNeeded(),
)

onBeforeUnmount(() => {
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
  if (!text || chat.streaming) return
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
  return (t || '').slice(5, 16)
}
</script>

<style scoped>
.chat-view {
  display: flex;
  height: 100%;
  background: #fff;
}

.conv-panel {
  width: 260px;
  border-right: 1px solid #e4e7ed;
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
  background: #f5f7fa;
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
  color: #c0c4cc;
}

.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-bottom: 1px solid #ebeef5;
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
  color: #909399;
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
  background: #c0c4cc;
}

.web-search-switch.on .switch-dot {
  background: var(--el-color-primary);
}

.spacer {
  flex: 1;
}

.msg-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
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
  gap: 8px;
  max-width: 86%;
}

.msg-row.right {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.bubble {
  padding: 10px 14px;
  border-radius: 10px;
  background: #f5f7fa;
  font-size: 14px;
  min-width: 0;
}

.bubble.user {
  background: var(--el-color-primary);
  color: #fff;
  white-space: pre-wrap;
}

.bubble.failed {
  border: 1px solid var(--el-color-danger-light-5);
}

.avatar {
  flex-shrink: 0;
  background: var(--el-color-primary);
  color: #fff;
  font-size: 12px;
}

.user-avatar {
  background: #909399;
}

.input-bar {
  display: flex;
  gap: 10px;
  align-items: flex-end;
  padding: 12px 16px;
  border-top: 1px solid #ebeef5;
}

.input-actions {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.input-bar .el-button {
  height: 54px;
}

.rate-body {
  text-align: center;
  padding: 12px 0;
}

/* 会话列表切换按钮：仅移动端显示 */
.conv-toggle {
  display: none;
}

.conv-mask {
  display: none;
}

/* 平板：收窄会话栏 */
@media (max-width: 1024px) {
  .conv-panel {
    width: 210px;
  }
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
    background: #fff;
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
</style>
