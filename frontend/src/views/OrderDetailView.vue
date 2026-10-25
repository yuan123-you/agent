<template>
  <div v-if="order" class="page detail-page">
    <div class="page-header-row">
      <button class="translucent-circle-back" title="返回" @click="goBack">
        <el-icon><ArrowLeft /></el-icon>
      </button>
      <h3 class="page-title">订单详情</h3>
    </div>

    <!-- 顶栏状态与支付成功横幅 (对标拼多多/京东下单完成页) -->
    <div class="order-status-banner" :class="order.status.toLowerCase()">
      <div class="osb-left">
        <div class="osb-title">{{ statusBannerTitle }}</div>
        <div class="osb-sub">{{ statusBannerSub }}</div>
      </div>
      <div class="osb-actions">
        <el-button v-if="order.status === 'PENDING_PAYMENT'" type="danger" size="small" round @click="pay">
          去支付
        </el-button>
        <el-button v-if="order.status === 'PAID'" type="primary" size="small" round :loading="shippingSimulating" @click="handleSimulateShip">
          🚀 模拟商家发货
        </el-button>
        <el-button v-if="order.status === 'SHIPPED'" type="success" size="small" round @click="confirmReceipt">
          确认收货
        </el-button>
        <el-button v-if="order.status === 'DELIVERED'" type="warning" size="small" round @click="goToReview">
          评价晒单
        </el-button>
      </div>
    </div>

    <!-- 顺丰物流轨迹动态卡片 -->
    <div v-if="order.status === 'SHIPPED' || order.status === 'DELIVERED'" class="logistics-card mall-card">
      <div class="lc-head">
        <span class="lc-company">📦 {{ order.deliveryCompany || '顺丰速运' }}</span>
        <span class="lc-no">运单号：{{ order.logisticsNo || 'SF1982839210' }}</span>
      </div>
      <div class="lc-timeline">
        <div v-if="order.status === 'DELIVERED'" class="lc-node active">
          <div class="lcn-dot" />
          <div class="lcn-body">
            <div class="lcn-text">【已签收】快件已安全送达收件人，感谢您选择官方旗舰店！</div>
            <div class="lcn-time">{{ order.deliveredAt || '今日 14:20' }}</div>
          </div>
        </div>
        <div class="lc-node" :class="{ active: order.status === 'SHIPPED' }">
          <div class="lcn-dot" />
          <div class="lcn-body">
            <div class="lcn-text">【派送中】顺丰速运 快递员正在为您派送，请保持电话畅通</div>
            <div class="lcn-time">预计今日送达</div>
          </div>
        </div>
        <div class="lc-node">
          <div class="lcn-dot" />
          <div class="lcn-body">
            <div class="lcn-text">【运输中】快件已离开 [北京顺义智能总仓] 陆运枢纽，正发往目的地城市</div>
            <div class="lcn-time">{{ order.shippedAt || '今日 09:15' }}</div>
          </div>
        </div>
        <div class="lc-node">
          <div class="lcn-dot" />
          <div class="lcn-body">
            <div class="lcn-text">【已揽收】顺丰速运 智能分拣仓已完成打包出库与面单打印</div>
            <div class="lcn-time">{{ order.shippedAt || '今日 08:30' }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 收货地址 -->
    <div class="address-info-card mall-card">
      <div class="aic-icon">📍</div>
      <div class="aic-meta">
        <div class="aic-receiver">
          <span class="name">{{ order.receiverName }}</span>
          <span class="phone">{{ order.receiverPhone }}</span>
        </div>
        <div class="aic-address">{{ order.receiverAddress }}</div>
      </div>
    </div>

    <!-- 商品明细卡片 -->
    <div class="items-card mall-card">
      <div class="card-caption">商品清单</div>
      <div v-for="(i, idx) in order.items" :key="idx" class="order-item-row" @click="i.productId && $router.push(`/products/${i.productId}`)">
        <div class="oi-pic-box">
          <el-image :src="i.productImage" fit="cover" class="oi-pic">
            <template #error><div class="oi-fb">🛍️</div></template>
          </el-image>
        </div>
        <div class="oi-info">
          <div class="oi-name">{{ i.productName }}</div>
          <div class="oi-spec">{{ i.skuSp || '官方正品 · 顺丰直达' }}</div>
          <div class="oi-bottom">
            <span class="oi-price">￥{{ i.price }}</span>
            <span class="oi-qty">× {{ i.quantity }}</span>
          </div>
        </div>
      </div>

      <!-- 履约保障 -->
      <div class="guarantee-row">
        <span>🛡️ 假一赔十</span>
        <span>🚚 顺丰包邮</span>
        <span>⚡ 极速退款</span>
        <span>📦 赠退货运费险</span>
      </div>

      <!-- 费用汇总 -->
      <div class="calc-section">
        <div class="calc-row">
          <span>商品总额</span>
          <span>￥{{ order.totalAmount }}</span>
        </div>
        <div class="calc-row">
          <span>运费</span>
          <span class="free">免运费</span>
        </div>
        <div class="calc-row total">
          <span>实付款</span>
          <span class="actual-price">￥{{ order.totalAmount }}</span>
        </div>
      </div>
    </div>

    <!-- 订单参数信息 -->
    <div class="order-meta-card mall-card">
      <div class="omc-row">
        <span>订单编号</span>
        <span class="selectable">{{ order.orderNo }}</span>
      </div>
      <div class="omc-row">
        <span>创建时间</span>
        <span>{{ order.createdAt }}</span>
      </div>
      <div v-if="order.paidAt" class="omc-row">
        <span>支付时间</span>
        <span>{{ order.paidAt }}</span>
      </div>
      <div v-if="order.shippedAt" class="omc-row">
        <span>发货时间</span>
        <span>{{ order.shippedAt }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  apiCancelOrder, apiConfirmReceipt, apiOrderDetail, apiOrderSimulateShip, apiPayOrder,
} from '@/api'
import type { OrderVO } from '@/types/api'

const route = useRoute()
const router = useRouter()
const order = ref<OrderVO | null>(null)
const shippingSimulating = ref(false)

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/orders')
}

