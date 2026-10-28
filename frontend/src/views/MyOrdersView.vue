<template>
  <el-scrollbar class="page-scroll" :distance="60" @end-reached="direction => direction === 'bottom' && !loadFailed && loadMore()">
    <div class="page orders">
      <header class="orders-header">
        <div class="orders-heading">
          <button type="button" class="orders-back" title="返回" aria-label="返回上一页" @click="goBack"><el-icon><ArrowLeft /></el-icon></button>
          <h1 class="orders-title">我的订单</h1>
        </div>
        <div class="orders-header-links"><button type="button" class="continue-shopping" @click="router.push('/after-sales')">退款 / 售后</button><button type="button" class="continue-shopping" @click="router.push('/products')">继续购物 <el-icon><ArrowRight /></el-icon></button></div>
      </header>

      <section class="orders-filters" aria-label="订单状态筛选">
        <el-tabs v-model="status" class="orders-nav-tabs" @tab-change="reload">
          <el-tab-pane label="全部" name="" />
          <el-tab-pane label="待付款" name="PENDING_PAYMENT" />
          <el-tab-pane label="待发货" name="PAID" />
          <el-tab-pane label="待收货" name="SHIPPED" />
          <el-tab-pane label="待评价" name="PENDING_REVIEW" />
          <el-tab-pane label="已完成" name="DELIVERED" />
          <el-tab-pane label="已取消" name="CANCELLED" />
        </el-tabs>
      </section>
      <div class="orders-list-meta">
        <span>{{ status ? statusTextOf(status) + '订单' : '全部订单' }}</span>
        <span v-if="!loading && !loadFailed" class="order-count">{{ status === 'PENDING_REVIEW' && !finished ? '已找到' : '共' }} {{ total }} 笔</span>
      </div>

      <div class="list" aria-label="订单列表" :aria-busy="loading">
        <article v-for="o in orders" :key="o.orderId" class="order-card" :aria-label="'订单 ' + o.orderNo">
          <header class="order-card-header">
            <div class="order-store"><span class="store-icon"><el-icon><Shop /></el-icon></span><strong>AI Mall</strong><span class="store-caption">商城订单</span><span v-if="o.source === 'AI'" class="source">AI 下单</span></div>
            <span class="order-status" :class="'status-' + o.status.toLowerCase()">{{ statusTextOf(o.status, o.statusText) }}</span>
          </header>
          <div class="items">
            <div v-for="(i, idx) in o.items" :key="i.orderItemId || idx" class="item">
              <button type="button" class="item-product-link" :disabled="!i.productId" :aria-label="'查看商品：' + i.productName" @click="router.push(`/products/${i.productId}`)">
                <el-image :src="i.productImage" :alt="i.productName" fit="cover" loading="lazy" class="item-image">
                  <template #error><span class="item-image-fallback"><el-icon><Box /></el-icon><span>暂无图片</span></span></template>
                </el-image>
                <span class="item-info"><span class="item-name">{{ i.productName }}</span></span>
              </button>
              <div class="item-pricing"><span class="item-price">¥{{ money(i.price) }}</span><span class="item-qty">×{{ i.quantity }}</span></div>
            </div>
            <p v-if="!o.items.length" class="items-unavailable">商品信息暂不可用，请查看订单详情</p>
          </div>
          <div v-if="o.status === 'SHIPPED' || o.status === 'PAID'" class="order-status-hint">
            <el-icon><component :is="statusIcon(o.status)" /></el-icon><span>{{ orderHint(o) }}</span>
            <button v-if="o.status === 'SHIPPED'" type="button" class="logistics-link" aria-label="查看物流" @click="router.push(`/orders/${o.orderId}`)"><el-icon><ArrowRight /></el-icon></button>
          </div>
          <footer class="order-card-footer">
            <div class="order-total">
              <span class="order-quantity">共 {{ itemCount(o) }} 件商品</span>
              <span class="amount-label">{{ o.status === 'PENDING_PAYMENT' ? '需付款' : o.status === 'CANCELLED' ? '合计' : '实付款' }}</span>
              <span class="amount" :class="{ 'amount-pending': o.status === 'PENDING_PAYMENT' }"><span>¥</span>{{ money(o.totalAmount) }}</span><span v-if="o.refundedAmount" class="order-refund-amount">已退款（模拟）¥{{ money(o.refundedAmount) }}</span>
            </div>
            <div class="order-footer-actions">
              <button type="button" class="order-support" aria-label="联系客服" @click="router.push('/assistant')"><el-icon><Headset /></el-icon><span>客服</span></button>
              <AfterSaleOrderActions :order="o" @changed="reload" />
              <div class="actions">
                <el-button v-if="o.status === 'PENDING_PAYMENT'" class="cancel-order" @click="cancel(o)">取消订单</el-button>
                <el-button class="order-detail-action" @click="router.push(`/orders/${o.orderId}`)">查看详情</el-button>
                <el-button v-if="repeatProductId(o)" class="order-repurchase" @click="buyAgain(o)">再次购买</el-button>
                <el-button v-if="o.status === 'PENDING_PAYMENT'" class="order-primary-action" @click="pay(o)">去支付</el-button>
                <el-button v-if="o.status === 'SHIPPED'" class="order-primary-action" @click="confirmReceipt(o)">确认收货</el-button>
                <el-button v-if="reviewableItems(o).length" class="order-primary-action" @click="openReview(o)">评价晒单</el-button>
                <span v-else-if="o.status === 'DELIVERED' && o.items.length && o.items.every(i => i.reviewed)" class="reviewed-label">已评价</span>
              </div>
            </div>
          </footer>
          <div class="order-meta"><span class="no">订单号 {{ o.orderNo }}</span><time v-if="o.createdAt" class="time">{{ formatOrderTime(o.createdAt) }}</time></div>
        </article>
      </div>

      <LoadingState v-if="loading" variant="list" :count="3" />
      <div v-else-if="loadFailed" class="orders-error" role="alert">
        <el-icon><RefreshRight /></el-icon><h2>订单加载失败</h2><p>请检查网络后重试，你的订单不会丢失</p><el-button @click="loadMore">重新加载</el-button>
      </div>
      <div v-else-if="!orders.length" class="orders-empty">
        <div class="empty-order-icon"><el-icon><ShoppingBag /></el-icon></div>
        <h2>{{ status ? '暂无' + statusTextOf(status) + '订单' : '暂无订单' }}</h2>
        <p>{{ status ? '可以切换其他状态，查看你的订单' : '还没有订单，去看看心仪的好物吧' }}</p><el-button @click="router.push('/products')">去逛逛</el-button>
      </div>
      <div v-else-if="finished" class="load-state"><span />没有更多订单了<span /></div>
      <div v-else class="load-state"><el-button text @click="loadMore">加载更多订单</el-button></div>
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
          <span class="ro-prod-name">{{ activeReviewItem?.productName || '已选商品' }}</span>
          <span class="ro-order-no">订单编号：{{ activeReviewOrder.orderNo }}</span>
        </div>
      </div>

      <el-select v-if="reviewableItems(activeReviewOrder).length > 1" v-model="activeReviewItemId" aria-label="选择评价商品">
        <el-option v-for="item in reviewableItems(activeReviewOrder)" :key="item.orderItemId" :label="item.productName" :value="item.orderItemId" />
      </el-select>

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

    </div>
    <template #footer>
      <div class="ro-footer-bar">
        <el-button @click="showReviewDialog = false">取消</el-button>
        <el-button
          type="primary"
          class="ro-submit-btn"
          :disabled="!reviewContent.trim() || !activeReviewItem || reviewRating < 1"
          :loading="reviewSubmitting"
          @click="submitOrderReview"
        >
          发表评价
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import AfterSaleOrderActions from '@/components/order/AfterSaleOrderActions.vue'
import LoadingState from '@/components/common/LoadingState.vue'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ArrowLeft, ArrowRight, Box, Clock, Van, CircleCheck, Close, RefreshRight, Shop, Headset, ShoppingBag } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiCancelOrder, apiConfirmReceipt, apiMyOrders, apiOrderDetail, apiPayOrder, apiReviewCreate, subscribeOrderStatus } from '@/api'
import type { OrderVO } from '@/types/api'

