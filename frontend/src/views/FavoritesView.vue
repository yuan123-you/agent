<template>
  <el-scrollbar class="page-scroll" :distance="60" @end-reached="direction => direction === 'bottom' && loadMore()">
    <div class="page">
    <h3 class="page-title">我的收藏（{{ total }}）</h3>
    <div class="grid">
      <div v-for="p in products" :key="p.id" class="fav-card" @click="$router.push(`/products/${p.id}`)">
        <el-image :src="p.imageUrl" fit="cover" class="pic">
          <template #error>
            <div class="pic-fb">{{ p.name.slice(0, 1) }}</div>
          </template>
        </el-image>
        <div class="name">{{ p.name }}</div>
        <div class="row">
          <span class="price">￥{{ p.price }}</span>
          <el-button text type="danger" size="small" @click.stop="unfavorite(p)">取消收藏</el-button>
        </div>
      </div>
    </div>
    <el-empty v-if="!loading && products.length === 0" description="暂无收藏" />
    <div v-if="loading" class="load-state">加载中...</div>
    <div v-else-if="finished && products.length > 0" class="load-state">— 没有更多了 —</div>
    </div>
  </el-scrollbar>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiFavoriteToggle, apiFavorites } from '@/api'
import type { ProductVO } from '@/types/api'

type FavProduct = ProductVO & { time: string }

const products = ref<FavProduct[]>([])
const loading = ref(false)
const finished = ref(false)
const page = ref(1)
const total = ref(0)

async function load() {
  if (loading.value || finished.value) return
  loading.value = true
  try {
    const result = await apiFavorites({ page: page.value, size: 20 })
    products.value.push(...(result.records as FavProduct[]))
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

async function unfavorite(p: FavProduct) {
  await apiFavoriteToggle(p.id)
  ElMessage.success('已取消收藏')
  products.value = products.value.filter((x) => x.id !== p.id)
  total.value--
}

onMounted(load)
</script>

<style scoped>
.page-scroll { height: 100%; }
.page {
  min-height: 100%;
  box-sizing: border-box;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  padding: 16px;
}

.page-title {
  margin: 0 0 14px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.fav-card {
  background: #fff;
  border-radius: 8px;
  padding: 10px;
  cursor: pointer;
}

.pic {
  width: 100%;
  aspect-ratio: 1;
  border-radius: 6px;
}

.pic-fb {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  color: #c0c4cc;
  font-size: 36px;
  font-weight: 700;
}

.name {
  font-weight: 600;
  margin-top: 8px;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
}

.price {
  color: var(--el-color-danger);
  font-weight: 700;
  font-size: 17px;
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

  .grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }
}
</style>
