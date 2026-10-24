<template>
  <el-scrollbar class="page-scroll" :distance="60" @end-reached="direction => direction === 'bottom' && loadMore()">
    <div class="product-list">
      <!-- 常驻搜索框：随时在本页改词搜索 -->
      <div class="list-search">
        <input v-model="keywordInput" class="search-input" type="text"
          placeholder="搜索商品 / 品牌 / 卖点" @keyup.enter="doSearch" />
        <button class="search-btn" @click="doSearch">
          <el-icon :size="16"><Search /></el-icon>
          <span>搜索</span>
        </button>
      </div>

      <div class="list-body">
        <!-- ============ 左侧筛选侧栏（桌面） ============ -->
        <aside class="filter-side desktop-side">
          <div class="fs-block">
            <div class="fs-title">商品分类</div>
            <div v-for="c in sideCats" :key="c.key" class="fs-item"
              :class="{ active: isActiveCat(c) }" @click="pickCat(c)">
              <span class="fs-icon">{{ c.icon || '🛍️' }}</span>{{ c.name }}
            </div>
          </div>
          <div class="fs-block">
            <div class="fs-title">品牌</div>
            <div v-for="b in brands.slice(0, 12)" :key="b.id" class="fs-item"
              :class="{ active: brandId === b.id }" @click="pickBrand(b.id)">
              {{ b.name }}
            </div>
            <div v-if="brandId" class="fs-item fs-clear" @click="pickBrand(undefined)">清除品牌筛选</div>
          </div>
          <div class="fs-block">
            <div class="fs-title">价格区间</div>
            <div class="fs-price">
              <el-input-number v-model="minPrice" :min="0" :controls="false" placeholder="￥低" size="small" />
              <span class="dash">—</span>
              <el-input-number v-model="maxPrice" :min="0" :controls="false" placeholder="￥高" size="small" />
            </div>
            <el-button size="small" type="primary" plain class="fs-apply" @click="applyPrice">确定</el-button>
          </div>
        </aside>

        <!-- ============ 右侧主区 ============ -->
        <div class="list-main">
          <!-- 移动端分类横滑 chips -->
          <div class="mobile-cats">
            <span v-for="c in sideCats" :key="c.key" class="m-cat"
              :class="{ active: isActiveCat(c) }" @click="pickCat(c)">{{ c.name }}</span>
          </div>

          <!-- 排序条 -->
          <div class="sort-bar">
            <span class="sort-item" :class="{ active: sort === 'created_desc' }" @click="setSort('created_desc')">综合</span>
            <span class="sort-item" :class="{ active: sort === 'sales_desc' }" @click="setSort('sales_desc')">销量</span>
            <span class="sort-item" :class="{ active: sort === 'price_asc' || sort === 'price_desc' }" @click="togglePrice">
              价格 <i class="arr" :class="{ up: sort === 'price_asc' }">{{ sort === 'price_asc' ? '↑' : '↓' }}</i>
            </span>
            <span class="sort-item" :class="{ active: sort === 'newest' }" @click="setSort('newest')">新品</span>
          </div>

          <!-- 商品栅格 -->
          <div class="grid">
            <ProductCard v-for="p in products" :key="p.id" :product="p" />
          </div>
          <el-empty v-if="!loading && products.length === 0" description="没有找到相关商品" />

          <!-- 懒加载状态 -->
          <div v-if="loading" class="load-state">加载中...</div>
          <div v-else-if="finished && products.length > 0" class="load-state">— 没有更多了 —</div>
        </div>
      </div>
    </div>
  </el-scrollbar>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { apiCatalogBrands, apiCatalogCategories, apiProducts } from '@/api'
import ProductCard from '@/components/product/ProductCard.vue'
import { CATEGORIES, categoryIcon, categoryName } from '@/constants/categories'
import type { BrandVO, CategoryVO, ProductVO } from '@/types/api'

const route = useRoute()

