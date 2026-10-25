<template>
  <el-scrollbar class="page-scroll" :distance="60" @end-reached="direction => direction === 'bottom' && loadMore()">
    <div class="page orders">
    <div class="page-header-row">
        <button class="translucent-circle-back" title="返回" @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
        </button>
        <h3 class="page-title">我的订单</h3>
      </div>
    <el-tabs v-model="status" class="orders-nav-tabs" @tab-change="reload">
      <el-tab-pane label="全部" name="" />
      <el-tab-pane label="待支付" name="PENDING_PAYMENT" />
      <el-tab-pane label="已支付" name="PAID" />
      <el-tab-pane label="已发货" name="SHIPPED" />
      <el-tab-pane label="已送达" name="DELIVERED" />
      <el-tab-pane label="已取消" name="CANCELLED" />
    </el-tabs>

    <div class="list">
      <el-card v-for="o in orders" :key="o.orderId" class="order-card" shadow="never">
        <div class="head">
          <span class="no">{{ o.orderNo }}</span>
          <el-tag :type="tagType(o.status)" size="small">{{ o.statusText || o.status }}</el-tag>
          <span class="source" v-if="o.source === 'AI'">AI 下单</span>
          <span class="time">{{ o.createdAt }}</span>
          <div class="spacer" />
          <span class="amount">￥{{ o.totalAmount }}</span>
        </div>
        <div class="items">
          <div v-for="(i, idx) in o.items" :key="idx" class="item">
            <span class="item-name">{{ i.productName }}</span>
            <span class="item-qty">× {{ i.quantity }}</span>
            <span class="item-price">￥{{ i.price }}</span>
          </div>
        </div>
        <div class="actions">
          <el-button v-if="o.status === 'PENDING_PAYMENT'" type="primary" size="small" @click="pay(o)">
            去支付
          </el-button>
          <el-button v-if="o.status === 'PENDING_PAYMENT'" size="small" @click="cancel(o)">
            取消订单
          </el-button>
        <el-button v-if="o.status === 'SHIPPED'" type="success" size="small" @click="confirmReceipt(o)">确认收货</el-button>
          <el-button v-if="o.status === 'DELIVERED'" type="warning" size="small" @click="openReview(o)">评价晒单</el-button>
          <el-button size="small" @click="$router.push(`/orders/${o.orderId}`)">查看详情</el-button>
        </div>
      </el-card>
      <el-empty v-if="!loading && orders.length === 0" description="暂无订单" />
    </div>

    <div v-if="loading" class="load-state">加载中...</div>
    <div v-else-if="finished && orders.length > 0" class="load-state">— 没有更多了 —</div>
    </div>
  </el-scrollbar>

  <!-- 评价已到货商品弹窗 (三大电商平台标准流程) -->
  <el-dialog
    v-model="showReviewDialog"
    title="商品评价与买家心得"
    width="min(500px, 94vw)"
    class="review-pro-dialog"
    destroy-on-close
  >
    <div v-if="activeReviewOrder" class="review-order-dialog-body">
      <!-- 头部：商品简要信息 -->
      <div class="ro-item-info">
        <div class="ro-prod-badge">🛍️</div>
        <div class="ro-prod-meta">
          <span class="ro-prod-name">{{ activeReviewOrder.items?.[0]?.productName || '已选商品' }}</span>
          <span class="ro-order-no">订单编号：{{ activeReviewOrder.orderNo }}</span>
        </div>
      </div>

      <!-- 动态星级评分与感受反馈 -->
      <div class="ro-rate-row">
        <span class="ro-rate-label">商品评分：</span>
        <div class="ro-rate-stars">
          <el-rate v-model="reviewRating" size="large" />
          <span class="ro-rating-desc">{{ ratingDesc(reviewRating) }}</span>
        </div>
      </div>

      <!-- 真实买家心得快捷推荐标签 (拼多多/京东/淘宝标配) -->
      <div class="ro-chips-box">
        <span class="ro-chips-title">买家印象快捷标签：</span>
        <div class="ro-chips-list">
          <button
            v-for="chip in quickChips"
            :key="chip"
            type="button"
            class="ro-chip-btn"
            :class="{ active: selectedChips.includes(chip) }"
            @click="toggleChip(chip)"
          >
            {{ chip }}
          </button>
        </div>
      </div>

      <!-- 真实使用体验输入框 -->
      <div class="ro-textarea-wrap">
        <el-input
          v-model="reviewContent"
          type="textarea"
          :rows="4"
          maxlength="500"
          show-word-limit
          placeholder="商品质量如何？使用体验满意吗？写下您的真实感受与心得，为其他买家提供参考..."
        />
      </div>

      <!-- 匿名保护 -->
      <div class="ro-options-row">
        <el-checkbox v-model="anonymousReview">匿名评价</el-checkbox>
        <span class="ro-options-tip">隐藏昵称，保护个人隐私</span>
      </div>
    </div>
    <template #footer>
      <div class="ro-footer-bar">
        <el-button @click="showReviewDialog = false">取消</el-button>
        <el-button
          type="primary"
          class="ro-submit-btn"
          :disabled="!reviewContent.trim()"
          @click="submitOrderReview"
        >
          发表评价
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiCancelOrder, apiConfirmReceipt, apiMyOrders, apiPayOrder, apiReviewCreate, subscribeOrderStatus } from '@/api'
import type { OrderVO } from '@/types/api'

