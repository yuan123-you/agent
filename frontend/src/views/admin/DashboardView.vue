<template>
  <div class="page dashboard" v-loading="loading">
    <div class="page-heading">
      <div><h3 class="page-title">数据看板</h3><p>平台今日运营概览</p></div>
      <el-button :loading="loading" @click="loadDashboard">刷新</el-button>
    </div>

    <el-alert v-if="error" title="数据加载失败，请稍后重试" type="error" show-icon :closable="false" class="load-error">
      <template #default><el-button link type="primary" @click="loadDashboard">重新加载</el-button></template>
    </el-alert>

    <section class="summary-grid" aria-label="平台摘要">
      <el-card v-for="card in summaryCards" :key="card.label" shadow="never" class="summary-card">
        <div class="summary-value">{{ card.value }}</div><div class="summary-label">{{ card.label }}</div>
      </el-card>
    </section>

    <section class="panel-grid trend-status">
      <el-card shadow="never"><template #header>近 7 日订单与 GMV</template>
        <div v-if="dashboard.orderTrend.length" class="trend-table">
          <div v-for="point in dashboard.orderTrend" :key="point.date" class="trend-row">
            <span class="trend-date">{{ dateText(point.date) }}</span><div class="bar-track"><div class="bar" :style="{ width: `${trendWidth(point.orderCount)}%` }" /></div>
            <span class="trend-count">{{ point.orderCount }} 单</span><strong class="trend-gmv">{{ formatMoney(point.gmv) }}</strong>
          </div>
        </div>
        <el-empty v-else description="暂无近 7 日订单数据" :image-size="72" />
      </el-card>
      <el-card shadow="never"><template #header>订单状态分布</template>
        <div v-if="dashboard.orderStatusDistribution.length" class="status-list">
          <div v-for="item in dashboard.orderStatusDistribution" :key="item.status" class="status-row"><el-tag :type="statusType(item.status)">{{ orderStatusText(item.status) }}</el-tag><b>{{ item.count }}</b></div>
        </div>
        <el-empty v-else description="暂无订单状态数据" :image-size="72" />
      </el-card>
    </section>

    <section class="panel-grid operations-quality">
      <el-card shadow="never"><template #header>待人工处理</template>
        <div class="waiting"><span>{{ dashboard.operations.waitingHumanConversationCount }}</span><small>个会话正在等待人工接入</small></div>
      </el-card>
      <el-card shadow="never"><template #header>AI 服务质量（今日）</template>
        <div class="quality-grid"><div v-for="metric in qualityMetrics" :key="metric.label"><strong>{{ metric.value }}</strong><span>{{ metric.label }}</span></div></div>
      </el-card>
    </section>

    <section class="panel-grid ranks">
      <el-card shadow="never"><template #header>热门问题（今日）</template>
        <el-table v-if="dashboard.topQuestions.length" :data="dashboard.topQuestions" size="small"><el-table-column type="index" width="52" /><el-table-column prop="name" label="问题" show-overflow-tooltip /><el-table-column prop="count" label="次数" width="90" /></el-table>
        <el-empty v-else description="暂无热门问题" :image-size="72" />
      </el-card>
      <el-card shadow="never"><template #header>工具排行（今日）</template>
        <el-table v-if="dashboard.toolCalls.length" :data="dashboard.toolCalls" size="small"><el-table-column type="index" width="52" /><el-table-column label="工具" show-overflow-tooltip><template #default="{ row }">{{ toolText(row.name) }}</template></el-table-column><el-table-column prop="count" label="调用次数" width="100" /></el-table>
        <el-empty v-else description="暂无工具调用" :image-size="72" />
      </el-card>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { apiAdminDashboard } from '@/api'
import { formatMoney, formatPercent, normalizeDashboard, orderStatusText, toolText } from './dashboard'
import type { NormalizedDashboard } from './dashboard'

const dashboard = ref<NormalizedDashboard>(normalizeDashboard())
const loading = ref(false)
const error = ref(false)

