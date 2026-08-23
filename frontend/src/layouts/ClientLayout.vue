<template>
  <el-container class="client-layout">
    <!-- 顶栏 + 分类导航条：仅首页显示 -->
    <template v-if="isHome">
      <el-header class="header">
      <div class="logo" @click="$router.push('/')">AI Mall</div>
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
            <el-avatar :size="28">{{ (auth.user?.nickname || 'U').slice(0, 1) }}</el-avatar>
            <span class="nickname">{{ auth.user?.nickname }}</span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">个人中心</el-dropdown-item>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
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
          <el-avatar :size="26">{{ (auth.user?.nickname || 'U').slice(0, 1) }}</el-avatar>
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

    <!-- 分类导航条（横向滚动，仅首页） -->
    <div v-if="isHome" class="category-bar">
      <div class="cat-item" :class="{ active: route.path === '/' }" @click="$router.push('/')">
        推荐
      </div>
      <div
        v-for="c in CATEGORIES"
        :key="c.code"
        class="cat-item"
        :class="{ active: isCatActive(c.code) }"
        @click="$router.push(`/products?category=${c.code}`)"
      >
        <span class="cat-icon">{{ c.icon }}</span>{{ c.name }}
      </div>
    </div>

    <el-main class="main">
      <router-view />
    </el-main>

    <!-- 移动端底部导航 -->
    <MobileTabbar />
  </el-container>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ChatDotRound, Search, ShoppingBag } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { CATEGORIES } from '@/constants/categories'
import MobileTabbar from '@/components/layout/MobileTabbar.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const keyword = ref('')

/** 仅首页显示完整顶栏+分类导航；其余页面用简洁子头部 */
const isHome = computed(() => route.path === '/')

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

function isCatActive(code: string): boolean {
  return route.path === '/products' && route.query.category === code
}

async function onCommand(cmd: string) {
  if (cmd === 'home') {
    router.push('/')
  } else if (cmd === 'profile') {
    router.push('/profile')
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

.header {
  display: flex;
  align-items: center;
  gap: 20px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  height: 60px;
  padding: 0 20px;
}

.logo {
  font-size: 22px;
  font-weight: 700;
  color: var(--el-color-primary);
  cursor: pointer;
  white-space: nowrap;
}

.search-box {
  flex: 1;
  max-width: 560px;
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

.nickname {
  font-size: 14px;
  max-width: 90px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 分类导航条 */
.category-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  padding: 8px 20px;
  overflow-x: auto;
  scrollbar-width: none;
}

.category-bar::-webkit-scrollbar {
  display: none;
}

.cat-item {
  flex-shrink: 0;
  padding: 5px 14px;
  border-radius: 16px;
  font-size: 14px;
  color: #606266;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
}

.cat-item:hover {
  background: #f5f7fa;
  color: var(--el-color-primary);
}

.cat-item.active {
  background: var(--el-color-primary);
  color: #fff;
}

.cat-icon {
  margin-right: 4px;
}

.main {
  padding: 0;
  flex: 1;
  overflow-y: auto;
}

/* 子页面简洁头部 */
.sub-header {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
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

/* 平板：紧凑顶栏 */
@media (max-width: 1024px) {
  .header {
    gap: 12px;
    padding: 0 12px;
  }

  .quick-links .link-text {
    display: none;
  }
}

/* 移动端：隐藏文字入口（由底部 TabBar 承担），搜索框撑满 */
@media (max-width: 768px) {
  .header {
    height: 52px;
    gap: 10px;
    padding: 0 12px;
  }

  .logo {
    font-size: 18px;
  }

  .quick-links {
    display: none;
  }

  .main {
    padding-bottom: 56px; /* 底部 TabBar 高度 */
  }
}
</style>