const statusBannerTitle = computed(() => {
  if (!order.value) return ''
  switch (order.value.status) {
    case 'PENDING_PAYMENT': return '等待买家付款'
    case 'PAID': return '🎉 付款成功，等待商家发货'
    case 'SHIPPED': return '🚚 顺丰速运极速派送中'
    case 'DELIVERED': return '✨ 订单已完成，期待再次相遇'
    case 'CANCELLED': return '订单已取消'
    default: return order.value.statusText || order.value.status
  }
})

const statusBannerSub = computed(() => {
  if (!order.value) return ''
  switch (order.value.status) {
    case 'PENDING_PAYMENT': return '请在 30 分钟内完成支付，超时订单将自动关闭'
    case 'PAID': return '智能仓储正在加急出库，点击右侧可模拟商家发货'
    case 'SHIPPED': return '顺丰特快专递直达，预计明日送达'
    case 'DELIVERED': return '已确认收货，可点击右侧评价商品分享使用心得'
    case 'CANCELLED': return '款项已原路退回，库存已回补'
    default: return ''
  }
})

async function load() {
  try {
    order.value = await apiOrderDetail(Number(route.params.id))
  } catch {
    router.replace('/404')
  }
}

async function pay() {
  await apiPayOrder(order.value!.orderId)
  ElMessage.success('支付成功，已进入待发货状态')
  await load()
}

async function handleSimulateShip() {
  shippingSimulating.value = true
  try {
    await apiOrderSimulateShip(order.value!.orderId)
    ElMessage.success('已成功模拟顺丰速运出库发货！')
    await load()
  } catch {
    ElMessage.error('模拟发货失败，请重试')
  } finally {
    shippingSimulating.value = false
  }
}

async function confirmReceipt() {
  await ElMessageBox.confirm('确认已收到商品？', '确认收货', { type: 'info' })
  await apiConfirmReceipt(order.value!.orderId)
  ElMessage.success('已确认收货，感谢您的支持！')
  await load()
}

function goToReview() {
  router.push({ path: '/orders', query: { reviewOrderId: order.value?.orderId } })
}

onMounted(load)
</script>

