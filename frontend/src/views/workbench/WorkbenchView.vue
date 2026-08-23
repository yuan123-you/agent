<template>
  <div class="page">
    <h3 class="page-title">客服工作台</h3>
    <div v-loading="loading" class="sla-row">
      <div class="sla-card"><div class="num">{{ sla.pendingCount }}</div><div class="label">待接入</div></div>
      <div class="sla-card"><div class="num">{{ sla.servicingCount }}</div><div class="label">服务中</div></div>
      <div class="sla-card"><div class="num">{{ sla.todayNewCount }}</div><div class="label">今日新增</div></div>
      <div class="sla-card"><div class="num">{{ sla.todayHandledCount }}</div><div class="label">今日已处理</div></div>
      <div class="sla-card"><div class="num">{{ firstRespText }}</div><div class="label">平均首次响应</div></div>
    </div>
    <el-tabs v-model="tab" @tab-change="load">
      <el-tab-pane label="待接入" name="pending">
        <div v-loading="loading" class="list">
          <el-card v-for="c in pendingList" :key="c.conversationId" shadow="never" class="conv-card">
            <div class="head">
              <span class="user">{{ c.userNickname }}</span>
              <el-tag type="warning" size="small">等待人工</el-tag>
              <span class="title">{{ c.title || '新对话' }}</span>
              <div class="spacer" />
              <el-button type="primary" size="small" @click="claim(c)">接入</el-button>
            </div>
            <el-collapse v-if="c.summary" class="summary">
              <el-collapse-item title="AI 会话摘要" name="s">
                <div class="summary-text">{{ c.summary }}</div>
              </el-collapse-item>
            </el-collapse>
          </el-card>
          <el-empty v-if="!loading && pendingList.length === 0" description="暂无待接入会话" />
        </div>
      </el-tab-pane>
      <el-tab-pane label="服务中" name="servicing">
        <div v-loading="loading" class="list">
          <el-card v-for="c in servicingList" :key="c.conversationId" shadow="never" class="conv-card">
            <div class="head">
              <span class="user">{{ c.userNickname }}</span>
              <el-tag type="success" size="small">服务中</el-tag>
              <span class="title">{{ c.title || '新对话' }}</span>
              <div class="spacer" />
              <el-button size="small" @click="$router.push(`/workbench/conv/${c.conversationId}`)">
                继续服务
              </el-button>
            </div>
          </el-card>
          <el-empty v-if="!loading && servicingList.length === 0" description="暂无服务中会话" />
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiClaim, apiPending, apiServicing, apiWorkbenchSla } from '@/api'
import type { ConversationVO, WorkbenchSla } from '@/types/api'

const router = useRouter()
const tab = ref('pending')
const loading = ref(false)
const pendingList = ref<ConversationVO[]>([])
const servicingList = ref<ConversationVO[]>([])
const sla = reactive<WorkbenchSla>({
  pendingCount: 0, servicingCount: 0, todayNewCount: 0, todayHandledCount: 0, avgFirstResponseSeconds: 0,
})

const firstRespText = computed(() => {
  const sec = sla.avgFirstResponseSeconds || 0
  if (sec <= 0) return '—'
  if (sec < 60) return `${sec}s`
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return s > 0 ? `${m}分${s}秒` : `${m}分`
})

let timer: number | undefined

async function load() {
  loading.value = true
  try {
    pendingList.value = await apiPending()
    servicingList.value = await apiServicing()
    Object.assign(sla, await apiWorkbenchSla())
  } finally {
    loading.value = false
  }
}

async function claim(c: ConversationVO) {
  try {
    await apiClaim(c.conversationId)
    ElMessage.success('接入成功')
    router.push(`/workbench/conv/${c.conversationId}`)
  } catch {
    await load() // 被他人抢先接入 → 刷新列表
  }
}

onMounted(() => {
  load()
  timer = window.setInterval(load, 10000)
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<style scoped>
.sla-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.sla-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px;
  text-align: center;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.sla-card .num {
  font-size: 24px;
  font-weight: 700;
  color: var(--el-color-primary);
}

.sla-card .label {
  margin-top: 4px;
  font-size: 13px;
  color: #909399;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 100px;
}

.conv-card .head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user {
  font-weight: 600;
}

.title {
  color: #909399;
  font-size: 13px;
  max-width: 300px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.spacer {
  flex: 1;
}

.summary {
  margin-top: 8px;
  border: none;
}

.summary-text {
  color: #606266;
  font-size: 13px;
  line-height: 1.6;
}
</style>
