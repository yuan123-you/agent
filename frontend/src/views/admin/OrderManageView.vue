<template>
  <el-scrollbar class="page-scroll" :distance="60" @end-reached="direction => direction === 'bottom' && loadMore()">
    <div class="page">
    <div class="toolbar">
      <h3 class="page-title">订单管理（{{ total }}）</h3>
      <el-select v-model="status" style="width: 140px" @change="reload">
        <el-option label="全部状态" value="" />
        <el-option label="待支付" value="PENDING_PAYMENT" />
        <el-option label="已支付" value="PAID" />
        <el-option label="已发货" value="SHIPPED" />
        <el-option label="已送达" value="DELIVERED" />
        <el-option label="已取消" value="CANCELLED" />
      </el-select>
    </div>

    <el-table v-loading="loading && orders.length === 0" :data="orders" border stripe>
      <el-table-column prop="orderNo" label="订单号" width="180" />
      <el-table-column prop="userNickname" label="买家" width="100" />
      <el-table-column label="商品" min-width="200">
        <template #default="{ row }">
          <span v-for="(i, idx) in row.items" :key="idx">{{ i.productName }}×{{ i.quantity }} </span>
        </template>
      </el-table-column>
      <el-table-column label="金额" width="100">
        <template #default="{ row }">￥{{ row.totalAmount }}</template>
      </el-table-column>
      <el-table-column label="来源" width="80">
        <template #default="{ row }">
          <el-tag v-if="row.source === 'AI'" size="small">AI</el-tag>
          <span v-else>页面</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="tagType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="createdAt" label="下单时间" width="160" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'PAID'" size="small" type="primary" @click="ship(row)">发货</el-button>
          <el-button v-if="row.status === 'SHIPPED'" size="small" @click="deliver(row)">标记送达</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="loading" class="load-state">加载中...</div>
    <div v-else-if="finished && orders.length > 0" class="load-state">— 没有更多了 —</div>

    <!-- 发货弹窗 -->
    <el-dialog v-model="shipDialog" title="订单发货" width="380px">
      <el-form label-width="80px">
        <el-form-item label="物流单号">
          <el-input v-model="logisticsNo" placeholder="留空自动生成" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="shipDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmShip">确认发货</el-button>
      </template>
    </el-dialog>
    </div>
  </el-scrollbar>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiAdminDeliver, apiAdminOrders, apiAdminShip } from '@/api'
import type { OrderVO } from '@/types/api'

const orders = ref<OrderVO[]>([])
const loading = ref(false)
const finished = ref(false)
const status = ref('')
const page = ref(1)
const total = ref(0)
const shipDialog = ref(false)
const logisticsNo = ref('')
const currentOrder = ref<OrderVO | null>(null)

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
    const result = await apiAdminOrders({
      page: page.value, size: 20,
      ...(status.value ? { status: status.value } : {}),
    })
    orders.value.push(...result.records)
    total.value = result.total
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

function ship(row: OrderVO) {
  currentOrder.value = row
  logisticsNo.value = ''
  shipDialog.value = true
}

async function confirmShip() {
  if (!currentOrder.value) return
  await apiAdminShip(currentOrder.value.orderId, logisticsNo.value.trim())
  ElMessage.success('发货成功')
  shipDialog.value = false
  reload()
}

async function deliver(row: OrderVO) {
  await apiAdminDeliver(row.orderId)
  ElMessage.success('已标记送达')
  reload()
}

function statusText(status: string): string {
  return {
    PENDING_PAYMENT: '待支付', PAID: '已支付', SHIPPED: '已发货',
    DELIVERED: '已送达', CANCELLED: '已取消',
  }[status] || status
}

function tagType(status: string): 'warning' | 'primary' | 'success' | 'info' {
  return {
    PENDING_PAYMENT: 'warning', PAID: 'primary', SHIPPED: 'success',
    DELIVERED: 'success', CANCELLED: 'info',
  }[status] as never || 'info'
}

onMounted(load)
</script>

<style scoped>
.page-scroll { height: 100%; }
.page {
  min-height: 100%;
  box-sizing: border-box;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.page-title {
  margin: 0;
  flex: 1;
}

.load-state {
  text-align: center;
  color: #909399;
  font-size: 13px;
  padding: 18px 0 24px;
}
</style>
