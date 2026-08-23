<template>
  <section v-if="action" class="order-action-card" :class="`status-${action.status?.toLowerCase()}`">
    <header class="action-head">
      <div class="eyebrow">待确认下单</div>
      <el-tag :type="statusMeta.type" size="small">{{ statusMeta.label }}</el-tag>
    </header>

    <div class="product-line">
      <strong>{{ action.productName }}</strong>
      <span>× {{ action.quantity }}</span>
    </div>
    <div class="amount">
      <small>应付金额</small>
      <b>¥{{ money(action.amount) }}</b>
    </div>
    <div class="delivery">
      <div><span>收货人</span>{{ action.receiverName }} · {{ maskPhone(action.receiverPhone) }}</div>
      <div><span>配送至</span>{{ action.receiverAddress }}</div>
    </div>

    <footer class="action-footer">
      <span v-if="action.status === 'CONFIRMED'" class="order-no">订单号 {{ action.orderNo }}</span>
      <span v-else-if="action.status === 'CANCELLED'" class="hint">本次下单已取消，不会创建订单</span>
      <span v-else-if="action.status === 'EXPIRED'" class="hint">确认请求已失效，请重新发起下单</span>
      <span v-else class="hint">确认后才会正式创建订单</span>

      <div v-if="canDecide" class="action-buttons">
        <el-button :disabled="action.status === 'CONFIRMING'" @click="emit('cancel', action.actionId)">取消</el-button>
        <el-button
          type="primary"
          :loading="action.status === 'CONFIRMING'"
          :disabled="action.status === 'CONFIRMING'"
          @click="emit('confirm', action.actionId)"
        >确认下单</el-button>
      </div>
      <el-button v-else-if="action.status === 'CONFIRMED'" type="primary" plain @click="emit('view-order', action.orderId)">
        查看订单
      </el-button>
    </footer>
  </section>

  <div v-else-if="card" class="tool-card" :class="{ running: card.status === 'running' }">
    <div class="tool-head">
      <el-icon class="tool-icon"><component :is="icon" /></el-icon>
      <span class="tool-label">{{ label }}</span>
      <el-icon v-if="card.status === 'running'" class="is-loading"><Loading /></el-icon>
      <el-icon v-else class="done-icon"><CircleCheck /></el-icon>
    </div>
    <el-collapse v-if="card.result?.preview" class="tool-detail">
      <el-collapse-item title="查看结果" name="detail">
        <div class="preview">{{ card.result.preview }}</div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CircleCheck, Link, Loading, Search, ShoppingCart, Tickets, User, Goods, Document } from '@element-plus/icons-vue'
import type { OrderAction, ToolCard } from '@/types/api'

const props = defineProps<{ card?: ToolCard; action?: OrderAction }>()
const emit = defineEmits<{
  confirm: [actionId: string]
  cancel: [actionId: string]
  'view-order': [orderId?: number]
}>()

const META: Record<string, { label: string; icon: unknown }> = {
  product_search: { label: '检索商品', icon: Search },
  product_detail: { label: '查询商品详情', icon: Goods },
  order_query: { label: '查询订单', icon: Tickets },
  order_create: { label: '准备订单', icon: ShoppingCart },
  kb_search: { label: '检索知识库', icon: Document },
  escalate_to_human: { label: '转接人工客服', icon: User },
  web_search: { label: '联网搜索', icon: Link },
}

const label = computed(() => props.card ? (META[props.card.tool]?.label || props.card.tool) : '')
const icon = computed(() => props.card ? ((META[props.card.tool]?.icon as any) || Search) : Search)
const canDecide = computed(() => props.action?.status === 'PENDING' || props.action?.status === 'FAILED')
const statusMeta = computed(() => {
  switch (props.action?.status) {
    case 'CONFIRMING': return { label: '创建中', type: 'warning' as const }
    case 'CONFIRMED': return { label: '已创建订单', type: 'success' as const }
    case 'CANCELLED': return { label: '已取消', type: 'info' as const }
    case 'EXPIRED': return { label: '已过期', type: 'info' as const }
    case 'FAILED': return { label: '确认失败，可重试', type: 'danger' as const }
    default: return { label: '请核对', type: 'warning' as const }
  }
})

function money(value: number) { return Number(value).toFixed(2) }
function maskPhone(phone: string) { return phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2') }
</script>

<style scoped>
.tool-card {
  max-width: 420px;
  padding: 6px 10px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  background: #f4f6fa;
  color: #606266;
  font-size: 12px;
}
.tool-card.running { border-color: var(--el-color-primary-light-7); }
.tool-head { display: flex; align-items: center; gap: 6px; }
.tool-icon { color: var(--el-color-primary); }
.tool-label { font-weight: 500; }
.done-icon { margin-left: auto; color: var(--el-color-success); }
.tool-detail { margin-top: 4px; border: none; }
.tool-detail :deep(.el-collapse-item__header) {
  height: 24px; border: none; background: transparent; color: #909399; font-size: 12px; line-height: 24px;
}
.tool-detail :deep(.el-collapse-item__wrap) { border: none; background: transparent; }
.preview { max-height: 120px; overflow-y: auto; color: #909399; white-space: pre-wrap; word-break: break-all; }

.order-action-card {
  width: min(430px, 100%);
  box-sizing: border-box;
  padding: 16px;
  border: 1px solid #f1d8b5;
  border-radius: 14px;
  background: linear-gradient(145deg, #fffdf8, #fff8ed);
  box-shadow: 0 8px 24px rgba(111, 74, 30, .08);
}
.order-action-card.status-confirmed { border-color: #bfe3cd; background: #f6fff9; }
.order-action-card.status-cancelled,
.order-action-card.status-expired { border-color: #dcdfe6; background: #fafafa; }
.action-head, .action-footer, .product-line, .amount { display: flex; align-items: center; }
.action-head { justify-content: space-between; margin-bottom: 14px; }
.eyebrow { color: #9a5b16; font-size: 12px; font-weight: 700; letter-spacing: .12em; }
.product-line { justify-content: space-between; color: #2f2923; }
.product-line span { color: #7e746a; }
.amount { justify-content: space-between; margin: 12px 0; padding: 12px 0; border-block: 1px dashed #ead7bd; }
.amount small { color: #827568; }
.amount b { color: #d9541e; font-size: 22px; }
.delivery { display: grid; gap: 7px; color: #4f4841; font-size: 13px; line-height: 1.5; }
.delivery span { display: inline-block; width: 52px; color: #988a7c; }
.action-footer { justify-content: space-between; gap: 12px; margin-top: 16px; }
.action-buttons { display: flex; flex-shrink: 0; gap: 8px; }
.hint, .order-no { color: #8b7e71; font-size: 12px; }
@media (max-width: 520px) {
  .action-footer { align-items: stretch; flex-direction: column; }
  .action-buttons { justify-content: flex-end; }
}
</style>
