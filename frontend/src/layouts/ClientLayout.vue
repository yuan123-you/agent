<template>
  <el-container class="client-layout">
    <!-- ============ 顶部通栏（桌面/平板） ============ -->
    <div v-if="isHome" class="shop-topbar">
      <div class="topbar-inner">
        <span class="topbar-slogan">AI Mall 品牌正品 · 7 天无理由退货 · 极速退款</span>
        <div class="topbar-links">
          <ThemeToggle />
          <span class="tb-link" @click="$router.push('/assistant')">AI 助手</span>
          <span v-if="auth.isCustomer" class="tb-link" @click="$router.push('/orders')">我的订单</span>
          <span v-if="auth.isCustomer" class="tb-link" @click="$router.push('/favorites')">我的收藏</span>
          <el-dropdown v-if="auth.user" @command="onCommand">
            <span class="tb-link user-name">{{ auth.user.nickname }}</span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人中心</el-dropdown-item>
                <el-dropdown-item command="cart">我的购物车</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <span v-else class="tb-link" @click="$router.push('/login')">登录 / 注册</span>
        </div>
      </div>
    </div>

    <!-- ============ 主头部（大 Logo + 大搜索 + 购物车） ============ -->
    <header v-if="isHome" class="shop-header">
      <div class="header-inner">
        <div class="logo" @click="$router.push('/')">
          <span class="logo-badge">AI</span>
          <div class="logo-words">
            <span class="logo-text">AI Mall</span>
            <span class="logo-sub">正品好货 · AI 甄选</span>
          </div>
        </div>
        <div class="search-area">
          <div class="search-box">
            <input
              v-model="keyword"
              class="search-input"
              type="text"
              placeholder="搜索商品 / 品牌 / 卖点"
              @keyup.enter="doSearch"
            />
            <button class="search-btn" @click="doSearch">
              <el-icon :size="18"><Search /></el-icon>
              <span>搜索</span>
            </button>
          </div>
          <div class="search-hot">
            <span v-for="c in hotWords" :key="c" class="hot-word" @click="searchWord(c)">{{ c }}</span>
          </div>
        </div>
        <button class="cart-entry" @click="$router.push('/cart')">
          <el-icon :size="20"><ShoppingCart /></el-icon>
          <span>我的购物车</span>
          <i v-if="cartCount > 0" class="cart-badge">{{ cartCount > 99 ? '99+' : cartCount }}</i>
        </button>
      </div>
    </header>

    <!-- ============ 主题色导航条（仅首页；含全部分类下拉） ============ -->
    <nav v-if="isHome" class="shop-nav">
      <div class="nav-inner">
        <div class="all-cats" @mouseenter="catsOpen = true" @mouseleave="catsOpen = false">
          <div class="all-cats-label">
            <el-icon :size="16"><Menu /></el-icon>
            <span>全部商品分类</span>
          </div>
          <transition name="cats-fade">
            <div v-if="catsOpen" class="cats-panel">
              <div v-for="c in navCats" :key="c.key" class="cats-row"
                @click="goCategory(c); catsOpen = false">
                <span class="cats-icon">{{ c.icon || '🛍️' }}</span>
                <span class="cats-name">{{ c.name }}</span>
                <span class="cats-arrow">›</span>
              </div>
            </div>
          </transition>
        </div>
        <div class="nav-links">
          <span class="nav-link" :class="{ active: route.path === '/' }" @click="$router.push('/')">首页</span>
          <span class="nav-link" @click="$router.push('/products')">全部商品</span>
          <span class="nav-link nav-hot" @click="scrollToSeckill">限时秒杀 ⚡</span>
          <span class="nav-link" @click="scrollToCoupons">领券中心 🎫</span>
          <span class="nav-link" @click="$router.push('/assistant')">AI 助手</span>
        </div>
        <span class="nav-tip desktop-only">正品保障 · 极速发货</span>
      </div>
    </nav>

    <!-- ============ 子页面精简头部 ============ -->
    <header v-else class="sub-header">
      <el-button :icon="ArrowLeft" circle size="small" @click="goBack" />
      <span class="sub-title">{{ subTitle }}</span>
      <div class="spacer" />
      <ThemeToggle />
      <el-button text :type="route.path.startsWith('/assistant') ? 'primary' : ''"
        @click="$router.push('/assistant')">
        <el-icon><ChatDotRound /></el-icon>
      </el-button>
      <el-dropdown @command="onCommand">
        <span class="user-chip">
          <el-avatar :size="26" class="user-avatar">{{ (auth.user?.nickname || 'U').slice(0, 1) }}</el-avatar>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="home">回首页</el-dropdown-item>
            <el-dropdown-item command="cart">购物车</el-dropdown-item>
            <el-dropdown-item command="profile">个人中心</el-dropdown-item>
            <el-dropdown-item command="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </header>

    <el-main class="main">
      <router-view />
    </el-main>

    <footer v-if="isHome" class="shop-footer">
      <div class="footer-inner">
        <div class="footer-brand">
          <span class="logo-badge">AI</span>
          <span>AI Mall · 智能电商平台 · 演示环境，无真实交易</span>
        </div>
        <div class="footer-links">
          <span @click="$router.push('/assistant')">AI 助手</span>
          <span @click="$router.push('/orders')">我的订单</span>
          <span @click="$router.push('/profile')">个人中心</span>
        </div>
      </div>
    </footer>

    <!-- 移动端底部导航（商品详情页使用专属购买栏，不展示全站通用 Tabbar） -->
    <MobileTabbar v-if="!isProductDetail" />
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ChatDotRound, Menu, Search, ShoppingCart } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { CATEGORIES, categoryIcon, categoryName } from '@/constants/categories'
import { apiCartList, apiCatalogCategories } from '@/api'
import type { CategoryVO } from '@/types/api'
import MobileTabbar from '@/components/layout/MobileTabbar.vue'
import ThemeToggle from '@/components/layout/ThemeToggle.vue'

