<template>
  <div v-if="order" class="page detail">
    <h3 class="page-title">订单详情</h3>

    <!-- 状态时间线 -->
    <el-card shadow="never" class="card">
      <div class="status-head">
        <el-tag :type="tagType(order.status)" size="large">{{ order.statusText || order.status }}</el-tag>
        <span class="no">订单号：{{ order.orderNo }}</span>
        <span v-if="order.source === 'AI'" class="ai-source">AI 下单</span>
        <div class="spacer" />
        <el-button v-if="order.status === 'PENDING_PAYMENT'" type="primary" @click="pay">去支付</el-button>
        <el-button v-if="order.status === 'PENDING_PAYMENT'" @click="cancel">取消订单</el-button>
      </div>
      <el-steps :active="stepActive" align-center class="steps">
        <el-step title="下单" :description="order.createdAt" />
        <el-step title="支付" :description="order.paidAt" />
        <el-step title="发货" :description="order.shippedAt" />
        <el-step title="送达" :description="order.deliveredAt" />
      </el-steps>
      <div v-if="order.logisticsNo" class="logistics">物流单号：{{ order.logisticsNo }}</div>
    </el-card>

    <!-- 商品明细 -->
    <el-card shadow="never" class="card">
      <template #header>商品明细</template>
      <div v-for="(i, idx) in order.items" :key="idx" class="item">
        <span class="item-name">{{ i.productName }}</span>
        <span class="item-qty">￥{{ i.price }} × {{ i.quantity }}</span>
        <span class="item-subtotal">￥{{ i.subtotal }}</span>
      </div>
      <div class="total-row">合计：<span class="total">￥{{ order.totalAmount }}</span></div>
    </el-card>

    <!-- 收货信息 -->
    <el-card shadow="never" class="card">
      <template #header>收货信息</template>
      <el-descriptions :column="3">
        <el-descriptions-item label="收货人">{{ order.receiverName }}</el-descriptions-item>
        <el-descriptions-item label="电话">{{ order.receiverPhone }}</el-descriptions-item>
        <el-descriptions-item label="地址" :span="2">{{ order.receiverAddress }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiCancelOrder, apiOrderDetail, apiPayOrder } from '@/api'
import type { OrderVO } from '@/types/api'

const route = useRoute()
const router = useRouter()
const order = ref<OrderVO | null>(null)

const stepActive = computed(() => {
  const map: Record<string, number> = {
    PENDING_PAYMENT: 1, PAID: 2, SHIPPED: 3, DELIVERED: 4, CANCELLED: 1,
  }
  return map[order.value?.status || ''] ?? 0
})

onMounted(async () => {
  try {
    order.value = await apiOrderDetail(Number(route.params.id))
  } catch {
    router.replace('/404')
  }
})

async function pay() {
  await apiPayOrder(order.value!.orderId)
  ElMessage.success('支付成功，等待发货')
  order.value = await apiOrderDetail(order.value!.orderId)
}

async function cancel() {
  await ElMessageBox.confirm('确定取消该订单吗？', '提示', { type: 'warning' })
  await apiCancelOrder(order.value!.orderId)
  ElMessage.success('订单已取消')
  order.value = await apiOrderDetail(order.value!.orderId)
}

function tagType(status: string): 'warning' | 'primary' | 'success' | 'info' {
  return {
    PENDING_PAYMENT: 'warning', PAID: 'primary', SHIPPED: 'success', DELIVERED: 'success', CANCELLED: 'info',
  }[status] as never || 'info'
}
</script>

<style scoped>
.detail {
  height: 100%;
  overflow-y: auto;
  background: #fff;
  border-radius: 8px;
  margin: 16px;
  padding: 16px;
  height: calc(100% - 32px);
}

.card {
  margin-bottom: 14px;
}

.status-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.no {
  font-size: 13px;
  color: #606266;
}

.ai-source {
  font-size: 12px;
  color: var(--el-color-primary);
}

.spacer {
  flex: 1;
}

.steps {
  margin-top: 8px;
}

.logistics {
  margin-top: 12px;
  color: #909399;
  font-size: 13px;
}

.item {
  display: flex;
  gap: 16px;
  padding: 6px 0;
}

.item-name {
  flex: 1;
}

.item-qty {
  color: #909399;
}

.item-subtotal {
  width: 90px;
  text-align: right;
}

.total-row {
  text-align: right;
  margin-top: 8px;
  color: #606266;
}

.total {
  color: var(--el-color-danger);
  font-size: 20px;
  font-weight: 700;
}
</style>
