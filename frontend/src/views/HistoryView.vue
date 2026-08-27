<template>
  <el-scrollbar class="page-scroll" :distance="60" @end-reached="direction => direction === 'bottom' && loadMore()">
    <div class="page">
    <div class="head">
      <h3 class="page-title">浏览历史（{{ total }}）</h3>
      <el-button v-if="products.length > 0" text type="danger" @click="clear">清空历史</el-button>
    </div>
    <div class="list">
      <div v-for="p in products" :key="p.id" class="his-item" @click="$router.push(`/products/${p.id}`)">
        <el-image :src="p.imageUrl" fit="cover" class="pic">
          <template #error>
            <div class="pic-fb">{{ p.name.slice(0, 1) }}</div>
          </template>
        </el-image>
        <div class="info">
          <div class="name">{{ p.name }}</div>
          <div class="points">{{ p.sellingPoints }}</div>
          <div class="row">
            <span class="price">￥{{ p.price }}</span>
            <span class="time">{{ shortTime(p.time) }}</span>
          </div>
        </div>
      </div>
    </div>
    <el-empty v-if="!loading && products.length === 0" description="暂无浏览记录" />
    <div v-if="loading" class="load-state">加载中...</div>
    <div v-else-if="finished && products.length > 0" class="load-state">— 没有更多了 —</div>
    </div>
  </el-scrollbar>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiHistory, apiHistoryClear } from '@/api'
import type { ProductVO } from '@/types/api'

type HisProduct = ProductVO & { time: string }

const products = ref<HisProduct[]>([])
const loading = ref(false)
const finished = ref(false)
const page = ref(1)
const total = ref(0)

async function load() {
  if (loading.value || finished.value) return
  loading.value = true
  try {
    const result = await apiHistory({ page: page.value, size: 20 })
    products.value.push(...(result.records as HisProduct[]))
    total.value = result.total
    if (result.records.length === 0 || products.value.length >= result.total) {
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

async function clear() {
  await ElMessageBox.confirm('确定清空全部浏览历史吗？', '提示', { type: 'warning' })
  await apiHistoryClear()
  ElMessage.success('已清空')
  products.value = []
  total.value = 0
  finished.value = true
}

function shortTime(t?: string): string {
  return (t || '').replace('T', ' ').slice(5, 16)
}

onMounted(load)
</script>

<style scoped>
.page-scroll { height: 100%; }
.page {
  min-height: 100%;
  box-sizing: border-box;
  max-width: 960px;
  margin: 0 auto;
  width: 100%;
  padding: 16px;
}

.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.page-title {
  margin: 0 0 14px;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.his-item {
  display: flex;
  gap: 12px;
  background: #fff;
  border-radius: 8px;
  padding: 10px;
  cursor: pointer;
}

.pic {
  width: 88px;
  height: 88px;
  border-radius: 6px;
  flex-shrink: 0;
}

.pic-fb {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  color: #c0c4cc;
  font-size: 30px;
  font-weight: 700;
}

.info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.name {
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.points {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.row {
  margin-top: auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.price {
  color: var(--el-color-danger);
  font-weight: 700;
  font-size: 17px;
}

.time {
  font-size: 12px;
  color: #c0c4cc;
}

.load-state {
  text-align: center;
  color: #909399;
  font-size: 13px;
  padding: 18px 0 24px;
}

@media (max-width: 768px) {
  .page {
    padding: 10px;
  }

  .pic {
    width: 72px;
    height: 72px;
  }
}
</style>
