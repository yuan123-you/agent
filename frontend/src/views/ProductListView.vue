<template>
  <div
    class="page product-list"
    v-infinite-scroll="loadMore"
    :infinite-scroll-disabled="loading || finished"
    :infinite-scroll-distance="60"
  >
    <div class="filter-bar">
      <div class="filters">
        <el-input v-model="keyword" placeholder="搜索商品/品牌/卖点" clearable style="width: 220px"
          @keyup.enter="reload" @clear="reload" />
        <el-input-number v-model="maxPrice" :min="0" :step="500" placeholder="价格上限" style="width: 140px" />
        <el-select v-model="sort" style="width: 150px" @change="reload">
          <el-option label="最新上架" value="created_desc" />
          <el-option label="价格从低到高" value="price_asc" />
          <el-option label="价格从高到低" value="price_desc" />
        </el-select>
        <el-button type="primary" @click="reload">搜索</el-button>
      </div>
      <div class="result-meta">共 {{ total }} 件商品</div>
    </div>

    <div class="grid">
      <ProductCard v-for="p in products" :key="p.id" :product="p" />
    </div>
    <el-empty v-if="!loading && products.length === 0" description="没有找到相关商品" />

    <!-- 懒加载状态 -->
    <div v-if="loading" class="load-state">加载中...</div>
    <div v-else-if="finished && products.length > 0" class="load-state">— 没有更多了 —</div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { apiProducts } from '@/api'
import ProductCard from '@/components/product/ProductCard.vue'
import type { ProductVO } from '@/types/api'

const route = useRoute()

const products = ref<ProductVO[]>([])
const loading = ref(false)
const finished = ref(false)
const keyword = ref((route.query.keyword as string) || '')
const category = ref((route.query.category as string) || '')
const maxPrice = ref<number | undefined>()
const sort = ref('created_desc')
const page = ref(1)
const total = ref(0)

/** 顶部分类导航/搜索框切换时重置并重载 */
watch(
  () => route.query,
  () => {
    category.value = (route.query.category as string) || ''
    keyword.value = (route.query.keyword as string) || ''
    reload()
  },
)

function reload() {
  page.value = 1
  finished.value = false
  products.value = []
  load()
}

/** 懒加载：滚动到底部自动追加下一页 */
async function load() {
  if (loading.value || finished.value) return
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, size: 20, sort: sort.value }
    if (category.value) params.category = category.value
    if (keyword.value.trim()) params.keyword = keyword.value.trim()
    if (maxPrice.value) params.maxPrice = maxPrice.value
    const result = await apiProducts(params)
    products.value.push(...result.records)
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

onMounted(load)
</script>

<style scoped>
.product-list {
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  height: 100%;
  overflow-y: auto;
  padding: 16px;
  box-sizing: border-box;
}

.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.filters {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.result-meta {
  font-size: 13px;
  color: #909399;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
  min-height: 200px;
}

.load-state {
  text-align: center;
  color: #909399;
  font-size: 13px;
  padding: 18px 0 24px;
}

/* 平板 */
@media (max-width: 1024px) {
  .grid {
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  }
}

/* 手机 */
@media (max-width: 768px) {
  .product-list {
    padding: 10px;
  }

  .filters {
    width: 100%;
  }

  .filters .el-input,
  .filters .el-input-number {
    width: calc(50% - 4px) !important;
  }

  .result-meta {
    display: none;
  }

  .grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }
}
</style>
