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

      <!-- 已选条件标签（可单个移除） -->
      <div v-if="activeFilters.length" class="applied-bar">
        <span class="applied-label">已选条件：</span>
        <span v-for="f in activeFilters" :key="f.key" class="applied-chip">
          {{ f.label }}
          <i class="x" @click="f.clear()">×</i>
        </span>
        <span class="applied-clear" @click="clearAll">清空全部</span>
      </div>

      <div class="list-body">
        <!-- ============ 左侧筛选侧栏（桌面） ============ -->
        <aside class="filter-side desktop-side">
          <div class="fs-block">
            <div class="fs-title">商品分类</div>
            <div class="fs-item" :class="{ active: !hasCatFilter }" @click="clearCat">
              <span class="fs-icon">🛍️</span>全部分类
            </div>
            <div v-for="c in sideCats" :key="c.key" class="fs-item"
              :class="{ active: isActiveCat(c) }" @click="pickCat(c)">
              <span class="fs-icon">{{ c.icon || '🛍️' }}</span>{{ c.name }}
            </div>
          </div>
          <div class="fs-block">
            <div class="fs-title">品牌</div>
            <input v-model="brandFilter" class="fs-brand-search" type="text" placeholder="搜索品牌" />
            <div class="fs-item" :class="{ active: !brandId }" @click="pickBrand(undefined)">全部品牌</div>
            <div v-for="b in visibleBrands" :key="b.id" class="fs-item"
              :class="{ active: brandId === b.id }" @click="pickBrand(b.id)">
              {{ b.name }}
            </div>
            <div v-if="brandFilteredCount > brandLimit" class="fs-expand" @click="brandExpanded = !brandExpanded">
              {{ brandExpanded ? '收起 ∧' : `展开全部 (${brandFilteredCount}) ∨` }}
            </div>
          </div>
          <div class="fs-block">
            <div class="fs-title">价格区间</div>
            <div class="fs-price">
              <el-input-number v-model="minPrice" :min="0" :controls="false" placeholder="￥低" size="small" />
              <span class="dash">—</span>
              <el-input-number v-model="maxPrice" :min="0" :controls="false" placeholder="￥高" size="small" />
            </div>
            <el-button size="small" type="primary" class="fs-apply" @click="applyPrice">确定</el-button>
            <div class="fs-quick">
              <span v-for="q in QUICK_PRICE" :key="q.label" class="fs-q" @click="applyQuickPrice(q)">{{ q.label }}</span>
            </div>
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
            <span class="sort-meta">
              <el-button class="mobile-filter-btn" size="small" plain type="primary" @click="filterDrawer = true">
                <el-icon><Filter /></el-icon>筛选<em v-if="activeFilters.length" class="f-count">{{ activeFilters.length }}</em>
              </el-button>
            </span>
          </div>

          <!-- 商品栅格 -->
          <div class="grid">
            <ProductCard v-for="p in products" :key="p.id" :product="p" show-points />
          </div>
          <el-empty v-if="!loading && products.length === 0" description="没有找到相关商品">
            <div class="empty-tips">
              <div class="empty-tip-label">大家都在逛：</div>
              <span v-for="c in sideCats.slice(0, 6)" :key="c.key" class="empty-tip"
                @click="clearAllThenGo(c)">{{ c.name }}</span>
            </div>
          </el-empty>

          <!-- 懒加载状态 -->
          <div v-if="loading" class="load-state">加载中...</div>
          <div v-else-if="finished && products.length > 0" class="load-state">— 没有更多了 —</div>
        </div>
      </div>

      <!-- ============ 移动端筛选抽屉 ============ -->
      <el-drawer v-model="filterDrawer" direction="btt" size="72vh" class="filter-drawer"
        :with-header="false">
        <div class="fd-body">
          <div class="fd-head">
            <span>筛选</span>
            <el-icon class="fd-close" @click="filterDrawer = false"><Close /></el-icon>
          </div>
          <div class="fd-block">
            <div class="fd-title">商品分类</div>
            <div class="fd-opts">
              <span class="fd-opt" :class="{ active: !hasCatFilter }" @click="clearCat">全部</span>
              <span v-for="c in sideCats" :key="c.key" class="fd-opt"
                :class="{ active: isActiveCat(c) }" @click="pickCat(c); filterDrawer = false">{{ c.name }}</span>
            </div>
          </div>
          <div class="fd-block">
            <div class="fd-title">品牌</div>
            <div class="fd-opts">
              <span class="fd-opt" :class="{ active: !brandId }" @click="pickBrand(undefined); filterDrawer = false">全部</span>
              <span v-for="b in brands.slice(0, 14)" :key="b.id" class="fd-opt"
                :class="{ active: brandId === b.id }" @click="pickBrand(b.id); filterDrawer = false">{{ b.name }}</span>
            </div>
          </div>
          <div class="fd-block">
            <div class="fd-title">价格区间</div>
            <div class="fs-price">
              <el-input-number v-model="minPrice" :min="0" :controls="false" placeholder="￥低" size="small" />
              <span class="dash">—</span>
              <el-input-number v-model="maxPrice" :min="0" :controls="false" placeholder="￥高" size="small" />
            </div>
            <div class="fs-quick">
              <span v-for="q in QUICK_PRICE" :key="q.label" class="fs-q" @click="applyQuickPrice(q)">{{ q.label }}</span>
            </div>
          </div>
        </div>
        <div class="fd-foot">
          <el-button class="fd-reset" @click="clearAll; filterDrawer = false">重置</el-button>
          <el-button class="fd-ok" type="danger" @click="applyPrice(); filterDrawer = false">确定</el-button>
        </div>
      </el-drawer>
    </div>
  </el-scrollbar>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Close, Filter, Search } from '@element-plus/icons-vue'
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