interface NavCat { key: string; name: string; icon: string; query: Record<string, string> }

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const keyword = ref('')
const catsOpen = ref(false)
const cartCount = ref(0)

/** 仅首页显示完整电商头部；其余页面用精简子头部 */
const isHome = computed(() => route.path === '/')

/** 商品详情页隐藏通用 Tabbar，交由商品详情页底部专属操作栏承载 */
const isProductDetail = computed(() => /^\/products\/\d+/.test(route.path))

// 分类导航：商城目录（nav_status=1）优先，接口为空/失败时回落内置常量
const navCats = ref<NavCat[]>(
  CATEGORIES.map((c) => ({
    key: c.code,
    name: c.name,
    icon: c.icon,
    query: { category: c.code },
  })),
)

const hotWords = computed(() => navCats.value.slice(0, 5).map((c) => c.name))

onMounted(async () => {
  try {
    const tree = await apiCatalogCategories()
    if (tree && tree.length) {
      navCats.value = tree.slice(0, 16).map((c: CategoryVO) => ({
        key: String(c.id),
        name: categoryName(c.name),
        icon: c.icon || categoryIcon(c.name),
        query: { categoryId: String(c.id) },
      }))
    }
  } catch {
    /* 目录不可用时使用内置常量 */
  }
  // 购物车徽标（游客忽略 401）
  if (auth.isCustomer) {
    apiCartList().then((d) => (cartCount.value = d.items.length)).catch(() => {})
  }
})

const SUB_TITLES: Record<string, string> = {
  '/assistant': 'AI 购物助手',
  '/products': '商品列表',
  '/orders': '我的订单',
  '/cart': '购物车',
  '/favorites': '我的收藏',
  '/history': '浏览历史',
  '/profile': '个人中心',
}
const subTitle = computed(
  () => SUB_TITLES[route.path] || (route.path.startsWith('/products/') ? '商品详情' : 'AI Mall'),
)

function goBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/')
  }
}

function doSearch() {
  router.push({ path: '/products', query: keyword.value.trim() ? { keyword: keyword.value.trim() } : {} })
}

