<template>
  <section class="trace-console">
    <header class="page-heading">
      <div><span class="eyebrow">AI OPERATIONS</span><h1>AI 链路</h1><p>从用户问题到最终回答，逐步检查 Agent 与 RAG 的真实执行数据。</p></div>
      <button class="button" :disabled="loading" @click="load(page)">刷新列表</button>
    </header>
    <div class="privacy-note">仅管理员可见 · 数据经脱敏与长度限制 · 不采集模型内部思维链 · 历史请求无法补录执行明细</div>

    <!-- AI 客服标准评测基准卡片 -->
    <section v-if="benchmarkData && (benchmarkData.overall_score != null || benchmarkData.overallScore != null)" class="benchmark-card" aria-label="标准客服评测">
      <div class="benchmark-header">
        <div>
          <span class="eyebrow">STANDARDIZED BENCHMARK</span>
          <div class="benchmark-title-wrap">
            <h2>AI 客服标准评测基准</h2>
            <span class="benchmark-badge">{{ benchmarkData.overall_score ?? benchmarkData.overallScore }} 分</span>
            <span class="benchmark-rate">通过率 {{ Math.round(((benchmarkData.overall_pass_rate ?? benchmarkData.overallPassRate) || 0) * 100) }}%</span>
            <span class="benchmark-meta">{{ benchmarkData.total_cases ?? benchmarkData.totalCases }} 题标准用例 · 覆盖 6 大电商客服维度</span>
          </div>
        </div>
        <button class="button small" @click="showBenchmarkDetails = !showBenchmarkDetails">
          {{ showBenchmarkDetails ? '收起维度雷达' : '展开场景雷达' }}
        </button>
      </div>
      <div v-if="showBenchmarkDetails" class="benchmark-grid">
        <div v-for="sc in (benchmarkData.scorecards || [])" :key="sc.category" class="sc-item">
          <div class="sc-name">{{ sc.category_name || sc.categoryName }}</div>
          <div class="sc-score">{{ sc.average_score ?? sc.averageScore }} <small>/ 100</small></div>
          <div class="sc-meta">通过率 {{ Math.round((sc.pass_rate ?? sc.passRate) * 100) }}% ({{ sc.passed_cases ?? sc.passedCases }}/{{ sc.total_cases ?? sc.totalCases }})</div>
        </div>
      </div>
    </section>
    <section class="list-panel" aria-label="链路记录">
      <form class="filters" @submit.prevent="load(1)">
        <label>问题关键词<input v-model="query" name="query" placeholder="搜索用户问题" maxlength="80" /></label>
        <label>会话 ID<input v-model="conversationId" name="conversationId" inputmode="numeric" placeholder="全部会话" /></label>
        <label>执行状态<select v-model="status"><option value="">全部状态</option><option v-for="value in statuses" :key="value" :value="value">{{ statusLabel(value) }}</option></select></label>
        <button class="button primary" :disabled="loading">查询</button>
      </form>
      <div v-if="listError" class="notice error" role="alert">{{ listError }}</div>
      <div v-if="loading" class="notice" role="status">正在加载链路记录…</div>
      <div v-else-if="!rows.length && !listError" class="empty-state"><strong>暂无链路记录</strong><p>启用此功能后发送一条新的 AI 消息，即可在这里查看执行过程。</p></div>
      <div v-else-if="rows.length" class="table-scroll">
        <table><thead><tr><th>时间 / 链路 ID</th><th class="question-col">用户问题</th><th>状态</th><th>总耗时</th><th>LLM 调用</th><th>已上报 Token</th><th>步骤</th><th><span class="sr-only">操作</span></th></tr></thead>
          <tbody><tr v-for="row in rows" :key="row.traceId" :class="{ selected: selectedId === row.traceId }">
            <td><span>{{ row.createdAt.replace('T', ' ') }}</span><small class="mono">{{ row.traceId.slice(0, 12) }}</small></td>
            <td class="question-cell"><strong>{{ row.inputPreview || '（空问题）' }}</strong><small>会话 {{ row.conversationId }} · 用户 {{ row.userId }}</small></td>
            <td><span class="status" :data-status="row.status">{{ statusLabel(row.status) }}</span></td><td class="mono">{{ duration(row.durationMs) }}</td><td class="mono">{{ row.modelCalls }}</td><td class="mono">{{ row.totalTokens ?? '未返回' }}</td><td class="mono">{{ row.stageCount }}</td>
            <td><button class="text-button" @click="selectTrace(row.traceId)">查看链路</button></td>
          </tr></tbody>
        </table>
      </div>
      <footer class="pagination"><span>共 {{ total }} 轮请求</span><div><button class="button small" :disabled="loading || page <= 1" @click="load(page - 1)">上一页</button><span>{{ page }} / {{ Math.max(1, Math.ceil(total / 20)) }}</span><button class="button small" :disabled="loading || page * 20 >= total" @click="load(page + 1)">下一页</button></div></footer>
    </section>

    <section v-if="selectedId" class="detail-panel" aria-label="链路详情">
      <header class="detail-heading"><div><h2>执行详情</h2><span class="mono trace-id">{{ selectedId }}</span></div><button class="button" :disabled="detailLoading" @click="selectTrace(selectedId)">刷新详情</button></header>
      <div v-if="detailLoading" class="notice" role="status">正在加载执行步骤…</div>
      <div v-else-if="detailError" class="notice error" role="alert">{{ detailError }}</div>
      <template v-else-if="detail">
        <div class="turn-summary"><p>{{ detail.inputPreview }}</p><div><span class="status" :data-status="detail.status">{{ statusLabel(detail.status) }}</span><span>{{ duration(detail.durationMs) }}</span><span>{{ detail.modelCalls }} 次 LLM 调用</span><span>{{ detail.totalTokens ?? '未返回' }} 已上报 Token</span></div></div>
        <div v-if="detail.status === 'RUNNING'" class="notice">执行中，完成后刷新查看明细；若连接异常中止，请检查服务状态。</div>
        <div v-if="detail.error" class="notice error">{{ detail.error }}</div>
        <div v-if="detail.omittedStages" class="notice">达到采集上限，另有 {{ detail.omittedStages }} 个步骤未保留。</div>
        <div v-if="!detail.stages.length" class="notice">未收到 AI 执行明细。请求可能在模型服务连接前失败，或仍在执行。</div>
        <div v-else class="execution-grid">
          <aside class="timeline"><div class="timeline-header"><h3>执行时间线</h3><select v-model="kind" aria-label="筛选步骤类型"><option value="">全部类型</option><option v-for="item in kinds" :key="item" :value="item">{{ kindLabel(item) }}</option></select></div>
            <button v-for="step in filteredStages" :key="step.id" class="step" :class="{ active: stageId === step.id }" :data-stage-id="step.id" @click="stageId = step.id">
              <span class="step-dot" :data-status="step.status" /><span class="step-body"><span class="step-title">{{ stageLabel(step.name) }}</span><span class="step-meta">{{ kindLabel(step.kind) }} · +{{ duration(step.startMs) }} <span>{{ duration(step.durationMs) }}</span></span></span>
            </button>
            <p v-if="!filteredStages.length" class="notice">此链路没有该类型步骤。</p>
          </aside>
          <article v-if="selectedStage" class="stage-detail"><header><div><span class="eyebrow">{{ kindLabel(selectedStage.kind) }}</span><h3>{{ stageLabel(selectedStage.name) }}</h3><code>{{ selectedStage.name }}</code></div><span class="status" :data-status="selectedStage.status">{{ statusLabel(selectedStage.status) }}</span></header>
            <dl class="stage-metrics"><div><dt>步骤耗时</dt><dd>{{ duration(selectedStage.durationMs) }}</dd></div><div v-if="selectedStage.model"><dt>模型</dt><dd>{{ selectedStage.model }}</dd></div><div v-if="selectedStage.usage"><dt>Token 用量</dt><dd>{{ selectedStage.usage.total_tokens ?? '未返回' }}</dd></div></dl>
            <p v-if="selectedStage.error" class="notice error">{{ selectedStage.error }}</p>
            <h4>输入</h4><pre>{{ pretty(selectedStage.input) }}</pre><h4>输出</h4><pre>{{ pretty(selectedStage.output) }}</pre>
            <p class="data-note">内容按原始结构展示。检索步骤可检查候选、来源与各阶段得分；“未返回”不等于零，引用存在也不代表语义必然正确。</p>
          </article>
        </div>
      </template>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { apiAiTrace, apiAiTraces, apiAiBenchmark } from '@/api/aiTraces'
