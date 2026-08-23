<template>
  <div
    class="page orders"
    v-infinite-scroll="loadMore"
    :infinite-scroll-disabled="loading || finished"
    :infinite-scroll-distance="60"
  >
    <h3 class="page-title">我的订单</h3>
    <el-tabs v-model="status" @tab-change="reload">
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
          <el-button size="small" @click="$router.push(`/orders/${o.orderId}`)">查看详情</el-button>
        </div>
      </el-card>
      <el-empty v-if="!loading && orders.length === 0" description="暂无订单" />
    </div>

    <div v-if="loading" class="load-state">加载中...</div>
    <div v-else-if="finished && orders.length > 0" class="load-state">— 没有更多了 —</div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiCancelOrder, apiMyOrders, apiPayOrder, subscribeOrderStatus } from '@/api'
import type { OrderVO } from '@/types/api'

const orders = ref<OrderVO[]>([])
const loading = ref(false)
const finished = ref(false)
const status = ref('')
const page = ref(1)

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
.orders {
  background: #fff;
  border-radius: 8px;
  margin: 16px;
  padding: 16px;
  width: calc(100% - 32px);
  height: calc(100% - 32px);
  overflow-y: auto;
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
  color: #c0c4cc;
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
  background: #f5f7fa;
  border-radius: 6px;
}

.item {
  display: flex;
  gap: 16px;
  font-size: 14px;
  padding: 2px 0;
}

.item-name {
  flex: 1;
}

.item-qty {
  color: #909399;
}

.item-price {
  color: #606266;
}

.load-state {
  text-align: center;
  color: #909399;
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
</style>
