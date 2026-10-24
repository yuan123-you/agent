<template>
  <el-container class="client-layout">
    <!-- 顶栏 + 分类导航条：仅首页显示 -->
    <template v-if="isHome">
      <el-header class="header">
        <div class="header-inner">
          <div class="logo" @click="$router.push('/')">
            <span class="logo-badge">AI</span>
            <span class="logo-text">Mall</span>
          </div>
          <div class="search-box">
            <el-input
              v-model="keyword"
              placeholder="搜索商品 / 品牌 / 卖点"
              clearable
              @keyup.enter="doSearch"
              @clear="doSearch"
            >
              <template #append>
                <el-button :icon="Search" @click="doSearch" />
              </template>
            </el-input>
            <!-- 桌面端搜索热词（点击直达分类） -->
            <div class="search-hints desktop-only">
              <span v-for="c in navCats.slice(0, 4)" :key="c.key" class="hint" @click="goCategory(c)">
                {{ c.name }}
              </span>
            </div>
          </div>
          <div class="quick-links">
            <el-button text :type="route.path.startsWith('/assistant') ? 'primary' : ''" @click="$router.push('/assistant')">
              <el-icon><ChatDotRound /></el-icon>
              <span class="link-text">AI 助手</span>
            </el-button>
            <el-button v-if="auth.isCustomer" text :type="route.path.startsWith('/orders') ? 'primary' : ''"
              @click="$router.push('/orders')">
              <el-icon><ShoppingBag /></el-icon>
              <span class="link-text">我的订单</span>
            </el-button>
            <el-dropdown @command="onCommand">
              <span class="user-chip">
                <el-avatar :size="30" class="user-avatar">{{ (auth.user?.nickname || 'U').slice(0, 1) }}</el-avatar>
                <span class="nickname">{{ auth.user?.nickname }}</span>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="profile">个人中心</el-dropdown-item>
                  <el-dropdown-item command="cart" v-if="auth.isCustomer">购物车</el-dropdown-item>
                  <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </el-header>
    </template>

    <!-- 子页面简洁头部（非首页） -->
    <header v-else class="sub-header">
      <el-button :icon="ArrowLeft" circle size="small" @click="goBack" />
      <span class="sub-title">{{ subTitle }}</span>
      <div class="spacer" />
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
            <el-dropdown-item command="profile">个人中心</el-dropdown-item>
            <el-dropdown-item command="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </header>

    <!-- 分类导航条（真实目录优先，常量兜底；PC 换行、平板换行、手机横滑，仅首页） -->
    <div v-if="isHome" class="category-bar">
      <div class="cat-track">
        <div class="cat-item" :class="{ active: route.path === '/' }" @click="$router.push('/')">
          推荐
        </div>
        <div
          v-for="c in navCats"
          :key="c.key"
          class="cat-item"
          :class="{ active: isCatActive(c) }"
          @click="goCategory(c)"
        >
          <span v-if="c.icon" class="cat-icon">{{ c.icon }}</span>{{ c.name }}
        </div>
      </div>
    </div>

    <el-main class="main">
      <router-view />
    </el-main>

    <!-- 移动端底部导航（商品详情页使用专属购买栏，不展示全站通用 Tabbar） -->
    <MobileTabbar v-if="!isProductDetail" />
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ChatDotRound, Search, ShoppingBag } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { CATEGORIES, categoryName } from '@/constants/categories'
import { apiCatalogCategories } from '@/api'
import type { CategoryVO } from '@/types/api'
import MobileTabbar from '@/components/layout/MobileTabbar.vue'

interface NavCat { key: string; name: string; icon: string; query: Record<string, string> }

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const keyword = ref('')

/** 仅首页显示完整顶栏+分类导航；其余页面用简洁子头部 */
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