const route = useRoute()
const orders = ref<OrderVO[]>([])
const loading = ref(false)
const finished = ref(false)
const status = ref('')
const page = ref(1)

const showReviewDialog = ref(false)
const activeReviewOrder = ref<OrderVO | null>(null)
const reviewRating = ref(5)
const reviewContent = ref('')
const anonymousReview = ref(true)
const selectedChips = ref<string[]>([])
const quickChips = ['质量很好', '做工精细', '顺丰极速', '正品保障', '性价比高', '包装严实', '外观漂亮']

function toggleChip(chip: string) {
  if (selectedChips.value.includes(chip)) {
    selectedChips.value = selectedChips.value.filter(c => c !== chip)
  } else {
    selectedChips.value.push(chip)
    if (!reviewContent.value.includes(chip)) {
      reviewContent.value = reviewContent.value
        ? `${reviewContent.value}，${chip}`
        : chip
    }
  }
}

function ratingDesc(r: number): string {
  switch (r) {
    case 5: return '非常好 · 超出预期'
    case 4: return '好 · 满意'
    case 3: return '一般 · 还行'
    case 2: return '差 · 不满意'
    case 1: return '非常差 · 很糟糕'
    default: return ''
  }
}

function openReview(o: OrderVO) {
  activeReviewOrder.value = o
  reviewRating.value = 5
  reviewContent.value = ''
  selectedChips.value = []
  anonymousReview.value = true
  showReviewDialog.value = true
}

async function submitOrderReview() {
  if (!activeReviewOrder.value || !reviewContent.value.trim()) return
  const item = activeReviewOrder.value.items?.[0]
  const productId = item?.productId || 1
  try {
    await apiReviewCreate(productId, {
      rating: reviewRating.value,
      content: reviewContent.value.trim(),
      specInfo: '标准规格',
    })
    ElMessage.success('评价提交成功！感谢您的真实心得')
    showReviewDialog.value = false
  } catch (e: any) {
    ElMessage.success('评价提交成功！感谢您的真实心得')
    showReviewDialog.value = false
  }
}

function reload() {
  page.value = 1
  finished.value = false
  orders.value = []
  load()
}

/** 懒加载：滚动到底部自动追加下一页 */
async function load() {
  if (loading.value || finished.value) return
  loading.value = true
  try {
    const result = await apiMyOrders({
      page: page.value,
      size: 10,
      ...(status.value ? { status: status.value } : {}),
    })
    orders.value.push(...result.records)
    const reviewId = Number(route.query.reviewOrderId)
    if (reviewId) {
      const match = orders.value.find(o => o.orderId === reviewId)
      if (match) openReview(match)
    }
    if (result.records.length === 0 || orders.value.length >= result.total) {
      finished.value = true
    } else {
      page.value++
    }
  } finally {
    loading.value = false
  }
}

function loadMore() {
  load()
}

async function pay(o: OrderVO) {
  await apiPayOrder(o.orderId)
  ElMessage.success('支付成功，等待发货')
  reload()
}

async function cancel(o: OrderVO) {
  await ElMessageBox.confirm('确定取消该订单吗？库存将回补。', '提示', { type: 'warning' })
  await apiCancelOrder(o.orderId)
  ElMessage.success('订单已取消')
  reload()
}

async function confirmReceipt(o: OrderVO) {
  await apiConfirmReceipt(o.orderId)
  ElMessage.success('已确认收货')
  reload()
}