const route = useRoute()
const router = useRouter()
function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/')
}
let generation = 0
let mounted = false
let pendingReview: { id: number; detail?: Promise<OrderVO> } | undefined
const reviewedProducts = new Set<number>()
const orders = ref<OrderVO[]>([])
const loading = ref(false)
const finished = ref(false)
const status = ref('')
const page = ref(1)
const total = ref(0)
const loadFailed = ref(false)
let fetchedOrders = 0

const showReviewDialog = ref(false)
const activeReviewOrder = ref<OrderVO | null>(null)
const reviewRating = ref(5)
const reviewContent = ref('')
const activeReviewItemId = ref<number>()
const reviewSubmitting = ref(false)
const activeReviewItem = computed(() => activeReviewOrder.value
  ? reviewableItems(activeReviewOrder.value).find(i => i.orderItemId === activeReviewItemId.value)
  : undefined)
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

function reviewableItems(o: OrderVO) {
  return o.status === 'DELIVERED'
    ? o.items.filter(i => i.canReview === true && !i.reviewed && i.productId > 0 && !!i.orderItemId)
    : []
}

function openReview(o: OrderVO) {
  const item = reviewableItems(o)[0]
  if (!item) return
  activeReviewOrder.value = o
  activeReviewItemId.value = item.orderItemId
  reviewRating.value = 5
  reviewContent.value = ''
  selectedChips.value = []
  showReviewDialog.value = true
}