const products = ref<ProductVO[]>([])
const loading = ref(false)
const finished = ref(false)
const keyword = ref((route.query.keyword as string) || '')
const keywordInput = ref(keyword.value)
const category = ref((route.query.category as string) || '')
const categoryId = ref<number | undefined>(
  route.query.categoryId ? Number(route.query.categoryId) : undefined,
)
const brandId = ref<number | undefined>(
  route.query.brandId ? Number(route.query.brandId) : undefined,
)
const brands = ref<BrandVO[]>([])
const minPrice = ref<number | undefined>()
const maxPrice = ref<number | undefined>()
const appliedMinPrice = ref<number | undefined>()
const appliedMaxPrice = ref<number | undefined>()
const sort = ref('created_desc')
const page = ref(1)
const total = ref(0)

// 侧栏分类：商城目录优先，为空时回落内置常量
interface SideCat { key: string; name: string; icon: string; query: Record<string, string> }
const sideCats = ref<SideCat[]>(
  CATEGORIES.map((c) => ({
    key: c.code,
    name: c.name,
    icon: c.icon,
    query: { category: c.code },
  })),
)

const listTitle = computed(() => {
  if (keyword.value) return `“${keyword.value}” 的搜索结果`
  const cat = sideCats.value.find((c) => isActiveCat(c))
  return cat ? cat.name : '全部商品'
})

function isActiveCat(c: SideCat): boolean {
  if ('categoryId' in c.query) return route.query.categoryId === c.query.categoryId
  return route.query.category === c.query.category
}

function pickCat(c: SideCat) {
  routerReplace({ ...c.query })
}

function pickBrand(id?: number) {
  const cur = new URLSearchParams(
    Object.entries(route.query).map(([k, v]) => [k, String(v)]),
  )
  if (id) cur.set('brandId', String(id))
  else cur.delete('brandId')
  routerReplace(Object.fromEntries(cur.entries()))
}

function applyPrice() {
  appliedMinPrice.value = minPrice.value
  appliedMaxPrice.value = maxPrice.value
  reload()
}

function doSearch() {
  // 搜索时重置分类/品牌筛选（对齐主流电商搜索动线）
  routerPush({ keyword: keywordInput.value.trim() })
}

function setSort(s: string) {
  sort.value = s === 'newest' ? 'created_desc' : s
  reload()
}

function togglePrice() {
  sort.value = sort.value === 'price_asc' ? 'price_desc' : 'price_asc'
  reload()
}

function routerReplace(query: Record<string, string>) {
  useSafeReplace(query)
}

function routerPush(query: Record<string, string>) {
  useSafeReplace(query)
}

import { useRouter } from 'vue-router'
const router = useRouter()

function useSafeReplace(query: Record<string, string>) {
  const cleaned = Object.fromEntries(Object.entries(query).filter(([, v]) => v !== ''))
  router.push({ path: '/products', query: cleaned })
}