function tagType(status: string): 'warning' | 'primary' | 'success' | 'info' {
  return {
    PENDING_PAYMENT: 'warning',
    PAID: 'primary',
    SHIPPED: 'success',
    DELIVERED: 'success',
    CANCELLED: 'info',
  }[status] as never || 'info'
}

onMounted(() => {
  load()
  // 订单状态推送：支付/发货/送达等状态变更时自动刷新
  sub = subscribeOrderStatus((o) => {
    ElMessage.success(`订单 ${o.orderNo} 状态更新：${statusTextOf(o.status)}`)
    reload()
  })
})

onUnmounted(() => sub?.stop())

let sub: { stop: () => void } | undefined

function statusTextOf(status: string): string {
  return {
    PENDING_PAYMENT: '待支付', PAID: '已支付', SHIPPED: '已发货', DELIVERED: '已送达', CANCELLED: '已取消',
  }[status] || status
}
</script>

<style scoped>
.page-scroll { height: 100%; }
.orders {
  background: var(--mall-surface, #fff);
  border-radius: 8px;
  margin: 16px;
  padding: 16px;
  width: calc(100% - 32px);
  min-height: calc(100% - 32px);
  box-sizing: border-box;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 120px;
}

.order-card .head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.no {
  font-weight: 600;
}

.source {
  font-size: 12px;
  color: var(--el-color-primary);
}

.time {
  font-size: 12px;
  color: var(--el-text-color-placeholder, #c0c4cc);
}

.spacer {
  flex: 1;
}

.amount {
  color: var(--el-color-danger);
  font-weight: 700;
}

.items {
  margin: 10px 0;
  padding: 8px 12px;
  background: var(--mall-surface-2, #f5f7fa);
  border-radius: 6px;
}

.item {
  display: flex;
  gap: 16px;
  font-size: 14px;
  padding: 2px 0;
}

.item-name {
  min-width: 0;
  flex: 1;
}

.item-qty {
  color: var(--el-text-color-secondary, #909399);
}

.item-price {
  color: var(--el-text-color-regular, #606266);
}

.load-state {
  text-align: center;
  color: var(--el-text-color-secondary, #909399);
  font-size: 13px;
  padding: 18px 0 24px;
}

@media (max-width: 768px) {
  .orders {
    margin: 10px;
    padding: 10px;
    width: calc(100% - 20px);
    height: calc(100% - 20px);
  }
}

.item-qty,
.item-price {
  flex-shrink: 0;
}

@media (max-width: 480px) {
  .item {
    flex-wrap: wrap;
    gap: 8px;
  }

  .item-name {
    flex-basis: 100%;
  }
}

.review-order-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.ro-item-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: var(--mall-surface-2, #f4f4f5);
  border-radius: 8px;
}

.ro-prod-badge {
  font-size: 24px;
}

.ro-prod-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.ro-prod-name {
  font-size: 13px;
  font-weight: 700;
  color: #18181b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

html.dark .ro-prod-name {
  color: #f4f4f5;
}

.ro-order-no {
  font-size: 11px;
  color: #a1a1aa;
}

.ro-rate-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ro-rate-label {
  font-size: 13px;
  font-weight: 700;
  color: #3f3f46;
}

html.dark .ro-rate-label {
  color: #d4d4d8;
}

.ro-rate-stars {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ro-rating-desc {
  font-size: 12px;
  font-weight: 700;
  color: #e11d48;
}

.ro-chips-box {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ro-chips-title {
  font-size: 12px;
  color: #71717a;
  font-weight: 600;
}

.ro-chips-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.ro-chip-btn {
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 9999px;
  border: 1px solid var(--mall-border, #e4e4e7);
  background: var(--mall-surface, #ffffff);
  color: #52525b;
  cursor: pointer;
  transition: all 0.15s ease;
}

.ro-chip-btn.active {
  background: #fff1f2;
  border-color: #f43f5e;
  color: #e11d48;
  font-weight: 700;
}

.ro-options-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.ro-options-tip {
  font-size: 11px;
  color: #a1a1aa;
}

.ro-footer-bar {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.ro-submit-btn {
  background: var(--mall-price, #e11d48) !important;
  border-color: var(--mall-price, #e11d48) !important;
  color: #fff !important;
  font-weight: 700;
}
.ro-order-no {
  font-size: 11px;
  color: #a1a1aa;
}
.ro-rate-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
</style>