async function submitOrderReview() {
  const item = activeReviewItem.value
  if (reviewSubmitting.value || !item || !reviewContent.value.trim() || reviewRating.value < 1) return
  reviewSubmitting.value = true
  try {
    await apiReviewCreate(item.productId, {
      orderItemId: item.orderItemId,
      rating: reviewRating.value,
      content: reviewContent.value.trim(),
    })
    reviewedProducts.add(item.productId)
    // A list request started before this commit may still return an older snapshot.
    for (const o of [...orders.value, ...(activeReviewOrder.value ? [activeReviewOrder.value] : [])]) {
      applyReviewedProducts(o)
    }
    if (status.value === 'PENDING_REVIEW') {
      orders.value = orders.value.filter(order => reviewableItems(order).length > 0)
      total.value = orders.value.length
      if (!orders.value.length && !finished.value) void load()
    }
    ElMessage.success('评价提交成功！感谢您的真实心得')
    showReviewDialog.value = false
  } catch {
    // The API layer reports the real error. Keep the draft and never claim success.
  } finally {
    reviewSubmitting.value = false
  }
}

watch(() => route.query.reviewOrderId, (value) => {
  if (value === undefined) return
  const id = Number(value)
  pendingReview = Number.isSafeInteger(id) && id > 0 ? { id } : undefined
  const { reviewOrderId: _, ...query } = route.query
  void router.replace({ query }).catch(() => {})
  if (mounted) void openRequestedReview(generation)
}, { immediate: true })

function applyReviewedProducts(o: OrderVO) {
  for (const item of o.items) {
    if (reviewedProducts.has(item.productId)) { item.reviewed = true; item.canReview = false }
  }
}

async function openRequestedReview(requestGeneration: number) {
  const intent = pendingReview
  if (!intent) return
  try {
    const target = orders.value.find(o => o.orderId === intent.id)
      || await (intent.detail ??= apiOrderDetail(intent.id))
    if (!mounted || requestGeneration !== generation || intent !== pendingReview) return
    pendingReview = undefined
    applyReviewedProducts(target)
    openReview(target)
  } catch {
    if (intent === pendingReview) pendingReview = undefined
    // Authorization/not-found failures are already reported by the API layer.
  }
}

function reload() {
  generation++
  page.value = 1
  finished.value = false
  orders.value = []
  loading.value = false
  total.value = 0
  fetchedOrders = 0
  loadFailed.value = false
  void load()
}

