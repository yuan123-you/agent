<template>
  <section v-if="action" class="order-action-card" :class="`status-${action.status?.toLowerCase()}`">
    <header class="action-head">
      <div class="eyebrow">{{ actionTitle }}</div>
      <el-tag :type="statusMeta.type" size="small">{{ statusMeta.label }}</el-tag>
    </header>

    <template v-if="action.type === 'ORDER_CREATE'">
      <div class="product-line"><strong>{{ action.productName }}</strong><span>× {{ action.quantity }}</span></div>
      <div class="amount"><small>应付金额</small><b>¥{{ money(action.amount) }}</b></div>
      <div class="delivery">
        <div><span>收货人</span>{{ action.receiverName }} · {{ maskPhone(action.receiverPhone) }}</div>
        <div><span>配送至</span>{{ action.receiverAddress }}</div>
      </div>
    </template>
    <template v-else-if="action.type === 'ORDER_CANCEL'">
      <div class="product-line"><strong>订单 {{ action.orderNo }}</strong><span>{{ action.orderStatus || '待支付' }}</span></div>
      <div class="delivery"><div><span>取消原因</span>{{ action.reason }}</div></div>
    </template>
    <template v-else>
      <div class="product-line"><strong>{{ action.productName }}</strong><span>× {{ action.quantity }}</span></div>
      <div class="delivery">
        <div><span>售后类型</span>{{ serviceTypeText }}</div>
        <div><span>问题分类</span>{{ issueCategoryText }}</div>
        <div><span>申请原因</span>{{ action.reason }}</div>
      </div>
      <div class="amount"><small>申请金额</small><b>¥{{ money(action.amount) }}</b></div>
    </template>

    <footer class="action-footer">
      <span v-if="action.status === 'CONFIRMED'" class="order-no">{{ confirmedText }}</span>
      <span v-else-if="action.status === 'CANCELLED'" class="hint">本次操作已撤销，不会执行</span>
      <span v-else-if="action.status === 'EXPIRED'" class="hint">确认请求已失效，请重新发起</span>
      <span v-else class="hint">{{ pendingHint }}</span>

      <div v-if="canDecide" class="action-buttons">
        <el-button :disabled="isDeciding" @click="requestCancel">放弃</el-button>
        <el-button type="primary" :loading="action.status === 'CONFIRMING'" :disabled="isDeciding"
                   @click="action.type === 'ORDER_CREATE' ? openReview() : requestConfirm()">核对并确认</el-button>
      </div>
      <el-button v-else-if="action.status === 'CONFIRMED' && action.orderId" type="primary" plain
                 @click="emit('view-order', action.orderId)">查看订单</el-button>
    </footer>

    <el-dialog v-if="action.type === 'ORDER_CREATE'" v-model="showReview" title="确认收货信息"
               width="min(92vw, 480px)" append-to-body>
      <el-form ref="approvalFormRef" :model="approvalForm" :rules="approvalRules" label-position="top">
        <el-form-item label="收货人" prop="receiverName"><el-input v-model="approvalForm.receiverName" maxlength="50" /></el-form-item>
        <el-form-item label="手机号" prop="receiverPhone"><el-input v-model="approvalForm.receiverPhone" maxlength="11" /></el-form-item>
        <el-form-item label="详细地址" prop="receiverAddress">
          <el-input v-model="approvalForm.receiverAddress" type="textarea" :rows="3" maxlength="255" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showReview = false">返回</el-button>
        <el-button type="primary" :loading="action.status === 'CONFIRMING'" @click="submitApproval">确认创建订单</el-button>
      </template>
    </el-dialog>
  </section>

  <div v-else-if="card" class="tool-card" :class="{ running: card.status === 'running' }">
    <div class="tool-head">
      <el-icon class="tool-icon"><component :is="icon" /></el-icon>
      <span class="tool-label">{{ label }}</span>
      <el-icon v-if="card.status === 'running'" class="is-loading"><Loading /></el-icon>
      <el-icon v-else class="done-icon"><CircleCheck /></el-icon>
    </div>
    <el-collapse v-if="card.result?.preview" class="tool-detail">
      <el-collapse-item title="查看结果" name="detail"><div class="preview">{{ card.result.preview }}</div></el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { CircleCheck, Link, Loading, Search, ShoppingCart, Tickets, User, Goods, Document } from '@element-plus/icons-vue'
import { ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import type { OrderAction, OrderApprovalForm, ToolCard } from '@/types/api'

const props = defineProps<{ card?: ToolCard; action?: OrderAction }>()
const emit = defineEmits<{
  confirm: [actionId: string, approval?: OrderApprovalForm]
  cancel: [actionId: string]
  'view-order': [orderId?: number]
}>()

const META: Record<string, { label: string; icon: unknown }> = {
  product_search: { label: '检索商品', icon: Search },
  product_detail: { label: '查询商品详情', icon: Goods },
  order_query: { label: '查询订单', icon: Tickets },
  order_create: { label: '准备订单', icon: ShoppingCart },
  order_cancel_prepare: { label: '准备取消订单', icon: Tickets },
  after_sale_prepare: { label: '准备售后申请', icon: Document },
  kb_search: { label: '检索知识库', icon: Document },
  escalate_to_human: { label: '转接人工客服', icon: User },
  web_search: { label: '联网搜索', icon: Link },
}

const label = computed(() => props.card ? (META[props.card.tool]?.label || props.card.tool) : '')
const icon = computed(() => props.card ? ((META[props.card.tool]?.icon as any) || Search) : Search)
const actionTitle = computed(() => props.action?.type === 'ORDER_CREATE' ? '待确认下单'
  : props.action?.type === 'ORDER_CANCEL' ? '待确认取消订单' : '待确认售后申请')
const pendingHint = computed(() => props.action?.type === 'ORDER_CREATE' ? '确认后才会正式创建订单'
  : props.action?.type === 'ORDER_CANCEL' ? '确认后才会取消订单' : '确认后才会提交售后申请')
const confirmedText = computed(() => props.action?.type === 'ORDER_CREATE' ? `订单号 ${props.action.orderNo || ''}`
  : props.action?.type === 'ORDER_CANCEL' ? '订单已取消'
    : `售后单 ${props.action?.afterSaleNo || '已提交'}`)
const serviceTypeText = computed(() => ({ RETURN_REFUND: '退货退款', EXCHANGE: '换货',
  REFUND_ONLY: '仅退款', ISSUE_REPORT: '问题反馈' }[props.action?.serviceType || ''] || props.action?.serviceType || ''))
const issueCategoryText = computed(() => ({ PERSONAL: '个人原因', QUALITY: '质量问题',
  MERCHANT: '商家问题', PLATFORM: '平台问题' }[props.action?.issueCategory || ''] || props.action?.issueCategory || ''))
const canDecide = computed(() => props.action?.status === 'PENDING' || props.action?.status === 'FAILED')
const isDeciding = computed(() => props.action?.status === 'CONFIRMING' || props.action?.status === 'CANCELLING')
const showReview = ref(false)
const approvalFormRef = ref<FormInstance>()
const approvalForm = reactive<OrderApprovalForm>({ receiverName: '', receiverPhone: '', receiverAddress: '' })
const approvalRules: FormRules<OrderApprovalForm> = {
  receiverName: [{ required: true, message: '请输入收货人姓名', trigger: 'blur' }],
  receiverPhone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1\d{10}$/, message: '请输入正确的11位手机号', trigger: 'blur' },
  ],
  receiverAddress: [{ required: true, message: '请输入详细收货地址', trigger: 'blur' }],
}
const statusMeta = computed(() => {
  switch (props.action?.status) {
    case 'CONFIRMING': return { label: '执行中', type: 'warning' as const }
    case 'CANCELLING': return { label: '取消中', type: 'warning' as const }
    case 'CONFIRMED': return { label: '已确认', type: 'success' as const }
    case 'CANCELLED': return { label: '已放弃', type: 'info' as const }
    case 'EXPIRED': return { label: '已过期', type: 'info' as const }
    case 'FAILED': return { label: '确认失败，可重试', type: 'danger' as const }
    default: return { label: '请核对', type: 'warning' as const }
  }
})

function openReview() {
  if (!props.action) return
  Object.assign(approvalForm, {
    receiverName: props.action.receiverName || '',
    receiverPhone: props.action.receiverPhone || '',
    receiverAddress: props.action.receiverAddress || '',
  })
  showReview.value = true
}

async function submitApproval() {
  if (!props.action || !await approvalFormRef.value?.validate().catch(() => false)) return
  emit('confirm', props.action.actionId, { ...approvalForm })
  showReview.value = false
}

async function requestConfirm() {
  if (!props.action) return
  try {
    await ElMessageBox.confirm(pendingHint.value, actionTitle.value, {
      type: 'warning', confirmButtonText: '确认执行', cancelButtonText: '返回',
    })
    emit('confirm', props.action.actionId)
  } catch { /* 用户返回继续核对。 */ }
}

async function requestCancel() {
  if (!props.action) return
  try {
    await ElMessageBox.confirm('确定放弃本次待确认操作吗？', '放弃操作', {
      type: 'warning', confirmButtonText: '确定放弃', cancelButtonText: '返回',
    })
    emit('cancel', props.action.actionId)
  } catch {
    // 用户返回继续核对。
  }
}

function money(value?: number) { return Number(value || 0).toFixed(2) }
function maskPhone(phone?: string) { return (phone || '').replace(/(\d{3})\d{4}(\d{4})/, '$1****$2') }
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