onMounted(async () => {
  try {
    const tree = await apiCatalogCategories()
    if (tree && tree.length) {
      navCats.value = tree.slice(0, 16).map((c: CategoryVO) => ({
        key: String(c.id),
        name: categoryName(c.name),
        icon: c.icon || '',
        query: { categoryId: String(c.id) },
      }))
    }
  } catch {
    /* 目录不可用时使用内置常量 */
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

function goCategory(c: NavCat) {
  router.push({ path: '/products', query: c.query })
}

function isCatActive(c: NavCat): boolean {
  if (route.path !== '/products') return false
  if ('categoryId' in c.query) return route.query.categoryId === c.query.categoryId
  return route.query.category === c.query.category
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

/* ================= 顶栏 ================= */
.header {
  background: #fff;
  border-bottom: 1px solid #eef1f6;
  height: auto !important;
  padding: 0;
  box-shadow: 0 1px 4px rgba(30, 40, 80, 0.04);
  z-index: 50;
}

.header-inner {
  max-width: var(--mall-container);
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 24px;
  height: var(--mall-header-h);
  padding: 0 24px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  white-space: nowrap;
  user-select: none;
}

.logo-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: var(--mall-gradient);
  color: #fff;
  font-size: 14px;
  font-weight: 800;
  letter-spacing: 0.5px;
  box-shadow: var(--mall-shadow-float);
}

.logo-text {
  font-size: 22px;
  font-weight: 800;
  background: var(--mall-gradient);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.search-box {
  min-width: 0;
  flex: 1;
  max-width: 560px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.search-box :deep(.el-input__wrapper) {
  border-radius: 20px;
  box-shadow: 0 0 0 1px #e4e9f2 inset;
}

.search-box :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1.5px var(--el-color-primary) inset;
}

.search-hints {
  display: flex;
  gap: 14px;
  padding-left: 6px;
}

.search-hints .hint {
  font-size: 12px;
  color: #909399;
  cursor: pointer;
}

.search-hints .hint:hover {
  color: var(--el-color-primary);
}

.quick-links {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
}

.quick-links .link-text {
  margin-left: 4px;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  margin-left: 8px;
}

.user-avatar {
  background: var(--mall-gradient);
  color: #fff;
  font-weight: 600;
}

.nickname {
  font-size: 14px;
  max-width: 90px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ================= 分类导航条 ================= */
.category-bar {
  position: sticky;
  top: var(--mall-header-h);
  z-index: 49;
  background: #fff;
  border-bottom: 1px solid #eef1f6;
  flex-shrink: 0;
}

.cat-track {
  max-width: var(--mall-container);
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 24px;
  flex-wrap: wrap;
}

.cat-item {
  flex-shrink: 0;
  padding: 5px 14px;
  border-radius: 17px;
  font-size: 14px;
  color: #606266;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
}

.cat-item:hover {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}

.cat-item.active {
  background: var(--mall-gradient);
  color: #fff;
  font-weight: 500;
  box-shadow: var(--mall-shadow-float);
}

.cat-icon {
  margin-right: 4px;
}

.main {
  padding: 0;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}

/* ================= 子页面简洁头部 ================= */
.sub-header {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  gap: 10px;
  background: #fff;
  border-bottom: 1px solid #eef1f6;
  height: 52px;
  padding: 0 16px;
  box-shadow: 0 1px 4px rgba(30, 40, 80, 0.04);
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

/* ================= 平板 769–1199 ================= */
@media (max-width: 1199px) and (min-width: 769px) {
  .header-inner {
    gap: 14px;
    padding: 0 16px;
    height: 56px;
  }

  .logo-text {
    font-size: 18px;
  }

  .quick-links .link-text {
    display: none;
  }

  .category-bar {
    top: 56px;
  }

  .cat-track {
    padding: 6px 16px;
  }
}

/* ================= 手机 ≤768 ================= */
@media (max-width: 768px) {
  .header-inner {
    height: 52px;
    gap: 10px;
    padding: 0 12px;
  }

  .logo-badge {
    width: 28px;
    height: 28px;
    font-size: 12px;
    border-radius: 8px;
  }

  .logo-text {
    font-size: 17px;
  }

  .quick-links {
    display: none;
  }

  .search-box :deep(.el-input__inner) {
    height: 34px;
  }

  .category-bar {
    top: 52px;
  }

  .cat-track {
    flex-wrap: nowrap;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    padding: 6px 12px;
    gap: 6px;
    scrollbar-width: none;
  }

  .cat-track::-webkit-scrollbar {
    display: none;
  }

  .cat-item {
    padding: 4px 12px;
    font-size: 13px;
  }

  .main {
    padding-bottom: calc(56px + env(safe-area-inset-bottom)); /* 底部 TabBar 高度及安全区 */
  }
}
</style>
