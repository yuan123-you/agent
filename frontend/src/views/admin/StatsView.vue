<template>
  <div class="page" v-loading="loading">
    <h3 class="page-title">使用统计</h3>

    <div class="cards">
      <el-card shadow="never" class="stat-card">
        <div class="stat-value">{{ stats?.todayConversationCount ?? '-' }}</div>
        <div class="stat-label">今日会话数</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-value">{{ stats?.todayAiMessageCount ?? '-' }}</div>
        <div class="stat-label">今日 AI 消息数</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-value">{{ totalToolCalls }}</div>
        <div class="stat-label">今日工具调用总数</div>
      </el-card>
    </div>

    <el-row :gutter="16" class="panels">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>热门问题 TOP10（今日）</template>
          <el-table :data="stats?.topQuestions || []" size="small">
            <el-table-column prop="keyword" label="问题（前缀）" min-width="180" show-overflow-tooltip />
            <el-table-column prop="count" label="次数" width="90" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>工具调用分布（今日）</template>
          <el-table :data="toolCallRows" size="small">
            <el-table-column prop="tool" label="工具" min-width="150">
              <template #default="{ row }">{{ toolText(row.tool) }}</template>
            </el-table-column>
            <el-table-column prop="count" label="次数" width="90" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { apiStats } from '@/api'
import type { StatsVO } from '@/types/api'

const stats = ref<StatsVO | null>(null)
const loading = ref(false)

const toolCallRows = computed(() =>
  Object.entries(stats.value?.aiToolCalls || {}).map(([tool, count]) => ({ tool, count })),
)
const totalToolCalls = computed(() =>
  Object.values(stats.value?.aiToolCalls || {}).reduce((a, b) => a + b, 0),
)

function toolText(t: string): string {
  return {
    product_search: '检索商品', product_detail: '商品详情', order_query: '查询订单',
    order_create: '创建订单', kb_search: '检索知识库', escalate_to_human: '转人工',
  }[t] || t
}

onMounted(async () => {
  loading.value = true
  try {
    stats.value = await apiStats()
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--el-color-primary);
}

.stat-label {
  color: #909399;
  font-size: 13px;
  margin-top: 4px;
}
</style>