/** 顶部分类导航/搜索框切换时重置并重载 */
watch(
  () => route.query,
  () => {
    category.value = (route.query.category as string) || ''
    keyword.value = (route.query.keyword as string) || ''
    categoryId.value = route.query.categoryId ? Number(route.query.categoryId) : undefined
    brandId.value = route.query.brandId ? Number(route.query.brandId) : undefined
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
    if (categoryId.value) params.categoryId = categoryId.value
    if (brandId.value) params.brandId = brandId.value
    if (keyword.value.trim()) params.keyword = keyword.value.trim()
    if (appliedMinPrice.value) params.minPrice = appliedMinPrice.value
    if (appliedMaxPrice.value) params.maxPrice = appliedMaxPrice.value
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

onMounted(() => {
  apiCatalogBrands().then((list) => (brands.value = list || [])).catch(() => {})
  apiCatalogCategories()
    .then((tree) => {
      if (tree && tree.length) {
        sideCats.value = tree.slice(0, 16).map((c: CategoryVO) => ({
          key: String(c.id),
          name: categoryName(c.name),
          icon: c.icon || categoryIcon(c.name),
          query: { categoryId: String(c.id) },
        }))
      }
    })
    .catch(() => {})
  load()
})
</script>

<style scoped>
.page-scroll { height: 100%; }

.product-list {
  max-width: var(--mall-container, 1200px);
  margin: 0 auto;
  width: 100%;
  min-height: 100%;
  padding: 14px 16px 24px;
  box-sizing: border-box;
}

/* 常驻搜索框 */
.list-search {
  display: flex;
  height: 40px;
  margin-bottom: 12px;
  border: 2px solid var(--el-color-primary);
  border-radius: 4px;
  overflow: hidden;
  background: var(--mall-surface, #fff);
}

.search-input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: none;
  padding: 0 14px;
  font-size: 14px;
  color: inherit;
  background: transparent;
}

.search-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  border: 0;
  padding: 0 22px;
  background: var(--el-color-primary);
  color: #fff;
  font-size: 14px;
  cursor: pointer;
  transition: filter 0.15s;
}

.search-btn:hover {
  filter: brightness(1.08);
}

@media (max-width: 768px) {
  .list-search {
    height: 36px;
    margin-bottom: 10px;
  }

  .search-btn {
    padding: 0 14px;
  }
}

/* 双栏 */
.list-body {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}

/* ============ 侧栏 ============ */
.filter-side {
  width: 190px;
  flex-shrink: 0;
  background: var(--mall-surface, #fff);
  border-radius: var(--mall-radius, 8px);
  box-shadow: var(--mall-shadow-card);
  padding: 8px 0 12px;
}

.fs-block {
  padding: 10px 0;
  border-bottom: 1px dashed var(--el-border-color-lighter, #ebeef5);
}

.fs-block:last-child {
  border-bottom: 0;
}

.fs-title {
  font-weight: 700;
  font-size: 14px;
  padding: 0 16px 6px;
}

.fs-item {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 16px;
  font-size: 13px;
  color: var(--el-text-color-regular, #606266);
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: all 0.12s;
}

.fs-item:hover {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.fs-item.active {
  color: var(--el-color-primary);
  font-weight: 600;
  background: var(--el-color-primary-light-9);
}

.fs-clear {
  color: var(--el-text-color-secondary, #909399);
}

.fs-price {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 16px 8px;
}

.fs-price :deep(.el-input-number) {
  width: 62px;
}

.fs-price .dash {
  color: var(--el-text-color-placeholder, #c0c4cc);
}

.fs-apply {
  margin: 0 16px;
  width: calc(100% - 32px);
}

/* ============ 主区 ============ */
.list-main {
  flex: 1;
  min-width: 0;
}

.mobile-cats {
  display: none;
}

/* 排序条 */
.sort-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--mall-surface, #fff);
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: var(--mall-radius, 8px);
  padding: 0 12px;
  height: 42px;
  margin-bottom: 12px;
}

.sort-item {
  padding: 0 16px;
  height: 28px;
  line-height: 28px;
  font-size: 13px;
  color: var(--el-text-color-regular, #606266);
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.12s;
}

.sort-item:hover {
  color: var(--el-color-primary);
}

.sort-item.active {
  color: var(--el-color-primary);
  font-weight: 600;
  background: var(--el-color-primary-light-9);
}

.sort-item .arr {
  font-style: normal;
  font-size: 11px;
}


/* 栅格 */
.grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  min-height: 200px;
}

.load-state {
  text-align: center;
  color: var(--el-text-color-secondary, #909399);
  font-size: 13px;
  padding: 18px 0 24px;
}

/* ============ 平板 769-1199 ============ */
@media (max-width: 1199px) and (min-width: 769px) {
  .filter-side {
    width: 160px;
  }

  .grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

/* ============ 手机 ≤768 ============ */
@media (max-width: 768px) {
  .desktop-side {
    display: none;
  }

  .product-list {
    padding: 10px 12px 20px;
  }

  .mobile-cats {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    padding-bottom: 8px;
    scrollbar-width: none;
  }

  .mobile-cats::-webkit-scrollbar {
    display: none;
  }

  .m-cat {
    flex-shrink: 0;
    padding: 4px 12px;
    border-radius: 14px;
    background: var(--mall-surface, #fff);
    font-size: 13px;
    color: var(--el-text-color-regular, #606266);
    cursor: pointer;
  }

  .m-cat.active {
    background: var(--el-color-primary);
    color: #fff;
  }

  .grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }
}
</style>