<style scoped>
.detail-page {
  max-width: 720px;
  margin: 0 auto;
  padding: 16px 14px 40px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 顶部状态横幅 (拼多多/京东大厂风) */
.order-status-banner {
  background: linear-gradient(135deg, #18181b 0%, #27272a 100%);
  color: #ffffff;
  padding: 16px 18px;
  border-radius: var(--mall-radius, 10px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.order-status-banner.pending_payment {
  background: linear-gradient(135deg, #ea580c 0%, #f97316 100%);
}

.order-status-banner.paid {
  background: linear-gradient(135deg, #059669 0%, #10b981 100%);
}

.order-status-banner.shipped {
  background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%);
}

.osb-title {
  font-size: 16px;
  font-weight: 800;
}

.osb-sub {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.85);
  margin-top: 3px;
}

.osb-actions {
  flex-shrink: 0;
}

/* 顺丰物流卡片 */
.logistics-card {
  padding: 14px 16px;
  background: var(--mall-surface, #ffffff);
  border-radius: var(--mall-radius, 10px);
}

.lc-head {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--mall-border-light, #f4f4f5);
  margin-bottom: 10px;
}

.lc-company {
  font-weight: 700;
  color: #18181b;
}

html.dark .lc-company {
  color: #f4f4f5;
}

.lc-no {
  color: #71717a;
}

.lc-timeline {
  display: flex;
  flex-direction: column;
  gap: 12px;
  position: relative;
  padding-left: 14px;
  border-left: 2px solid var(--mall-border-light, #f4f4f5);
  margin-left: 6px;
}

.lc-node {
  position: relative;
}

.lcn-dot {
  position: absolute;
  left: -20px;
  top: 4px;
  width: 10px;
  height: 10px;
  border-radius: 9999px;
  background: #d4d4d8;
  border: 2px solid #ffffff;
}

.lc-node.active .lcn-dot {
  background: var(--mall-price, #e11d48);
  box-shadow: 0 0 0 3px rgba(225, 29, 72, 0.2);
}

.lcn-text {
  font-size: 12px;
  color: #3f3f46;
  line-height: 1.4;
}

html.dark .lcn-text {
  color: #d4d4d8;
}

.lc-node.active .lcn-text {
  font-weight: 700;
  color: #18181b;
}

html.dark .lc-node.active .lcn-text {
  color: #f4f4f5;
}

.lcn-time {
  font-size: 10px;
  color: #a1a1aa;
  margin-top: 2px;
}

/* 地址卡片 */
.address-info-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: var(--mall-surface, #ffffff);
  border-radius: var(--mall-radius, 10px);
}

.aic-icon {
  font-size: 20px;
  color: var(--el-color-primary, #2563eb);
}

.aic-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.aic-receiver {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 13px;
  font-weight: 700;
}

.aic-receiver .phone {
  color: #71717a;
  font-size: 12px;
  font-weight: 400;
}

.aic-address {
  font-size: 12px;
  color: #71717a;
}

/* 商品清单 */
.items-card {
  padding: 14px 16px;
  background: var(--mall-surface, #ffffff);
  border-radius: var(--mall-radius, 10px);
}

.card-caption {
  font-size: 13px;
  font-weight: 700;
  color: #18181b;
  margin-bottom: 10px;
}

html.dark .card-caption {
  color: #f4f4f5;
}

.order-item-row {
  display: flex;
  gap: 10px;
  padding: 8px 0;
  cursor: pointer;
  border-bottom: 1px solid var(--mall-border-light, #f4f4f5);
}

.oi-pic-box {
  width: 58px;
  height: 58px;
  border-radius: 6px;
  overflow: hidden;
  background: #f4f4f5;
  flex-shrink: 0;
}

.oi-pic {
  width: 100%;
  height: 100%;
}

.oi-fb {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}

.oi-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.oi-name {
  font-size: 13px;
  font-weight: 600;
  color: #18181b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

html.dark .oi-name {
  color: #f4f4f5;
}

.oi-spec {
  font-size: 11px;
  color: #a1a1aa;
}

.oi-bottom {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.oi-price {
  font-size: 13px;
  font-weight: 800;
  color: var(--mall-price, #e11d48);
}

.oi-qty {
  font-size: 11px;
  color: #71717a;
}

.guarantee-row {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #059669;
  padding: 10px 0;
  border-bottom: 1px solid var(--mall-border-light, #f4f4f5);
}

.calc-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-top: 10px;
  font-size: 12px;
  color: #71717a;
}

.calc-row {
  display: flex;
  justify-content: space-between;
}

.calc-row .free {
  color: #059669;
}

.calc-row.total {
  font-size: 14px;
  font-weight: 700;
  color: #18181b;
  padding-top: 4px;
}

html.dark .calc-row.total {
  color: #f4f4f5;
}

.actual-price {
  font-size: 16px;
  font-weight: 800;
  color: var(--mall-price, #e11d48);
}

/* 订单元信息 */
.order-meta-card {
  padding: 12px 16px;
  background: var(--mall-surface, #ffffff);
  border-radius: var(--mall-radius, 10px);
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 11px;
  color: #71717a;
}

.omc-row {
  display: flex;
  justify-content: space-between;
}

.selectable {
  user-select: text;
}
</style>
