<template>
  <div class="category-page-mode-b">
    <!-- ============ 顶部唯一极简搜索栏 (0px 紧贴顶部，带历史搜索与猜你想搜) ============ -->
    <header class="cat-search-bar-wrap">
      <div class="cat-search-box">
        <el-icon :size="16" class="cs-icon"><Search /></el-icon>
        <input
          v-model="keywordInput"
          class="cs-input"
          type="text"
          placeholder="搜索品牌 / 分类 / 单品..."
          @focus="showSearchPanel = true"
          @keyup.enter="handleSearch"
        />
        <button v-if="keywordInput" class="cs-clear-input" @click="keywordInput = ''; handleSearch()">
          <el-icon><CircleClose /></el-icon>
        </button>
        <button class="cs-submit-btn" @click="handleSearch">搜索</button>
      </div>

      <!-- 搜索展开浮窗：历史搜索 + 猜你想搜 -->
      <transition name="panel-fade">
        <div v-if="showSearchPanel" class="search-overlay-panel mall-card" @mouseleave="showSearchPanel = false">
          <!-- 历史搜索记录 -->
          <div class="search-block">
            <div class="sb-header">
              <span class="sb-title">历史搜索</span>
              <button v-if="searchHistory.length" class="sb-clear" @click="clearAllHistory">清空</button>
            </div>
            <div v-if="searchHistory.length" class="sb-tags">
              <span v-for="word in searchHistory" :key="word" class="history-chip" @click="applyKeyword(word)">
                <span>{{ word }}</span>
                <i class="del-chip" @click.stop="removeHistory(word)">×</i>
              </span>
            </div>
            <div v-else class="sb-empty">暂无搜索历史</div>
          </div>

          <!-- 猜你想搜 -->
          <div class="search-block">
            <div class="sb-header">
              <span class="sb-title">猜你想搜</span>
              <span class="guess-badge">热门</span>
            </div>
            <div class="guess-grid">
              <div
                v-for="(item, idx) in GUESS_SEARCH_WORDS"
                :key="item"
                class="guess-item"
                @click="applyKeyword(item)"
              >
                <span class="guess-rank" :class="{ 'top-rank': idx < 3 }">{{ idx + 1 }}</span>
                <span class="guess-word">{{ item }}</span>
              </div>
            </div>
          </div>
        </div>
      </transition>
    </header>

    <!-- ============ 形态 B：全宽探索页，移除左侧挤占空间的纵向侧栏 ============ -->
    <!-- 一级品类横向滑动胶囊栏 -->
    <div class="main-cat-bar-wrap">
      <div class="main-cat-bar">
        <span
          v-for="cat in MAIN_CATEGORIES"
          :key="cat.code"
          class="main-cat-tab"
          :class="{ active: activeCategoryCode === cat.code }"
          @click="selectCategory(cat.code)"
        >
          <span>{{ cat.name }}</span>
        </span>
      </div>
    </div>

    <!-- 二级细分品类扁平胶囊栏（彻底移除了分类名称和商品数量等冗余描述） -->
    <div class="sub-cat-bar-wrap">
      <div class="sub-cat-bar">
        <span
          v-for="sub in currentSubcategories"
          :key="sub"
          class="sub-cat-chip"
          :class="{ active: selectedSub === sub || (sub === '全部' && !selectedSub) }"
          @click="selectSubcategory(sub)"
        >
          {{ sub }}
        </span>
      </div>
    </div>

    <!-- ============ 排序与筛选工具栏（综合推荐、销量优先、价格双箭头、好评优先、定位、筛选） ============ -->
    <div class="filter-sort-bar-wrap">
      <div class="filter-sort-bar container">
        <div class="fsb-left">
          <!-- 综合推荐 -->
          <button
            class="fsb-tab"
            :class="{ active: sort === 'default' }"
            @click="setSort('default')"
          >
            综合推荐
          </button>

          <!-- 销量优先 (无图标) -->
          <button
            class="fsb-tab"
            :class="{ active: sort === 'sales_desc' }"
            @click="setSort('sales_desc')"
          >
            销量优先
          </button>

          <!-- 价格双三角箭头（升序▲高亮红 / 降序▼高亮红，不再展示繁琐文字） -->
          <button
            class="fsb-tab price-fsb-tab"
            :class="{ active: sort.startsWith('price') }"
            @click="togglePrice"
          >
            <span>价格</span>
            <div class="price-arrows-stack">
              <span class="arrow-up" :class="{ 'arrow-active': sort === 'price_asc' }">▲</span>
              <span class="arrow-down" :class="{ 'arrow-active': sort === 'price_desc' }">▼</span>
            </div>
          </button>

          <!-- 好评优先 (无图标) -->
          <button
            class="fsb-tab"
            :class="{ active: sort === 'rating' }"
            @click="setSort('rating')"
          >
            好评优先
          </button>
        </div>

        <div class="fsb-right">
          <!-- 定位入口 (无折行保护) -->
          <button class="location-btn" @click="locateCity">
            <el-icon :size="12"><LocationInformation /></el-icon>
            <span>{{ shortCity }}</span>
          </button>

          <!-- 筛选抽屉开关 -->
          <button class="filter-drawer-btn" @click="showFilterDrawer = true">
            <el-icon :size="13"><Operation /></el-icon>
            <span>筛选</span>
            <span v-if="appliedFilterCount > 0" class="filter-count-badge">{{ appliedFilterCount }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- ============ 全宽双列真实交错瀑布流 (严格一行 2 列，方式 1 点击跳转大页) ============ -->
    <main class="waterfall-stream-main container">
      <div class="pdd-waterfall-layout">
        <!-- 左列瀑布流 -->
        <div class="waterfall-col">
          <div
            v-for="p in leftColProducts"
            :key="p.id"
            class="stream-product-card"
            @click="goToDetail(p.id)"
          >
            <div class="spc-pic-wrap" :style="{ aspectRatio: p.aspectRatio || '1/1' }">
              <el-image :src="p.imageUrl" fit="cover" class="spc-img" lazy decoding="async">
                <template #placeholder>
                  <div class="spc-skeleton mall-skeleton" />
                </template>
                <template #error>
                  <div class="spc-fallback">{{ p.name.slice(0, 1) }}</div>
                </template>
              </el-image>
              </div>

            <div class="spc-info">
              <div v-if="p.brand" class="spc-brand">{{ p.brand }}</div>
              <div class="spc-title" :title="p.name">{{ p.name }}</div>

              <div class="spc-bottom">
                <div class="spc-price-box">
                  <span class="spc-price"><i>￥</i>{{ p.price }}</span>
                  </div>
                <span class="spc-sales">销量 {{ formatSales(p.sales) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 右列瀑布流 -->
        <div class="waterfall-col">
          <div
            v-for="p in rightColProducts"
            :key="p.id"
            class="stream-product-card"
            @click="goToDetail(p.id)"
          >
            <div class="spc-pic-wrap" :style="{ aspectRatio: p.aspectRatio || '1/1' }">
              <el-image :src="p.imageUrl" fit="cover" class="spc-img" lazy decoding="async">
                <template #placeholder>
                  <div class="spc-skeleton mall-skeleton" />
                </template>
                <template #error>
                  <div class="spc-fallback">{{ p.name.slice(0, 1) }}</div>
                </template>
              </el-image>
              </div>

            <div class="spc-info">
              <div v-if="p.brand" class="spc-brand">{{ p.brand }}</div>
              <div class="spc-title" :title="p.name">{{ p.name }}</div>

              <div class="spc-bottom">
                <div class="spc-price-box">
                  <span class="spc-price"><i>￥</i>{{ p.price }}</span>
                  </div>
                <span class="spc-sales">销量 {{ formatSales(p.sales) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 空结果提示 -->
      <p v-if="catalogLoading" role="status">商品加载中...</p>
      <p v-else-if="catalogError" role="alert">商品加载失败 <button @click="loadCatalogPage">重试</button></p>
      <button v-else-if="!catalogFinished" @click="loadCatalogPage">加载更多商品</button>
      <div v-if="!catalogLoading && !catalogError && filteredProducts.length === 0" class="stream-empty">
        <div class="empty-icon">🛍️</div>
        <div class="empty-text">暂无符合条件的商品</div>
        <el-button size="small" type="primary" round @click="resetAllFilters">重置全部筛选</el-button>
      </div>

      <div v-else-if="catalogFinished && filteredProducts.length > 0" class="stream-end">
        — 已经到底了 · 甄选好物持续更新中 (共 {{ filteredProducts.length }} 款) —
      </div>
    </main>

    <!-- ============ 高级筛选抽屉 (支持价格区间、品牌勾选、现货包邮) ============ -->
    <el-drawer
      v-model="showFilterDrawer"
      title="高级筛选"
      size="340px"
      direction="rtl"
      class="filter-drawer-custom"
      append-to-body
    >
      <div class="drawer-filter-content">
        <!-- 价格区间 -->
        <div class="df-section">
          <div class="df-title">价格区间 (元)</div>
          <div class="price-input-row">
            <input v-model.number="filterMinPrice" type="number" placeholder="最低价" class="pi-input" />
            <span class="pi-dash">—</span>
            <input v-model.number="filterMaxPrice" type="number" placeholder="最高价" class="pi-input" />
          </div>
          <div class="price-quick-tags">
            <span class="pqt-tag" @click="setQuickPrice(0, 100)">0-100</span>
            <span class="pqt-tag" @click="setQuickPrice(100, 500)">100-500</span>
            <span class="pqt-tag" @click="setQuickPrice(500, 2000)">500-2000</span>
            <span class="pqt-tag" @click="setQuickPrice(2000, 10000)">2000以上</span>
          </div>
        </div>

        <!-- 品牌筛选 -->
        <div class="df-section" v-if="currentCategoryBrands.length">
          <div class="df-title">品牌选择</div>
          <div class="brand-chips-wrap">
            <span
              v-for="b in currentCategoryBrands"
              :key="b"
              class="brand-filter-chip"
              :class="{ active: selectedBrand === b }"
              @click="selectedBrand = selectedBrand === b ? '' : b"
            >
              {{ b }}
            </span>
          </div>
        </div>

        <!-- 服务与特性 -->
        <div class="df-section">
          <div class="df-title">服务与优惠</div>
          <div class="switch-row">
            <span>顺丰包邮</span>
            <el-switch v-model="filterFreeShipping" />
          </div>
          <div class="switch-row">
            <span>降价特惠</span>
            <el-switch v-model="filterDiscountOnly" />
          </div>
          <div class="switch-row">
            <span>仅看有货</span>
            <el-switch v-model="filterInStockOnly" />
          </div>
        </div>

        <!-- 抽屉底部按钮 -->
        <div class="df-footer">
          <button class="df-reset-btn" @click="resetDrawerFilters">重置</button>
          <button class="df-confirm-btn" @click="showFilterDrawer = false">
            确定 ({{ filteredProducts.length }}款)
          </button>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search, CircleClose, LocationInformation, Operation } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { apiProducts } from '@/api'
import type { EnhancedProduct } from '@/data/products'

const route = useRoute()
const router = useRouter()
const products = ref<EnhancedProduct[]>([])
const catalogLoading = ref(false)
const catalogError = ref(false)
const catalogFinished = ref(false)
let catalogPage = 1
let catalogGeneration = 0
let disposed = false

const keywordInput = ref((route.query.keyword as string) || '')
const searchKeyword = ref(keywordInput.value)
const showSearchPanel = ref(false)
const showFilterDrawer = ref(false)

// 排序：default 综合推荐 / sales_desc 销量优先 / price_asc 价格升序 / price_desc 价格降序 / rating 好评优先
const sort = ref<'default' | 'sales_desc' | 'price_asc' | 'price_desc' | 'rating'>('default')

// 过滤参数
const filterMinPrice = ref<number | ''>('')
const filterMaxPrice = ref<number | ''>('')
const selectedBrand = ref('')
const filterFreeShipping = ref(false)
const filterDiscountOnly = ref(false)
const filterInStockOnly = ref(false)

// 配送定位
const deliveryCity = ref('北京市')
const shortCity = computed(() => deliveryCity.value)

function locateCity() {
  if (navigator.geolocation) {
    ElMessage.info('正在获取当前定位...')
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        deliveryCity.value = '北京市海淀区'
        ElMessage.success('已自动定位至：北京市海淀区')
      },
      () => {
        deliveryCity.value = '北京市朝阳区'
        ElMessage.success('定位成功：北京市朝阳区')
      },
      { timeout: 3000 }
    )
  } else {
    deliveryCity.value = '北京市'
  }
}

// 历史搜索
const HISTORY_KEY = 'aimall_search_history_v2'
const searchHistory = ref<string[]>(
  JSON.parse(localStorage.getItem(HISTORY_KEY) || '["降噪耳机", "轻薄笔记本", "机械键盘", "车厘子"]')
)

const GUESS_SEARCH_WORDS = [
  'iPhone 15 Pro 钛金属',
  'Sony 降噪头戴耳机',
  'M3 Pro 轻薄笔记本',
  'Keychron 机械键盘',
  '智利 JJJ 车厘子原箱',
  '始祖鸟 GORE-TEX 冲锋衣',
  '安格斯谷饲眼肉牛排',
  '赫曼米勒人体工学椅',
]

function saveHistory(w: string) {
  if (!w.trim()) return
  const list = [w, ...searchHistory.value.filter((x) => x !== w)].slice(0, 8)
  searchHistory.value = list
  localStorage.setItem(HISTORY_KEY, JSON.stringify(list))
}

function removeHistory(w: string) {
  searchHistory.value = searchHistory.value.filter((x) => x !== w)
  localStorage.setItem(HISTORY_KEY, JSON.stringify(searchHistory.value))
}

function clearAllHistory() {
  searchHistory.value = []
  localStorage.removeItem(HISTORY_KEY)
}

function handleSearch() {
  searchKeyword.value = keywordInput.value.trim()
  const kw = keywordInput.value.trim()
  if (kw) saveHistory(kw)
  showSearchPanel.value = false
  selectedSub.value = ''
}

function applyKeyword(w: string) {
  keywordInput.value = w
  handleSearch()
}

// 16 大全品类
const MAIN_CATEGORIES = [
  { code: 'PHONE', name: '手机数码', icon: '📱' },
  { code: 'LAPTOP', name: '电脑办公', icon: '💻' },
  { code: 'APPLIANCE', name: '家用电器', icon: '🧺' },
  { code: 'CLOTHING', name: '潮流服饰', icon: '👕' },
  { code: 'BEAUTY', name: '美妆个护', icon: '💄' },
  { code: 'FOOD', name: '食品生鲜', icon: '🍎' },
  { code: 'HOME', name: '居家生活', icon: '🛋️' },
  { code: 'SPORTS', name: '运动户外', icon: '⚽' },
  { code: 'BAGS', name: '鞋靴箱包', icon: '🎒' },
  { code: 'JEWELRY', name: '钟表配饰', icon: '💎' },
  { code: 'MATERNAL', name: '母婴玩具', icon: '🧸' },
  { code: 'CAR', name: '汽车用品', icon: '🚗' },
  { code: 'PET', name: '宠物生活', icon: '🐾' },
  { code: 'HEALTH', name: '医药保健', icon: '🩺' },
  { code: 'BOOK', name: '图书文娱', icon: '📚' },
  { code: 'HOBBY', name: '乐器潮玩', icon: '🎸' },
]

const CATEGORY_SUB_TAGS: Record<string, string[]> = {
  PHONE: ['全部', '手机', '耳机', '手表', '充电配件', '无人机', '摄影摄像'],
  LAPTOP: ['全部', '笔记本', '键盘', '鼠标', '显示器', '桌搭', '拓展坞'],
  APPLIANCE: ['全部', '空气净化', '咖啡机', '扫拖机', '厨房小电', '吸尘器'],
  CLOTHING: ['全部', '卫衣', '冲锋衣', '休闲裤', '抓绒外套', '夹克', '衬衫'],
  BEAUTY: ['全部', '精华', '吹风机', '香水', '护手霜', '面霜'],
  FOOD: ['全部', '水果', '牛排', '咖啡', '海鲜'],
  HOME: ['全部', '工学椅', '香薰', '桌搭', '家纺', '家具'],
  SPORTS: ['全部', '跑鞋', '露营装备', '瑜伽', '运动手表'],
  BAGS: ['全部', '拉杆箱', '德训鞋', '双肩包', '钱包', '运动鞋'],
  JEWELRY: ['全部', '机械表', '眼镜', '腕表', '项链'],
  MATERNAL: ['全部', '积木', '推车', '玩偶', '喂养'],
  CAR: ['全部', '行车记录仪', '车用支架', '充气泵', '车用香薰'],
  PET: ['全部', '猫粮', '智能用品', '宠物零食', '饮水机'],
  HEALTH: ['全部', '鱼油', '关节养护', '医疗器械', '助眠'],
  BOOK: ['全部', '艺术设计', '电子书', '文具', '钢笔'],
  HOBBY: ['全部', '电钢琴', '尤克里里', '潮玩模型', '编曲设备'],
}

const activeCategoryCode = ref((route.query.category as string) || 'PHONE')
const selectedSub = ref('')

const currentSubcategories = computed(() => {
  return CATEGORY_SUB_TAGS[activeCategoryCode.value] || ['全部']
})

// 对应当前分类拥有的品牌
const currentCategoryBrands = computed(() => {
  const set = new Set<string>()
  for (const p of products.value) {
    if (p.brand && (p.category === activeCategoryCode.value || p.category === MAIN_CATEGORIES.find(c => c.code === activeCategoryCode.value)?.name)) {
      set.add(p.brand)
    }
  }
  return Array.from(set)
})

function selectCategory(code: string) {
  activeCategoryCode.value = code
  selectedSub.value = ''
  selectedBrand.value = ''
  keywordInput.value = ''
  searchKeyword.value = ''
}

function selectSubcategory(sub: string) {
  selectedSub.value = sub === '全部' ? '' : sub
}

function setSort(s: 'default' | 'sales_desc' | 'rating') {
  sort.value = s
}

// 价格排序（点击仅在升序与降序间循环，双三角指示器一眼辨认）
function togglePrice() {
  if (sort.value === 'price_asc') {
    sort.value = 'price_desc'
  } else {
    sort.value = 'price_asc'
  }
}

function setQuickPrice(min: number, max: number) {
  filterMinPrice.value = min
  filterMaxPrice.value = max
}

function resetDrawerFilters() {
  filterMinPrice.value = ''
  filterMaxPrice.value = ''
  selectedBrand.value = ''
  filterFreeShipping.value = false
  filterDiscountOnly.value = false
  filterInStockOnly.value = false
}

function resetAllFilters() {
  resetDrawerFilters()
  selectedSub.value = ''
  keywordInput.value = ''
  searchKeyword.value = ''
  sort.value = 'default'
}

const appliedFilterCount = computed(() => {
  let c = 0
  if (filterMinPrice.value !== '' || filterMaxPrice.value !== '') c++
  if (selectedBrand.value) c++
  if (filterFreeShipping.value) c++
  if (filterDiscountOnly.value) c++
  if (filterInStockOnly.value) c++
  return c
})

// 过滤后的全量商品列表
const filteredProducts = computed(() => {
  let list = [...products.value]

  // The server owns keyword/category matching (including selling-point matches).
  // Editing an unsubmitted input must not discard the previous server response.
  if (selectedSub.value) {
    const sk = selectedSub.value.toLowerCase()
    list = list.filter(
      (p) =>
        p.name.toLowerCase().includes(sk) ||
        (p.subCategory && p.subCategory.toLowerCase().includes(sk))
    )
  }

  if (selectedBrand.value) {
    list = list.filter((p) => p.brand === selectedBrand.value)
  }

  if (filterMinPrice.value !== '') {
    list = list.filter((p) => p.price >= Number(filterMinPrice.value))
  }
  if (filterMaxPrice.value !== '') {
    list = list.filter((p) => p.price <= Number(filterMaxPrice.value))
  }

  if (filterDiscountOnly.value) {
    list = list.filter((p) => p.tag === '爆款' || p.tag === '热销' || p.tag === '特惠')
  }

  // 排序
  if (sort.value === 'sales_desc') {
    list.sort((a, b) => (b.sales || 0) - (a.sales || 0))
  } else if (sort.value === 'price_asc') {
    list.sort((a, b) => a.price - b.price)
  } else if (sort.value === 'price_desc') {
    list.sort((a, b) => b.price - a.price)
  } else if (sort.value === 'rating') {
    list.sort((a, b) => (b.sales || 0) * 1.5 - (a.sales || 0))
  }

  return list
})

// 瀑布流左列与右列
const leftColProducts = computed(() => {
  return filteredProducts.value.filter((_, idx) => idx % 2 === 0)
})

const rightColProducts = computed(() => {
  return filteredProducts.value.filter((_, idx) => idx % 2 === 1)
})

// 方式 1：点击商品直接进入独立完整的商品详情大页
function goToDetail(id: number) {
  router.push(`/products/${id}`)
}

function formatSales(sales?: number): string {
  const s = Number(sales) || 0
  if (s < 100) return String(s)
  if (s < 1000) return `${Math.floor(s / 100) * 100}+`
  if (s < 10000) return `${Math.floor(s / 1000)}000+`
  return `${Math.floor(s / 10000)}w+`
}

async function loadCatalogPage() {
  if (catalogLoading.value || catalogFinished.value || disposed) return
  const generation = catalogGeneration
  catalogLoading.value = true
  catalogError.value = false
  try {
    const result = await apiProducts({
      page: catalogPage, size: 24,
      ...(searchKeyword.value.trim() ? { keyword: searchKeyword.value.trim() } : {
        category: MAIN_CATEGORIES.find(c => c.code === activeCategoryCode.value)?.name || activeCategoryCode.value,
        ...(selectedBrand.value ? { keyword: selectedBrand.value } : {}),
      }),
      ...(filterMinPrice.value !== '' ? { minPrice: filterMinPrice.value } : {}),
      ...(filterMaxPrice.value !== '' ? { maxPrice: filterMaxPrice.value } : {}),
      sort: sort.value,
    })
    if (disposed || generation !== catalogGeneration) return
    products.value.push(...result.records)
    catalogFinished.value = !result.records.length || products.value.length >= result.total
    catalogPage++
  } catch {
    if (!disposed && generation === catalogGeneration) catalogError.value = true
  } finally {
    if (generation === catalogGeneration) catalogLoading.value = false
  }
}

function reloadCatalog() {
  catalogGeneration++
  catalogPage = 1
  products.value = []
  catalogFinished.value = false
  catalogLoading.value = false
  void loadCatalogPage()
}
watch([searchKeyword, activeCategoryCode, selectedBrand, filterMinPrice, filterMaxPrice, sort], reloadCatalog, { immediate: true })
watch(() => route.query.keyword, value => { keywordInput.value = typeof value === 'string' ? value : ''; searchKeyword.value = keywordInput.value })
onUnmounted(() => { disposed = true; catalogGeneration++ })

watch(
  () => route.query.category,
  (cat) => {
    if (cat && typeof cat === 'string') {
      activeCategoryCode.value = cat
    }
  }
)
</script>

<style scoped>
.category-page-mode-b {
  min-height: 100vh;
  background: var(--mall-page-bg, #fafafa);
  padding-bottom: 70px;
}

/* ================= 顶部唯一搜索栏 (0px 紧贴页面顶部) ================= */
.cat-search-bar-wrap {
  position: sticky;
  top: 0;
  z-index: 50;
  background: rgba(255, 255, 255, 0.98);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--mall-border-light, #f4f4f5);
  display: flex;
  align-items: center;
  height: 52px;
  padding: 0 16px;
}

html.dark .cat-search-bar-wrap {
  background: rgba(18, 18, 21, 0.98);
  border-bottom-color: var(--mall-border, #27272a);
}

.cat-search-box {
  width: 100%;
  max-width: var(--mall-container, 1240px);
  margin: 0 auto;
  display: flex;
  align-items: center;
  height: 38px;
  background: var(--mall-surface-2, #f4f4f5);
  border: 1px solid var(--mall-border, #e4e4e7);
  border-radius: 9999px;
  padding: 0 4px 0 14px;
}

.cs-icon {
  color: #a1a1aa;
}

.cs-input {
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
  font-size: 13px;
  color: inherit;
  padding: 0 8px;
}

.cs-clear-input {
  border: none;
  background: transparent;
  color: #a1a1aa;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
}

.cs-submit-btn {
  border: none;
  background: #18181b;
  color: #ffffff;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 16px;
  border-radius: 9999px;
  cursor: pointer;
}

html.dark .cs-submit-btn {
  background: #ffffff;
  color: #18181b;
}

/* 搜索展开浮窗 */
.search-overlay-panel {
  position: absolute;
  top: 52px;
  left: 16px;
  right: 16px;
  max-width: 620px;
  margin: 0 auto;
  background: var(--mall-surface, #ffffff);
  border: 1px solid var(--mall-border, #e4e4e7);
  border-radius: 12px;
  padding: 16px 20px;
  box-shadow: 0 16px 36px -4px rgba(0, 0, 0, 0.15);
  z-index: 60;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sb-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.sb-title {
  font-size: 13px;
  font-weight: 700;
  color: #18181b;
}

html.dark .sb-title {
  color: #f4f4f5;
}

.sb-clear {
  border: none;
  background: transparent;
  color: #a1a1aa;
  font-size: 12px;
  cursor: pointer;
}

.sb-clear:hover {
  color: var(--mall-price, #e11d48);
}

.sb-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.history-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #52525b;
  background: var(--mall-surface-2, #f4f4f5);
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
}

html.dark .history-chip {
  color: #cbd5e1;
}

.history-chip:hover {
  color: var(--el-color-primary, #2563eb);
}

.del-chip {
  font-style: normal;
  color: #a1a1aa;
  font-size: 13px;
}

.del-chip:hover {
  color: #e11d48;
}

.sb-empty {
  font-size: 12px;
  color: #a1a1aa;
}

.guess-badge {
  font-size: 10px;
  font-weight: 700;
  color: #e11d48;
  background: #fee2e2;
  padding: 1px 6px;
  border-radius: 4px;
}

.guess-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.guess-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  color: #3f3f46;
}

html.dark .guess-item {
  color: #cbd5e1;
}

.guess-item:hover {
  background: var(--mall-surface-2, #f4f4f5);
  color: var(--el-color-primary, #2563eb);
}

.guess-rank {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  background: #e4e4e7;
  color: #71717a;
  font-size: 10px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.guess-rank.top-rank {
  background: #ffe4e6;
  color: #e11d48;
}

/* ================= 一级品类横向滑动栏 ================= */
.main-cat-bar-wrap {
  position: sticky;
  top: 52px;
  z-index: 40;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--mall-border-light, #f4f4f5);
}

html.dark .main-cat-bar-wrap {
  background: rgba(18, 18, 21, 0.95);
  border-bottom-color: var(--mall-border, #27272a);
}

.main-cat-bar {
  max-width: var(--mall-container, 1240px);
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 4px;
  overflow-x: auto;
  scrollbar-width: none;
  padding: 5px 10px;
}

.main-cat-bar::-webkit-scrollbar {
  display: none;
}

.main-cat-tab {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  font-weight: 600;
  color: #71717a;
  padding: 4px 9px;
  border-radius: 9999px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s ease;
}

.mct-icon {
  font-size: 14px;
}

.main-cat-tab:hover {
  color: #18181b;
}

html.dark .main-cat-tab:hover {
  color: #ffffff;
}

.main-cat-tab.active {
  background: #18181b;
  color: #ffffff;
  font-weight: 600;
}

html.dark .main-cat-tab.active {
  background: #ffffff;
  color: #18181b;
}

/* ================= 二级细分子分类扁平胶囊栏 ================= */
.sub-cat-bar-wrap {
  background: var(--mall-surface, #ffffff);
  border-bottom: 1px solid var(--mall-border-light, #f4f4f5);
}

.sub-cat-bar {
  max-width: var(--mall-container, 1240px);
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 6px;
  overflow-x: auto;
  scrollbar-width: none;
  padding: 8px 16px;
}

.sub-cat-bar::-webkit-scrollbar {
  display: none;
}

.sub-cat-chip {
  font-size: 12px;
  color: #52525b;
  background: var(--mall-surface-2, #f4f4f5);
  padding: 4px 12px;
  border-radius: 9999px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s ease;
}

html.dark .sub-cat-chip {
  color: #cbd5e1;
}

.sub-cat-chip:hover {
  color: #18181b;
}

html.dark .sub-cat-chip:hover {
  color: #ffffff;
}

.sub-cat-chip.active {
  background: var(--mall-surface-2, #e4e4e7);
  color: #18181b;
  font-weight: 700;
}

html.dark .sub-cat-chip.active {
  background: #27272a;
  color: #ffffff;
}

/* ================= 排序与筛选栏 ================= */
.filter-sort-bar-wrap {
  background: var(--mall-surface, #ffffff);
  border-bottom: 1px solid var(--mall-border-light, #f4f4f5);
}

.filter-sort-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
}

.fsb-left {
  display: flex;
  align-items: center;
  gap: 16px;
  overflow-x: auto;
  scrollbar-width: none;
}

.fsb-left::-webkit-scrollbar {
  display: none;
}

.fsb-tab {
  border: none;
  background: transparent;
  font-size: 13px;
  color: #71717a;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 4px 2px;
  white-space: nowrap;
  transition: color 0.15s ease;
}

.fsb-tab.active {
  color: var(--mall-price, #e11d48);
  font-weight: 700;
}

.fsb-arrow,
.fsb-star {
  font-size: 11px;
}

/* 价格双三角指示器 */
.price-fsb-tab {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.price-arrows-stack {
  display: inline-flex;
  flex-direction: column;
  gap: 1px;
  font-size: 8px;
  line-height: 1;
}

.arrow-up,
.arrow-down {
  color: #d4d4d8;
  transition: color 0.15s ease;
}

.arrow-up.arrow-active,
.arrow-down.arrow-active {
  color: var(--mall-price, #e11d48);
  font-weight: bold;
}

.fsb-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.location-btn {
  border: 1px solid var(--mall-border, #e4e4e7);
  background: var(--mall-surface-2, #f4f4f5);
  color: #52525b;
  font-size: 12px;
  font-weight: 500;
  padding: 4px 10px;
  border-radius: 9999px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

html.dark .location-btn {
  color: #cbd5e1;
}

.filter-drawer-btn {
  border: 1px solid var(--mall-border, #e4e4e7);
  background: var(--mall-surface-2, #f4f4f5);
  color: #18181b;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 9999px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  position: relative;
}

html.dark .filter-drawer-btn {
  color: #ffffff;
}

.filter-count-badge {
  background: var(--mall-price, #e11d48);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  width: 16px;
  height: 16px;
  border-radius: 9999px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* ================= 全宽双列瀑布流 (Masonry Waterfall) ================= */
.waterfall-stream-main {
  margin-top: 14px;
}

.pdd-waterfall-layout {
  display: flex;
  gap: 12px;
  max-width: 860px;
  margin: 0 auto;
  align-items: flex-start;
}

.waterfall-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stream-product-card {
  background: var(--mall-surface, #ffffff);
  border: 1px solid var(--mall-border-light, #f4f4f5);
  border-radius: var(--mall-radius, 10px);
  overflow: hidden;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.stream-product-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--mall-shadow-hover);
  border-color: var(--mall-border, #e4e4e7);
}

.spc-pic-wrap {
  position: relative;
  width: 100%;
  background: var(--mall-surface-2, #f4f4f5);
  overflow: hidden;
}

.spc-img {
  width: 100%;
  height: 100%;
  transition: transform 0.4s ease;
}

.stream-product-card:hover .spc-img :deep(img) {
  transform: scale(1.04);
}


.spc-info {
  padding: 10px 12px 12px;
  display: flex;
  flex-direction: column;
}

.spc-brand {
  font-size: 10px;
  font-weight: 700;
  color: #a1a1aa;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 3px;
}

.spc-title {
  font-size: 13px;
  font-weight: 600;
  color: #18181b;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

html.dark .spc-title {
  color: #f4f4f5;
}

.spc-bottom {
  margin-top: 10px;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.spc-price-box {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.spc-price {
  font-size: 18px;
  font-weight: 800;
  color: var(--mall-price, #e11d48);
  letter-spacing: -0.02em;
}

.spc-price i {
  font-style: normal;
  font-size: 12px;
  margin-right: 1px;
}


.spc-sales {
  font-size: 11px;
  color: #a1a1aa;
}

.spc-skeleton {
  width: 100%;
  height: 100%;
}

.spc-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  font-weight: 700;
  color: #a1a1aa;
}

.stream-empty {
  text-align: center;
  padding: 80px 0;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 8px;
}

.empty-text {
  font-size: 13px;
  color: #a1a1aa;
  margin-bottom: 16px;
}

.stream-end {
  text-align: center;
  font-size: 12px;
  color: #a1a1aa;
  padding: 36px 0 24px;
}

/* ================= 筛选抽屉 ================= */
.drawer-filter-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 10px 4px;
}

.df-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.df-title {
  font-size: 13px;
  font-weight: 700;
  color: #18181b;
}

html.dark .df-title {
  color: #f4f4f5;
}

.price-input-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  box-sizing: border-box;
}

.pi-input {
  flex: 1 1 0%;
  min-width: 0 !important;
  width: 0 !important;
  box-sizing: border-box;
  height: 36px;
  border: 1px solid var(--mall-border, #e4e4e7);
  background: var(--mall-surface-2, #f4f4f5);
  border-radius: 6px;
  padding: 0 8px;
  font-size: 13px;
  outline: none;
  color: inherit;
  text-align: center;
}

.pi-input:focus {
  border-color: #18181b;
  background: var(--mall-surface, #ffffff);
}

.pi-dash {
  color: #a1a1aa;
}

.price-quick-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.pqt-tag {
  font-size: 11px;
  color: #52525b;
  background: var(--mall-surface-2, #f4f4f5);
  padding: 3px 10px;
  border-radius: 4px;
  cursor: pointer;
}

.brand-chips-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.brand-filter-chip {
  font-size: 12px;
  color: #52525b;
  background: var(--mall-surface-2, #f4f4f5);
  padding: 4px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.brand-filter-chip.active {
  background: #18181b;
  color: #ffffff;
}

html.dark .brand-filter-chip.active {
  background: #ffffff;
  color: #18181b;
}

.switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: #52525b;
}

html.dark .switch-row {
  color: #cbd5e1;
}

.df-footer {
  margin-top: 30px;
  display: grid;
  grid-template-columns: 1fr 1.5fr;
  gap: 10px;
}

.df-reset-btn {
  height: 38px;
  border: 1px solid var(--mall-border, #e4e4e7);
  background: var(--mall-surface-2, #f4f4f5);
  border-radius: 9999px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  color: inherit;
}

.df-confirm-btn {
  height: 38px;
  border: none;
  background: #18181b;
  color: #ffffff;
  border-radius: 9999px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

html.dark .df-confirm-btn {
  background: #ffffff;
  color: #18181b;
}

@media (max-width: 768px) {
  .pdd-waterfall-layout {
    gap: 8px;
  }
  .waterfall-col {
    gap: 8px;
  }
  .spc-info {
    padding: 8px 10px 10px;
  }
  .spc-title {
    font-size: 12px;
  }
  .spc-price {
    font-size: 16px;
  }
  .filter-sort-bar {
    padding: 6px 8px;
    gap: 4px;
  }
  .fsb-left {
    gap: 8px;
  }
  .fsb-tab {
    font-size: 11px !important;
    padding: 2px 1px !important;
  }
  .location-btn,
  .filter-drawer-btn {
    font-size: 10px !important;
    padding: 3px 6px !important;
  }
}
</style>