import type { AiTraceSummary, AiTraceDetail } from '@/types/aiTrace'
const rows = ref<AiTraceSummary[]>([]), detail = ref<AiTraceDetail | null>(null)
const query = ref(''), conversationId = ref(''), status = ref(''), kind = ref('')
const page = ref(1), total = ref(0), loading = ref(false), detailLoading = ref(false)
const listError = ref(''), detailError = ref(''), selectedId = ref(''), stageId = ref('')
const benchmarkData = ref<any>(null), showBenchmarkDetails = ref(false)
let listRequest = 0, detailRequest = 0
const statuses = ['RUNNING', 'SUCCESS', 'DEGRADED', 'FAILED', 'CANCELLED']
const kinds = computed(() => [...new Set(detail.value?.stages.map(s => s.kind) || [])])
const filteredStages = computed(() => (detail.value?.stages || []).filter(s => !kind.value || s.kind === kind.value))
const selectedStage = computed(() => detail.value?.stages.find(s => s.id === stageId.value))
watch(kind, () => { if (!filteredStages.value.some(s => s.id === stageId.value)) stageId.value = filteredStages.value[0]?.id || '' })
const statusLabel = (value: string) => ({ RUNNING:'执行中', SUCCESS:'成功', DEGRADED:'降级', FAILED:'失败', CANCELLED:'已中止', SKIPPED:'已跳过' }[value] || value)
const kindLabel = (value: string) => ({ node:'图节点', model:'模型', tool:'工具', retrieval:'RAG 检索', guard:'输出校验', context:'上下文', embedding:'向量化', memory:'记忆', stage:'阶段' }[value] || value)
const names: Record<string, string> = { 'context.assemble':'装配会话上下文', intent_router:'意图路由', agent:'业务 Agent', tools:'执行工具', small_talk:'对话回复', web_answer:'联网回答', escalate_node:'转人工', finalize_without_tools:'强制收敛', 'rag.embedding':'查询向量化', 'rag.milvus':'Milvus 向量搜索', 'rag.current_version':'校验当前文档版本', 'rag.dense':'向量召回', 'rag.bm25':'BM25 召回', 'rag.metadata_filter':'元数据范围过滤', 'rag.rrf':'RRF 融合', 'rag.rerank':'候选重排', 'rag.answerability':'可回答性与证据', 'output.validate':'引用与链接校验', 'memory.identity':'保存显式称呼', 'memory.preference':'后台偏好记忆', 'memory.extract':'提取偏好与事实', 'memory.persist_identity':'写入称呼记忆', 'memory.persist_preferences':'写入偏好记忆' }
const stageLabel = (name: string) => names[name] || name
const duration = (ms?: number | null) => ms == null ? '—' : ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${Math.round(ms * 100) / 100} ms`
const pretty = (value: unknown) => value == null ? '未采集 / 无数据' : JSON.stringify(value, null, 2)
async function load(target = 1) {
  const value = conversationId.value.trim()
  if (value && (!/^\d+$/.test(value) || !Number.isSafeInteger(Number(value)) || Number(value) <= 0)) { listError.value = '请输入有效的会话 ID'; return }
  const version = ++listRequest; loading.value = true; listError.value = ''
  try {
    const data = await apiAiTraces({ page:target, size:20, query:query.value.trim() || undefined, status:status.value || undefined, conversationId:value ? Number(value) : undefined })
    if (version !== listRequest) return
    rows.value = data.records; total.value = data.total; page.value = target
  } catch { if (version === listRequest) { rows.value = []; total.value = 0; listError.value = '链路列表加载失败，请检查服务后重试。' } }
  finally { if (version === listRequest) loading.value = false }
}
async function selectTrace(id: string) {
  const version = ++detailRequest; selectedId.value = id; detailLoading.value = true; detailError.value = ''; detail.value = null; kind.value = ''
  try {
    const data = await apiAiTrace(id)
    if (version !== detailRequest) return
    detail.value = data; stageId.value = data.stages[0]?.id || ''
  } catch { if (version === detailRequest) detailError.value = '链路详情加载失败，请稍后重试。' }
  finally { if (version === detailRequest) detailLoading.value = false }
}
onMounted(() => {
  load()
  apiAiBenchmark().then(d => { if (d && (d.overall_score != null || d.overallScore != null)) benchmarkData.value = d }).catch(() => {})
})
onBeforeUnmount(() => { listRequest++; detailRequest++ })
</script>

<style scoped>
.trace-console { max-width:1540px; margin:0 auto; color:#253246; }
.page-heading,.detail-heading { display:flex; align-items:center; justify-content:space-between; gap:20px; margin-bottom:18px; }
.eyebrow { color:#6d7d92; font-size:11px; letter-spacing:.12em; font-weight:700; }
h1 { margin:5px 0 8px; font-size:27px; letter-spacing:-.04em; } .page-heading p { margin:0; color:#67758a; font-size:13px; }
h2 { margin:0 0 6px; font-size:18px; } h3 { margin:5px 0 8px; font-size:15px; } h4 { font-size:12px; color:#64748b; margin:18px 0 8px; }
.privacy-note { margin-bottom:18px; color:#67758a; font-size:12px; line-height:1.7; }
.list-panel,.detail-panel { background:#fff; border:1px solid #dde3eb; border-radius:8px; overflow:hidden; }
.detail-panel { margin-top:22px; padding:22px; }
.filters { display:flex; align-items:flex-end; gap:14px; padding:20px; border-bottom:1px solid #e8edf3; flex-wrap:wrap; }
.filters label { display:grid; gap:7px; font-size:12px; color:#65748a; } input,select { background:#fff; color:#263449; border:1px solid #d8e0e9; border-radius:5px; padding:9px 10px; min-height:36px; font:inherit; }
input:focus,select:focus { outline:2px solid #b4ceef; outline-offset:1px; } input[name=query] { width:250px; } input[name=conversationId] { width:145px; }
.button { background:#fff; color:#34445a; border:1px solid #d6dee8; border-radius:5px; padding:9px 14px; font-size:12px; cursor:pointer; white-space:nowrap; }
.button.primary { background:#2563b9; border-color:#2563b9; color:white; } button:disabled { opacity:.45; cursor:not-allowed; } .button.small { padding:6px 10px; }
.text-button { padding:6px 0; background:none; border:0; color:#2563b9; cursor:pointer; font-size:12px; white-space:nowrap; }
.table-scroll { overflow-x:auto; position:relative; } table { border-collapse:collapse; width:100%; font-size:12px; text-align:left; } th { background:#f8fafc; color:#718096; font-weight:500; padding:13px 17px; white-space:nowrap; } td { padding:15px 17px; border-top:1px solid #edf0f5; white-space:nowrap; }
.question-col { width:32%; } .question-cell { white-space:normal; min-width:180px; max-width:400px; } .question-cell strong { font-weight:500; overflow-wrap:anywhere; line-height:1.6; } td small { display:block; margin-top:6px; color:#8995a5; font-size:11px; } tr.selected { background:#f4f8fd; }
.mono,code,pre { font-family:Consolas,'SFMono-Regular',monospace; } .status { display:inline-block; padding:3px 7px; border-radius:4px; font-size:11px; color:#47617f; background:#edf2f8; white-space:nowrap; }
.status[data-status=SUCCESS] { color:#227354; background:#eaf5ef; } .status[data-status=FAILED],.status[data-status=CANCELLED] { color:#a74040; background:#fbeeee; } .status[data-status=DEGRADED] { color:#8c671b; background:#fbf4e4; } .status[data-status=SKIPPED] { color:#758195; background:#f0f2f5; }
.pagination,.pagination>div { display:flex; align-items:center; justify-content:space-between; gap:14px; } .pagination { padding:14px 20px; border-top:1px solid #e8edf3; color:#758195; font-size:12px; }
.notice { padding:16px 20px; font-size:12px; color:#758195; line-height:1.7; } .notice.error { color:#a13b3b; background:#fff6f6; } .empty-state { padding:52px 20px; text-align:center; color:#68778b; font-size:13px; } .empty-state strong { color:#34445a; }
.trace-id { color:#8a95a6; font-size:11px; overflow-wrap:anywhere; } .turn-summary { border-block:1px solid #e7ecf2; padding:16px 0; margin-bottom:20px; } .turn-summary p { font-size:14px; margin:0 0 12px; } .turn-summary>div { display:flex; gap:20px; align-items:center; color:#6c7a8e; font-size:12px; flex-wrap:wrap; }
.execution-grid { display:grid; grid-template-columns:300px minmax(0,1fr); gap:24px; } .timeline { border-right:1px solid #e7ecf2; padding-right:20px; } .timeline-header { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:16px; } .timeline-header select { width:106px; padding:6px; font-size:11px; }
.step { display:flex; align-items:flex-start; gap:10px; width:100%; text-align:left; padding:13px 10px; border:0; border-left:2px solid #e3e9f1; background:white; cursor:pointer; } .step.active { background:#f0f6fd; border-left-color:#3478c8; } .step-dot { width:7px; height:7px; border-radius:50%; background:#a6b3c3; margin-top:5px; flex-shrink:0; } .step-dot[data-status=SUCCESS] { background:#4a9a76; } .step-dot[data-status=FAILED] { background:#bf6666; } .step-body { width:100%; min-width:0; } .step-title { font-size:12px; color:#33445a; display:block; overflow-wrap:anywhere; } .step-meta { display:flex; gap:8px; margin-top:6px; font-size:10px; color:#8a97a8; } .step-meta>span { margin-left:auto; }
.stage-detail { min-width:0; } .stage-detail>header { display:flex; align-items:flex-start; justify-content:space-between; gap:14px; } .stage-detail code { color:#94a0af; font-size:11px; overflow-wrap:anywhere; } .stage-metrics { display:flex; gap:30px; margin:22px 0; flex-wrap:wrap; } dt { color:#8995a6; font-size:11px; } dd { margin:6px 0 0; color:#34445a; font-size:13px; }
pre { background:#f7f9fc; border:1px solid #e6ebf2; border-radius:5px; margin:0; padding:16px; font-size:11px; line-height:1.8; max-height:420px; overflow:auto; white-space:pre-wrap; overflow-wrap:anywhere; color:#42536b; } .data-note { margin-top:16px; color:#8a95a6; font-size:11px; line-height:1.8; } .sr-only { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0,0,0,0); }
@media(max-width:1000px) { .execution-grid { grid-template-columns:240px minmax(0,1fr); gap:16px; } .timeline { padding-right:12px; } }
@media(max-width:700px) { .page-heading { align-items:flex-start; } h1 { font-size:23px; } .filters { padding:14px; gap:12px; } input[name=query] { width:100%; } .filters label:first-child { width:100%; } .detail-panel { padding:15px; } .execution-grid { grid-template-columns:1fr; } .timeline { border-right:0; border-bottom:1px solid #e7ecf2; padding:0 0 16px; max-height:300px; overflow:auto; } .detail-heading { align-items:flex-start; } .trace-id { max-width:220px; display:block; } }

.benchmark-card { background:#fff; border:1px solid #dce4ee; border-radius:8px; padding:18px 20px; margin-bottom:20px; box-shadow:0 1px 3px rgba(0,0,0,0.02); }
.benchmark-header { display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap; }
.benchmark-title-wrap { display:flex; align-items:center; gap:12px; margin-top:4px; flex-wrap:wrap; }
.benchmark-title-wrap h2 { margin:0; font-size:16px; font-weight:700; color:#223249; }
.benchmark-badge { display:inline-block; padding:3px 9px; border-radius:12px; font-size:12px; font-weight:700; color:#1e6245; background:#e8f5ee; border:1px solid #c9ebd8; }
.benchmark-rate { font-size:12px; color:#2b7156; font-weight:600; }
.benchmark-meta { font-size:12px; color:#788698; }
.benchmark-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:12px; margin-top:16px; padding-top:16px; border-top:1px dashed #e2e8f0; }
.sc-item { background:#f8fafc; border:1px solid #e7ecf2; border-radius:6px; padding:12px; }
.sc-name { font-size:12px; font-weight:600; color:#334458; margin-bottom:4px; }
.sc-score { font-size:18px; font-weight:700; color:#2563b9; }
.sc-score small { font-size:11px; font-weight:normal; color:#8795a5; }
.sc-meta { font-size:11px; color:#718295; margin-top:4px; }
</style>