const summaryCards = computed(() => [
  { label: '平台用户', value: dashboard.value.summary.userCount }, { label: '商家数量', value: dashboard.value.summary.merchantCount },
  { label: '在售商品', value: dashboard.value.summary.onSaleProductCount }, { label: '今日订单', value: dashboard.value.summary.todayOrderCount },
  { label: '今日 GMV', value: formatMoney(dashboard.value.summary.todayGmv) }, { label: '今日会话', value: dashboard.value.summary.todayConversationCount },
])
const qualityMetrics = computed(() => [
  { label: '回复成功率', value: formatPercent(dashboard.value.aiQuality.replySuccessRate) }, { label: '工具调用率', value: formatPercent(dashboard.value.aiQuality.toolCallRatio) },
  { label: '平均响应时延', value: `${dashboard.value.aiQuality.avgLatencyMs} ms` }, { label: '总 Token', value: dashboard.value.aiQuality.totalTokens.toLocaleString() },
])
const maxOrderCount = computed(() => Math.max(1, ...dashboard.value.orderTrend.map(point => point.orderCount)))

function trendWidth(count: number): number { return Math.max(4, count / maxOrderCount.value * 100) }
function dateText(date: string): string { return date ? date.slice(5).replace('-', '/') : '-' }
function statusType(status: string): 'warning' | 'primary' | 'success' | 'info' | 'danger' {
  return { PENDING_PAYMENT: 'warning', PAID: 'primary', SHIPPED: 'success', DELIVERED: 'success', CANCELLED: 'info' }[status] || 'info'
}
async function loadDashboard() {
  loading.value = true; error.value = false
  try { dashboard.value = normalizeDashboard(await apiAdminDashboard()) } catch { error.value = true } finally { loading.value = false }
}
onMounted(loadDashboard)
</script>

<style scoped>
.dashboard { min-width: 0; }.page-heading { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }.page-title { margin:0; }.page-heading p { margin:5px 0 0; color:#909399; font-size:13px; }.load-error { margin-bottom:16px; }.summary-grid { display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:16px; margin-bottom:16px; }.summary-card { text-align:center; }.summary-value { color:var(--el-color-primary); font-size:25px; font-weight:700; word-break:break-word; }.summary-label { color:#909399; font-size:13px; margin-top:6px; }.panel-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; margin-bottom:16px; }.trend-table,.status-list { min-height:210px; }.trend-row { display:grid; grid-template-columns:48px minmax(60px,1fr) 48px 86px; gap:8px; align-items:center; padding:9px 0; font-size:13px; }.bar-track { overflow:hidden; height:10px; border-radius:8px; background:#edf2fc; }.bar { height:100%; background:var(--el-color-primary); border-radius:8px; }.trend-row strong { text-align:right; }.status-row { display:flex; justify-content:space-between; align-items:center; padding:12px 0; border-bottom:1px solid var(--el-border-color-lighter); }.waiting { min-height:210px; display:flex; flex-direction:column; align-items:center; justify-content:center; }.waiting span { color:var(--el-color-warning); font-size:42px; font-weight:700; }.waiting small { color:#909399; margin-top:8px; }.quality-grid { min-height:210px; display:grid; grid-template-columns:repeat(2,1fr); gap:1px; background:var(--el-border-color-lighter); }.quality-grid div { display:flex; flex-direction:column; justify-content:center; align-items:center; gap:8px; background:#fff; }.quality-grid strong { font-size:21px; }.quality-grid span { color:#909399; font-size:13px; }.ranks :deep(.el-card__body) { padding-top:8px; } @media (max-width:1100px) { .summary-grid { grid-template-columns:repeat(3,1fr); } } @media (max-width:760px) { .summary-grid,.panel-grid { grid-template-columns:1fr; }.page-heading { align-items:flex-start; flex-wrap:wrap; gap:8px; }.trend-row { grid-template-columns:1fr auto auto; }.bar-track { grid-column:1 / -1; grid-row:2; }.trend-gmv { min-width:76px; }.quality-grid { grid-template-columns:1fr; }.quality-grid div { min-height:90px; } }
</style>