/** Ignore stale requests after filter changes, status pushes or navigation. */
async function load() {
  if (loading.value || finished.value) return
  const requestGeneration = generation
  loading.value = true
  loadFailed.value = false
  try {
    const reviewOnly = status.value === 'PENDING_REVIEW'
    let added: number
    do {
      const result = await apiMyOrders({
        page: page.value,
        size: 10,
        ...(status.value ? { status: reviewOnly ? 'DELIVERED' : status.value } : {}),
      })
      if (!mounted || requestGeneration !== generation) return
      result.records.forEach(applyReviewedProducts)
      fetchedOrders += result.records.length
      const records = reviewOnly ? result.records.filter(order => reviewableItems(order).length > 0) : result.records
      added = records.length
      orders.value.push(...records)
      total.value = reviewOnly ? orders.value.length : result.total
      if (result.records.length === 0 || fetchedOrders >= result.total) finished.value = true
      else page.value++
      // A reviewed-only page must not masquerade as an empty result while later pages remain.
    } while (reviewOnly && added === 0 && !finished.value)
    await openRequestedReview(requestGeneration)
  } catch {
    if (mounted && requestGeneration === generation) loadFailed.value = true
    // The API reports the error; keep the current page available for retry.
  } finally {
    if (requestGeneration === generation) loading.value = false
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

function repeatProductId(o: OrderVO): number | undefined {
  return ['DELIVERED', 'CANCELLED'].includes(o.status) && o.items.length === 1 && o.items[0].productId > 0
    ? o.items[0].productId : undefined
}

function buyAgain(o: OrderVO) {
  const id = repeatProductId(o)
  if (id) void router.push(`/products/${id}`)
}

function money(value: number): string {
  return Number(value).toFixed(2)
}

function itemCount(o: OrderVO): number {
  return o.items.reduce((count, item) => count + item.quantity, 0)
}

function formatOrderTime(value: string): string {
  return value.replace('T', ' ').slice(0, 16)
}

function statusIcon(status: string) {
  const icons: Record<string, typeof Box> = { PENDING_PAYMENT: Clock, PAID: Box, SHIPPED: Van, DELIVERED: CircleCheck, CANCELLED: Close }
  return icons[status] || Box
}

function orderHint(o: OrderVO): string {
  switch (o.status) {
    case 'PENDING_PAYMENT': return '订单已提交，请完成付款'
    case 'PAID': return '付款成功，等待商家发货'
    case 'SHIPPED': return o.deliveryCompany || o.logisticsNo
      ? `商品已发出 · ${[o.deliveryCompany, o.logisticsNo].filter(Boolean).join(' · ')}`
      : '商品已发出，可在订单详情中查看物流信息'
    case 'DELIVERED': return reviewableItems(o).length ? '订单已完成，分享你的真实使用体验吧' : '订单已完成，感谢你的信任'
    case 'CANCELLED': return '订单已取消，可以继续选购其他商品'
    default: return '查看详情，了解订单最新进展'
  }
}

onMounted(() => {
  mounted = true
  void load()
  // 订单状态推送：支付/发货/送达等状态变更时自动刷新
  sub = subscribeOrderStatus((o) => {
    ElMessage.success(`订单 ${o.orderNo} 状态更新：${statusTextOf(o.status)}`)
    reload()
  })
})

onUnmounted(() => { mounted = false; generation++; sub?.stop() })

let sub: { stop: () => void } | undefined

function statusTextOf(status: string, fallback?: string): string {
  const labels: Record<string, string> = {
    PENDING_PAYMENT: '待付款', PAID: '待发货', SHIPPED: '待收货', PENDING_REVIEW: '待评价', DELIVERED: '已完成', CANCELLED: '已取消', REFUNDED: '已退款',
  }
  return labels[status] || fallback || status
}
</script>

<style scoped>
.page-scroll { height: 100%; background: var(--mall-surface-2); }
.orders { --order-accent: var(--mall-price); --order-muted: var(--el-text-color-secondary); --order-ink: var(--el-text-color-primary); max-width: 1120px; margin: 0 auto; padding: 24px 24px 40px; min-height: 100%; color: var(--order-ink); }
.orders-header, .orders-heading, .continue-shopping { display: flex; align-items: center; }
.orders-header { justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.orders-heading { gap: 12px; }
.orders-header-links { display:flex;align-items:center;gap:16px; }
.orders-back { display: grid; place-items: center; width: 32px; height: 32px; border: 0; border-radius: 50%; background: var(--mall-surface); color: inherit; cursor: pointer; }
.orders-title { margin: 0; font-size: 23px; font-weight: 650; line-height: 1.4; }
.continue-shopping { gap: 5px; padding: 5px 0; border: 0; background: transparent; color: var(--el-text-color-regular); font: inherit; font-size: 12px; cursor: pointer; white-space: nowrap; }
.orders-filters { position: sticky; top: 0; z-index: 3; padding: 0 20px; background: var(--mall-surface); border-radius: 10px; }
.orders-nav-tabs :deep(.el-tabs__header) { margin: 0; }
.orders-nav-tabs :deep(.el-tabs__nav-wrap::after) { display: none; }
.orders-nav-tabs :deep(.el-tabs__item) { height: 52px; padding: 0 25px; color: var(--el-text-color-regular); font-size: 14px; }
.orders-nav-tabs :deep(.el-tabs__item.is-active) { color: var(--order-accent); font-weight: 650; }
.orders-nav-tabs :deep(.el-tabs__active-bar) { height: 3px; border-radius: 2px; background: var(--order-accent); }
.orders-list-meta { display: flex; justify-content: space-between; margin: 17px 2px 12px; color: var(--order-muted); font-size: 12px; }
.order-count { font-size: 11px; }
.list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; align-items: start; }
.order-card { min-width: 0; padding: 0 18px; overflow: hidden; border-radius: 12px; background: var(--mall-surface); }
.order-card-header { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 15px 0 13px; }
.order-store { display: flex; align-items: center; gap: 7px; min-width: 0; }
.store-icon { display: grid; place-items: center; width: 23px; height: 23px; border-radius: 6px; background: var(--mall-price-bg); color: var(--order-accent); font-size: 15px; }
.order-store strong { font-size: 13px; font-weight: 650; white-space: nowrap; }
.store-caption { color: var(--order-muted); font-size: 10px; white-space: nowrap; }
.source { margin-left: 2px; padding: 2px 5px; border-radius: 3px; background: var(--mall-surface-2); color: var(--order-muted); font-size: 10px; white-space: nowrap; }
.order-status { flex-shrink: 0; font-size: 12px; font-weight: 500; color: var(--order-accent); }
.status-delivered, .status-cancelled, .status-refunded { color: var(--order-muted); }
.items { padding-bottom: 8px; }
.item { display: flex; align-items: flex-start; gap: 14px; min-width: 0; }
.item + .item { margin-top: 14px; }
.item-product-link { display: flex; align-items: flex-start; gap: 13px; min-width: 0; flex: 1; padding: 0; border: 0; background: transparent; color: inherit; font: inherit; text-align: left; cursor: pointer; }
.item-product-link:disabled { cursor: default; }
.item-image { width: 94px; height: 94px; flex-shrink: 0; border-radius: 7px; background: var(--mall-surface-2); }
.item-image-fallback { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; height: 100%; gap: 5px; color: var(--order-muted); font-size: 10px; }
.item-image-fallback .el-icon { font-size: 26px; }
.item-info { min-width: 0; flex: 1; padding-top: 2px; }
.item-name { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere; font-size: 14px; font-weight: 500; line-height: 1.6; }
.item-pricing { display: flex; flex-direction: column; align-items: flex-end; flex-shrink: 0; gap: 7px; padding-top: 5px; font-variant-numeric: tabular-nums; }
.item-price { font-size: 14px; }
.item-qty { font-size: 12px; color: var(--order-muted); }
.order-status-hint { display: flex; align-items: center; gap: 7px; min-height: 32px; margin: 3px 0 7px; padding: 7px 9px; border-radius: 5px; background: var(--mall-surface-2); color: var(--el-text-color-regular); font-size: 11px; line-height: 1.5; }
.order-status-hint > .el-icon { flex-shrink: 0; color: var(--order-muted); font-size: 14px; }
.order-status-hint > span { min-width: 0; flex: 1; overflow-wrap: anywhere; }
.logistics-link { display: grid; place-items: center; flex-shrink: 0; width: 23px; height: 23px; padding: 0; border: 0; border-radius: 3px; background: transparent; color: var(--order-muted); cursor: pointer; }
.order-card-footer { padding-top: 5px; }
.order-total { display: flex; align-items: baseline; justify-content: flex-end; flex-wrap: wrap; gap: 5px; margin: 0 0 13px; }
.order-quantity { margin-right: 5px; color: var(--order-muted); font-size: 11px; }
.amount-label { font-size: 12px; }
.amount { font-size: 21px; font-weight: 650; font-variant-numeric: tabular-nums; line-height: 1.25; letter-spacing: -.4px; }
.amount > span { margin-right: 2px; font-size: 13px; font-weight: 500; }
.order-refund-amount { width:100%;text-align:right;font-size:11px;color:var(--order-muted); }
.amount-pending { color: var(--order-accent); }
.order-footer-actions { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; padding-bottom: 14px; }
.order-support { display: inline-flex; align-items: center; gap: 4px; flex-shrink: 0; padding: 5px 0; border: 0; background: transparent; color: var(--order-muted); font: inherit; font-size: 11px; cursor: pointer; }
.order-support .el-icon { font-size: 15px; }
.actions { margin-left:auto; display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 7px; min-width: 0; }
.actions :deep(.el-button) { margin: 0; min-width: 78px; height: 31px; padding: 0 13px; border: 1px solid var(--mall-border); border-radius: 20px; background: transparent; color: var(--el-text-color-regular); font-size: 12px; }
.actions :deep(.order-primary-action) { border-color: var(--order-accent); background: var(--order-accent); color: var(--mall-surface); font-weight: 600; }
.actions :deep(.order-repurchase) { border-color: var(--order-accent); color: var(--order-accent); }
.actions :deep(.order-primary-action:hover) { filter: brightness(.94); }
.reviewed-label { order: -1; font-size: 11px; color: var(--order-muted); }
.order-meta { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 4px 10px; padding: 10px 0; border-top: 1px solid var(--mall-border-light); color: var(--order-muted); font-size: 10px; font-variant-numeric: tabular-nums; }
.no { min-width: 0; overflow-wrap: anywhere; }
.time { flex-shrink: 0; }
.items-unavailable { margin: 18px 0; color: var(--order-muted); font-size: 12px; }
.orders-empty, .orders-error { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 340px; text-align: center; }
.empty-order-icon { display: grid; place-items: center; width: 76px; height: 76px; border-radius: 50%; background: var(--mall-surface); color: var(--order-muted); font-size: 32px; }
.orders-error > .el-icon { color: var(--order-muted); font-size: 32px; }
.orders-empty h2, .orders-error h2 { margin: 15px 0 0; font-size: 16px; font-weight: 600; }
.orders-empty p, .orders-error p { margin: 10px 0 22px; color: var(--order-muted); font-size: 12px; }
.orders-empty :deep(.el-button), .orders-error :deep(.el-button) { padding: 0 30px; border-radius: 20px; border-color: var(--order-accent); color: var(--order-accent); background: var(--mall-surface); }
.load-state { display: flex; align-items: center; justify-content: center; gap: 12px; padding: 26px 0 8px; color: var(--order-muted); font-size: 11px; }
.load-state > span { width: 28px; height: 1px; background: var(--mall-border); }
.orders-back:hover, .continue-shopping:hover, .order-support:hover, .item-product-link:not(:disabled):hover .item-name { color: var(--order-accent); }
.orders button:focus-visible { outline: 2px solid var(--el-color-primary); outline-offset: 3px; }
@media (max-width: 900px) {
  .orders { max-width: 660px; padding: 18px 16px 36px; }
  .list { grid-template-columns: minmax(0, 1fr); gap: 12px; }
  .orders-nav-tabs :deep(.el-tabs__item) { padding: 0 21px; }
}
@media (max-width: 600px) {
  .orders { padding: 12px 10px 28px; }
  .orders-header { margin: 0 3px 12px; }
  .orders-heading { gap: 8px; }
  .orders-title { font-size: 20px; }
  .orders-back { width: 30px; height: 30px; }
  .continue-shopping { font-size: 11px; }
  .orders-filters { padding: 0 12px; border-radius: 8px; }
  .orders-nav-tabs :deep(.el-tabs__item) { height: 45px; padding: 0 13px; font-size: 13px; }
  .orders-list-meta { margin: 12px 4px 9px; font-size: 11px; }
  .order-card { padding: 0 13px; border-radius: 10px; }
  .order-card-header { padding: 12px 0 11px; }
  .order-store { gap: 6px; }
  .store-caption { display: none; }
  .store-icon { width: 20px; height: 20px; font-size: 13px; }
  .order-store strong { font-size: 12px; }
  .order-status { font-size: 12px; }
  .item { gap: 10px; }
  .item-product-link { gap: 10px; }
  .item-image { width: 82px; height: 82px; border-radius: 6px; }
  .item-name { font-size: 13px; line-height: 1.6; }
  .item-price { font-size: 13px; }
  .item-qty { font-size: 11px; }
  .order-card-footer { padding-top: 3px; }
  .order-total { margin-bottom: 11px; }
  .amount { font-size: 20px; }
  .order-footer-actions { padding-bottom: 12px; }
  .actions { gap: 6px; }
  .actions :deep(.el-button) { min-width: 66px; height: 30px; padding: 0 10px; font-size: 12px; }
  .order-meta { padding: 8px 0; font-size: 10px; }
}
@media (max-width: 360px) {
  .order-support > span { display: none; }
  .order-support .el-icon { font-size: 18px; }
  .item-image { width: 76px; height: 76px; }
  .actions :deep(.el-button) { min-width: 62px; padding: 0 8px; }
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