// 价格快捷档
const QUICK_PRICE = [
  { label: '0-50', min: 0, max: 50 },
  { label: '50-100', min: 50, max: 100 },
  { label: '100-300', min: 100, max: 300 },
  { label: '300-1000', min: 300, max: 1000 },
  { label: '1000+', min: 1000, max: undefined as number | undefined },
]

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

// 品牌内联过滤 + 展开
const brandFilter = ref('')
const brandExpanded = ref(false)
const brandLimit = 10
const brandFilteredCount = computed(() =>
  brands.value.filter((b) => !brandFilter.value.trim() || b.name.includes(brandFilter.value.trim())).length,
)
const visibleBrands = computed(() => {
  const kw = brandFilter.value.trim()
  const list = brands.value.filter((b) => !kw || b.name.includes(kw))
  return brandExpanded.value || kw ? list : list.slice(0, brandLimit)
})

// 已选条件标签
const activeFilters = computed(() => {
  const out: { key: string; label: string; clear: () => void }[] = []
  if (keyword.value) out.push({ key: 'kw', label: `“${keyword.value}”`, clear: () => routerPush({}) })
  if (hasCatFilter.value) {
    const c = sideCats.value.find((x) => isActiveCat(x))
    out.push({ key: 'cat', label: c ? c.name : '分类', clear: () => clearCat() })
  }
  if (brandId.value) {
    const b = brands.value.find((x) => x.id === brandId.value)
    out.push({ key: 'brand', label: b ? b.name : '品牌', clear: () => pickBrand(undefined) })
  }
  if (appliedMinPrice.value != null || appliedMaxPrice.value != null) {
    out.push({
      key: 'price',
      label: `￥${appliedMinPrice.value ?? 0}-${appliedMaxPrice.value ?? '∞'}`,
      clear: () => {
        minPrice.value = undefined
        maxPrice.value = undefined
        appliedMinPrice.value = undefined
        appliedMaxPrice.value = undefined
        reload()
      },
    })
  }
  return out
})

const hasCatFilter = computed(() => Boolean(category.value || categoryId.value))

function isActiveCat(c: SideCat): boolean {
  if ('categoryId' in c.query) return route.query.categoryId === c.query.categoryId
  return route.query.category === c.query.category
}

function pickCat(c: SideCat) {
  routerReplace({ ...c.query })
}

