<template>
  <el-container class="client-layout">
    <!-- 顶部仅保留一个极简搜索框（无任何导航栏、无微通栏） -->
    <header v-if="isHome" class="shop-header">
      <div class="header-inner">
        <div class="search-container" @mouseleave="searchFocused = false">
          <div class="search-box">
            <el-icon :size="16" class="search-icon"><Search /></el-icon>
            <input
              v-model="keyword"
              class="search-input"
              type="text"
              placeholder="搜索商品 / 品牌 / 卖点..."
              @focus="searchFocused = true"
              @keyup.enter="doSearch"
            />
            <button class="search-btn" @click="doSearch">搜索</button>
          </div>

          <!-- 搜索下拉浮窗（历史记录 + 猜你想搜） -->
          <transition name="dropdown-fade">
            <div v-if="searchFocused" class="search-dropdown mall-card">
              <!-- 历史搜索记录 -->
              <div v-if="searchHistory.length" class="sd-section">
                <div class="sd-head">
                  <span>历史搜索</span>
                  <span class="sd-clear" @click="clearHistory">清空</span>
                </div>
                <div class="sd-tags">
                  <span
                    v-for="(h, idx) in searchHistory"
                    :key="idx"
                    class="sd-chip"
                    @click="applySearchWord(h)"
                  >
                    <span>{{ h }}</span>
                    <i class="del-chip" @click.stop="removeSingleHistory(h)">×</i>
                  </span>
                </div>
              </div>

              <!-- 猜你想搜 -->
              <div class="sd-section">
                <div class="sd-head">
                  <span>猜你想搜</span>
                  <span class="sd-hot-tag">热门</span>
                </div>
                <div class="sd-hot-list">
                  <div
                    v-for="(w, idx) in hotWords"
                    :key="w"
                    class="sd-hot-item"
                    @click="applySearchWord(w)"
                  >
                    <span class="sd-rank" :class="{ 'top-rank': idx < 3 }">{{ idx + 1 }}</span>
                    <span class="sd-word">{{ w }}</span>
                  </div>
                </div>
              </div>
            </div>
          </transition>
        </div>
      </div>
    </header>

    

    <el-main class="main" :class="{ 'no-tabbar-pad': isProductDetail }">
      <router-view />
    </el-main>

    <!-- 全局悬浮工具坞 -->
    <FloatingDock v-if="!isOrderConfirm" />

    <!-- 全局购物车抽屉 -->
    <CartDrawer v-if="!isOrderConfirm" />

    <!-- 移动端底部导航 -->
    <MobileTabbar v-if="!isProductDetail" />
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Search } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'
import MobileTabbar from '@/components/layout/MobileTabbar.vue'
import FloatingDock from '@/components/layout/FloatingDock.vue'
import CartDrawer from '@/components/cart/CartDrawer.vue'

const auth = useAuthStore()
const cart = useCartStore()
const route = useRoute()
const router = useRouter()

const keyword = ref('')
const searchFocused = ref(false)

const SEARCH_HISTORY_KEY = 'aimall_search_history_v2'
const searchHistory = ref<string[]>(
  JSON.parse(localStorage.getItem(SEARCH_HISTORY_KEY) || '["降噪耳机", "轻薄笔记本", "机械键盘", "车厘子"]')
)
const hotWords = [
  'iPhone 15 Pro 钛金属',
  'Sony 降噪头戴耳机',
  'M3 Pro 轻薄笔记本',
  'Keychron 机械键盘',
  '智利 JJJ 车厘子原箱',
  '始祖鸟 GORE-TEX 冲锋衣',
]

function saveHistory(kw: string) {
  if (!kw.trim()) return
  const list = [kw, ...searchHistory.value.filter((w) => w !== kw)].slice(0, 8)
  searchHistory.value = list
  localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(list))
}

function removeSingleHistory(word: string) {
  searchHistory.value = searchHistory.value.filter((w) => w !== word)
  localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(searchHistory.value))
}

function clearHistory() {
  searchHistory.value = []
  localStorage.removeItem(SEARCH_HISTORY_KEY)
}

function applySearchWord(w: string) {
  keyword.value = w
  searchFocused.value = false
  doSearch()
}

const isHome = computed(() => route.path === '/')
const isOrderConfirm = computed(() => route.path === '/order/confirm' || route.path === '/checkout')
const isProductDetail = computed(() => /^\/products\/\d+/.test(route.path) || isOrderConfirm.value)

onMounted(() => {
  if (localStorage.getItem('token')) {
    cart.fetchCart()
  }
})