function searchWord(word: string) {
  router.push({ path: '/products', query: { keyword: word } })
}

function goCategory(c: NavCat) {
  router.push({ path: '/products', query: c.query })
}

function scrollToSeckill() {
  document.getElementById('seckill-zone')?.scrollIntoView({ behavior: 'smooth' })
}

function scrollToCoupons() {
  document.getElementById('coupon-zone')?.scrollIntoView({ behavior: 'smooth' })
}

async function onCommand(cmd: string) {
  if (cmd === 'home') {
    router.push('/')
  } else if (cmd === 'profile') {
    router.push('/profile')
  } else if (cmd === 'cart') {
    router.push('/cart')
  } else if (cmd === 'logout') {
    await auth.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.client-layout {
  height: 100%;
  flex-direction: column;
}

.main {
  padding: 0;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}

/* ================= 顶部通栏 ================= */
.shop-topbar {
  background: var(--mall-surface-2, #f7f8fa);
  border-bottom: 1px solid var(--el-border-color-lighter, #eceef2);
  font-size: 12px;
  color: var(--el-text-color-secondary, #6b7280);
}

.topbar-inner {
  max-width: var(--mall-container);
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 34px;
  padding: 0 16px;
}

.topbar-links {
  display: flex;
  align-items: center;
  gap: 14px;
}

.tb-link {
  cursor: pointer;
  transition: color 0.15s;
}

.tb-link:hover {
  color: var(--el-color-primary);
}

.user-name {
  max-width: 96px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  outline: none;
}

/* ================= 主头部 ================= */
.shop-header {
  background: var(--mall-surface, #fff);
  border-bottom: 1px solid var(--el-border-color-lighter, #eceef2);
}

.header-inner {
  max-width: var(--mall-container);
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 40px;
  height: 88px;
  padding: 0 16px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
  flex-shrink: 0;
}

.logo-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 46px;
  border-radius: 12px;
  background: var(--mall-gradient);
  color: #fff;
  font-size: 18px;
  font-weight: 800;
  box-shadow: var(--mall-shadow-float);
}

.logo-words {
  display: flex;
  flex-direction: column;
  line-height: 1.15;
}

.logo-text {
  font-size: 26px;
  font-weight: 800;
  background: var(--mall-gradient);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.logo-sub {
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
  letter-spacing: 2px;
}

/* 搜索区 */
.search-area {
  flex: 1;
  min-width: 0;
  max-width: 560px;
}

.search-box {
  display: flex;
  height: 40px;
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

.search-hot {
  display: flex;
  gap: 12px;
  margin-top: 6px;
  padding-left: 4px;
}

.hot-word {
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
  cursor: pointer;
}

.hot-word:hover {
  color: var(--el-color-primary);
}

/* 购物车入口 */
.cart-entry {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  height: 40px;
  padding: 0 18px;
  border: 1px solid var(--el-color-primary);
  border-radius: 4px;
  background: var(--mall-surface, #fff);
  color: var(--el-color-primary);
  font-size: 14px;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.15s;
}

.cart-entry:hover {
  background: var(--el-color-primary-light-9);
}

.cart-badge {
  position: absolute;
  top: -8px;
  right: -8px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: var(--mall-price, #e4393c);
  color: #fff;
  font-size: 11px;
  font-style: normal;
  line-height: 18px;
  text-align: center;
}

/* ================= 主题色导航条 ================= */
.shop-nav {
  background: var(--mall-gradient);
  box-shadow: var(--mall-shadow-float);
}

.nav-inner {
  max-width: var(--mall-container);
  margin: 0 auto;
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 16px;
  gap: 8px;
}

.all-cats {
  position: relative;
  height: 40px;
  width: 190px;
  flex-shrink: 0;
}

.all-cats-label {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 100%;
  padding: 0 16px;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.14);
  cursor: default;
}

.cats-panel {
  position: absolute;
  top: 40px;
  left: 0;
  z-index: 200;
  width: 190px;
  max-height: 460px;
  overflow-y: auto;
  background: var(--mall-surface, #fff);
  border: 1px solid var(--el-border-color-lighter, #eceef2);
  border-top: 0;
  box-shadow: var(--mall-shadow-hover);
}

.cats-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  height: 40px;
  font-size: 13px;
  color: var(--el-text-color-primary, #303133);
  cursor: pointer;
  transition: all 0.12s;
}

.cats-row:hover {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  padding-left: 18px;
}

.cats-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cats-arrow {
  color: var(--el-text-color-placeholder, #c0c4cc);
}

.cats-fade-enter-active,
.cats-fade-leave-active {
  transition: opacity 0.15s;
}

.cats-fade-enter-from,
.cats-fade-leave-to {
  opacity: 0;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.nav-link {
  padding: 0 16px;
  height: 40px;
  line-height: 40px;
  color: rgba(255, 255, 255, 0.92);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}

.nav-link:hover,
.nav-link.active {
  background: rgba(255, 255, 255, 0.16);
  color: #fff;
}

.nav-hot {
  color: #ffe98c;
}

.nav-tip {
  flex-shrink: 0;
  color: rgba(255, 255, 255, 0.75);
  font-size: 12px;
}

/* ================= 子页面精简头部 ================= */
.sub-header {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--mall-surface, #fff);
  border-bottom: 1px solid var(--el-border-color-lighter, #eceef2);
  height: 52px;
  padding: 0 16px;
}

.sub-title {
  font-weight: 600;
  font-size: 16px;
}

.sub-header .spacer {
  flex: 1;
}

.sub-header .user-chip {
  display: flex;
  align-items: center;
  cursor: pointer;
}

.user-avatar {
  background: var(--mall-gradient);
  color: #fff;
  font-weight: 600;
}

/* ================= 页脚 ================= */
.shop-footer {
  background: var(--mall-surface, #fff);
  border-top: 1px solid var(--el-border-color-lighter, #eceef2);
  margin-top: 24px;
}

.footer-inner {
  max-width: var(--mall-container);
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 16px;
  font-size: 13px;
  color: var(--el-text-color-secondary, #909399);
  flex-wrap: wrap;
  gap: 10px;
}

.footer-brand {
  display: flex;
  align-items: center;
  gap: 8px;
}

.footer-brand .logo-badge {
  width: 26px;
  height: 26px;
  font-size: 11px;
  border-radius: 7px;
}

.footer-links {
  display: flex;
  gap: 20px;
}

.footer-links span {
  cursor: pointer;
}

.footer-links span:hover {
  color: var(--el-color-primary);
}

/* ================= 平板 769-1199 ================= */
@media (max-width: 1199px) and (min-width: 769px) {
  .header-inner {
    gap: 20px;
    height: 72px;
  }

  .logo-text {
    font-size: 20px;
  }

  .nav-tip {
    display: none;
  }

  .all-cats {
    width: 160px;
  }
}

/* ================= 手机 ≤768 ================= */
@media (max-width: 768px) {
  .shop-topbar,
  .all-cats,
  .cart-entry span,
  .logo-words {
    display: none;
  }

  /* 手机端频道条：横向滑动 */
  .nav-inner {
    padding: 0 8px;
    height: 38px;
  }

  .nav-links {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
  }

  .nav-links::-webkit-scrollbar {
    display: none;
  }

  .nav-link {
    padding: 0 12px;
    font-size: 13px;
    height: 38px;
    line-height: 38px;
  }

  .header-inner {
    height: 54px;
    gap: 10px;
    padding: 0 12px;
  }

  .logo-badge {
    width: 34px;
    height: 34px;
    font-size: 14px;
    border-radius: 9px;
  }

  .search-area {
    max-width: none;
  }

  .search-box {
    height: 34px;
  }

  .search-btn {
    padding: 0 12px;
  }

  .cart-entry {
    height: 34px;
    padding: 0 10px;
    border-radius: 6px;
  }

  .main {
    padding-bottom: calc(56px + env(safe-area-inset-bottom));
  }
}
</style>