function clearCat() {
  routerReplace({})
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

function applyQuickPrice(q: { label: string; min: number; max?: number }) {
  minPrice.value = q.min
  maxPrice.value = q.max
  appliedMinPrice.value = q.min
  appliedMaxPrice.value = q.max
  reload()
}

function clearAllThenGo(c: SideCat) {
  clearAll()
  routerPush({ ...c.query })
}

function clearAll() {
  routerPush({})
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

const filterDrawer = ref(false)

function routerReplace(query: Record<string, string>) {
  useSafeReplace(query)
}

function routerPush(query: Record<string, string>) {
  useSafeReplace(query)
}

import { useRouter } from 'vue-router'
const router = useRouter()

function useSafeReplace(query: Record<string, string>) {
  const cleaned = Object.fromEntries(
    Object.entries(query).filter(([, v]) => v !== '' && v != null),
  )
  router.push({ path: '/products', query: cleaned })
}

/** 顶部分类导航/搜索框切换时重置并重载 */
watch(
  () => route.query,
  () => {
    category.value = (route.query.category as string) || ''
    keyword.value = (route.query.keyword as string) || ''
    keywordInput.value = keyword.value
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
          icon: c.icon || '',
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

/* 已选条件标签 */
.applied-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  background: var(--mall-surface, #fff);
  border: 1px dashed var(--el-color-primary-light-7);
  border-radius: var(--mall-radius, 8px);
  padding: 8px 12px;
  margin-bottom: 12px;
}

.applied-label {
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
}

.applied-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 4px;
}

.applied-chip .x {
  font-style: normal;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
}

.applied-chip .x:hover {
  color: var(--mall-price, #e4393c);
}

.applied-clear {
  margin-left: auto;
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
  cursor: pointer;
}

.applied-clear:hover {
  color: var(--el-color-primary);
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

.fs-brand-search {
  width: calc(100% - 24px);
  margin: 0 12px 6px;
  height: 26px;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  padding: 0 8px;
  font-size: 12px;
  outline: none;
  color: inherit;
  background: transparent;
}

.fs-brand-search:focus {
  border-color: var(--el-color-primary);
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

.fs-expand {
  padding: 6px 16px 0;
  font-size: 12px;
  color: var(--el-color-primary);
  cursor: pointer;
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
  margin: 0 16px 8px;
  width: calc(100% - 32px);
}

.fs-quick {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 0 16px;
}

.fs-q {
  font-size: 12px;
  color: var(--el-text-color-regular, #606266);
  background: var(--el-fill-color, #f0f2f5);
  padding: 3px 8px;
  border-radius: 4px;
  cursor: pointer;
}

.fs-q:hover {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
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

.sort-meta {
  margin-left: auto;
}

.mobile-filter-btn {
  position: relative;
}

.f-count {
  font-style: normal;
  margin-left: 4px;
  background: var(--mall-price, #e4393c);
  color: #fff;
  border-radius: 8px;
  font-size: 11px;
  padding: 0 5px;
  line-height: 16px;
}

/* 空结果推荐 */
.empty-tips {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 10px;
}

.empty-tip-label {
  font-size: 13px;
  color: var(--el-text-color-secondary, #909399);
}

.empty-tip {
  font-size: 13px;
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  padding: 4px 12px;
  border-radius: 14px;
  cursor: pointer;
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

/* ============ 移动端筛选抽屉 ============ */
.fd-body {
  padding: 0 16px 12px;
  overflow-y: auto;
  height: calc(100% - 64px);
}

.fd-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 16px;
  font-weight: 700;
  padding: 14px 0 8px;
  position: sticky;
  top: 0;
  background: var(--mall-surface, #fff);
}

.fd-close {
  cursor: pointer;
  font-size: 18px;
}

.fd-block {
  padding: 10px 0;
  border-bottom: 1px dashed var(--el-border-color-lighter, #ebeef5);
}

.fd-title {
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 8px;
}

.fd-opts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.fd-opt {
  font-size: 13px;
  padding: 5px 14px;
  border-radius: 15px;
  background: var(--el-fill-color, #f0f2f5);
  color: var(--el-text-color-regular, #606266);
  cursor: pointer;
}

.fd-opt.active {
  background: var(--el-color-primary);
  color: #fff;
}

.fd-foot {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  gap: 10px;
  padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
  background: var(--mall-surface, #fff);
  border-top: 1px solid var(--el-border-color-lighter, #ebeef5);
}

.fd-foot .el-button {
  flex: 1;
  height: 40px;
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