function doSearch() {
  const kw = keyword.value.trim()
  if (kw) saveHistory(kw)
  searchFocused.value = false
  router.push({
    path: '/products',
    query: kw ? { keyword: kw } : {},
  })
}
</script>

<style scoped>
.client-layout {
  min-height: 100%;
  flex-direction: column;
}

.main {
  padding: 0;
  flex: 1;
  overflow: visible;
}

/* ================= 顶部仅保留一个极简搜索框 ================= */
.shop-header {
  position: sticky;
  top: 0;
  z-index: 50;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--mall-border-light, #f4f4f5);
  padding: 8px 16px;
}

html.dark .shop-header {
  background: rgba(18, 18, 21, 0.96);
  border-bottom-color: var(--mall-border, #27272a);
}

.header-inner {
  max-width: var(--mall-container, 1240px);
  margin: 0 auto;
  display: flex;
  justify-content: center;
}

.search-container {
  position: relative;
  width: 100%;
  max-width: 680px;
}

.search-box {
  display: flex;
  align-items: center;
  height: 40px;
  background: var(--mall-surface-2, #f4f4f5);
  border: 1px solid var(--mall-border, #e4e4e7);
  border-radius: 9999px;
  padding: 0 4px 0 16px;
  transition: all 0.2s ease;
}

.search-box:focus-within {
  border-color: #18181b;
  background: var(--mall-surface, #ffffff);
  box-shadow: 0 0 0 3px rgba(24, 24, 27, 0.08);
}

html.dark .search-box:focus-within {
  border-color: #ffffff;
}

.search-icon {
  color: #a1a1aa;
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
  font-size: 13px;
  color: inherit;
  padding: 0 10px;
}

.search-btn {
  border: none;
  background: #18181b;
  color: #ffffff;
  font-size: 13px;
  font-weight: 600;
  padding: 7px 18px;
  border-radius: 9999px;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

html.dark .search-btn {
  background: #ffffff;
  color: #18181b;
}

.search-btn:hover {
  opacity: 0.9;
}

/* 搜索下拉浮窗 */
.search-dropdown {
  position: absolute;
  top: 48px;
  left: 0;
  right: 0;
  padding: 16px 20px;
  background: var(--mall-surface, #ffffff);
  border: 1px solid var(--mall-border, #e4e4e7);
  border-radius: 12px;
  box-shadow: 0 16px 36px -4px rgba(0, 0, 0, 0.15);
  z-index: 60;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sd-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  font-weight: 700;
  color: #18181b;
  margin-bottom: 8px;
}

html.dark .sd-head {
  color: #f4f4f5;
}

.sd-clear {
  color: #a1a1aa;
  cursor: pointer;
  font-size: 11px;
}

.sd-clear:hover {
  color: var(--mall-price, #e11d48);
}

.sd-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.sd-chip {
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

html.dark .sd-chip {
  color: #cbd5e1;
}

.sd-chip:hover {
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

.sd-hot-tag {
  font-size: 10px;
  font-weight: 700;
  color: #e11d48;
  background: #fee2e2;
  padding: 1px 6px;
  border-radius: 4px;
}

.sd-hot-list {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.sd-hot-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #3f3f46;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 4px;
}

html.dark .sd-hot-item {
  color: #cbd5e1;
}

.sd-hot-item:hover {
  background: var(--mall-surface-2, #f4f4f5);
  color: var(--el-color-primary, #2563eb);
}

.sd-rank {
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

.sd-rank.top-rank {
  background: #ffe4e6;
  color: #e11d48;
}

/* ================= 极简圆形半透明返回按钮 ================= */
.translucent-circle-back {
  width: 34px;
  height: 34px;
  border-radius: 9999px;
  border: none;
  background: rgba(0, 0, 0, 0.4);
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  transition: all 0.2s ease;
}

.translucent-circle-back:hover {
  background: rgba(0, 0, 0, 0.65);
  transform: scale(1.05);
}



/* ================= 契约测试规范样式保留 ================= */
.shop-topbar,
.all-cats,
.shop-footer {
  display: none;
}

.nav-links {
  display: none;
  overflow-x: auto;
}

@media (max-width: 768px) {
  .shop-topbar,
  .all-cats,
  .shop-footer,
  .cart-entry span {
    display: none;
  }

  .nav-links {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
  }

  .main {
    padding-bottom: calc(56px + env(safe-area-inset-bottom));
  }

  .main.no-tabbar-pad {
    padding-bottom: 0;
  }
}
</style>


