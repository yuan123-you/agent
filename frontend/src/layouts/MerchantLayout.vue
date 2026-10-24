<template>
  <el-container class="merchant-layout">
    <!-- 桌面/平板侧栏 -->
    <el-aside width="200px" class="aside">
      <div class="logo">🏪 卖家中心</div>
      <div class="shop-card">
        <div class="shop-name">{{ profile?.shopName || '...' }}</div>
        <div class="shop-meta">在售 {{ profile?.onSaleCount ?? '-' }} / 共 {{ profile?.totalProducts ?? '-' }}</div>
      </div>
      <el-menu :default-active="activeMenu" router class="menu">
        <el-menu-item index="/merchant/products">商品管理</el-menu-item>
        <el-menu-item index="/merchant/reviews">评论回复</el-menu-item>
      </el-menu>
      <div class="aside-footer">
        <el-button link @click="$router.push('/')">回商城</el-button>
        <el-button link type="danger" @click="logout">退出</el-button>
      </div>
    </el-aside>
    <el-container>
      <el-header class="header">
        <el-button class="menu-toggle" text :icon="Menu" @click="drawer = true" />
        <ThemeToggle /><span class="title mobile-only">🏪 卖家中心</span>
        <span class="spacer" />
        <span class="welcome">{{ profile?.shopName || auth.user?.nickname }}</span>
        <el-button link type="danger" @click="logout">退出</el-button>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>

    <!-- 移动端抽屉菜单 -->
    <el-drawer v-model="drawer" title="🏪 卖家中心" direction="ltr" size="72vw">
      <div class="drawer-shop">
        <div class="shop-name">{{ profile?.shopName || '...' }}</div>
        <div class="shop-meta">在售 {{ profile?.onSaleCount ?? '-' }} / 共 {{ profile?.totalProducts ?? '-' }}</div>
      </div>
      <el-menu :default-active="activeMenu" router class="drawer-menu" @select="drawer = false">
        <el-menu-item index="/merchant/products">商品管理</el-menu-item>
        <el-menu-item index="/merchant/reviews">评论回复</el-menu-item>
      </el-menu>
      <div class="drawer-footer">
        <el-button @click="$router.push('/'); drawer = false">回商城</el-button>
        <el-button type="danger" plain @click="logout">退出</el-button>
      </div>
    </el-drawer>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Menu } from '@element-plus/icons-vue'
import ThemeToggle from '@/components/layout/ThemeToggle.vue'
import { useAuthStore } from '@/stores/auth'
import { apiMerchantProfile } from '@/api'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const drawer = ref(false)
const profile = ref<{ shopName: string; onSaleCount: number; totalProducts: number } | null>(null)

const activeMenu = computed(() => '/' + (route.path.split('/')[2] || 'products'))

async function logout() {
  drawer.value = false
  await auth.logout()
  router.push('/login')
}

onMounted(async () => {
  profile.value = await apiMerchantProfile().catch(() => null)
})
</script>

<style scoped>
.merchant-layout {
  height: 100%;
}

.aside {
  background: var(--mall-surface, #fff);
  border-right: 1px solid var(--el-border-color, #e4e7ed);
  display: flex;
  flex-direction: column;
}

.logo {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  color: var(--el-color-primary);
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
}

.shop-card {
  padding: 14px 16px;
  border-bottom: 1px solid #f5f7fa;
}

.shop-name {
  min-width: 0;
  font-weight: 600;
  font-size: 15px;
}

.shop-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
  margin-top: 4px;
}

.menu {
  border-right: none;
  flex: 1;
}

.aside-footer {
  padding: 12px;
  display: flex;
  justify-content: center;
  gap: 8px;
  border-top: 1px solid #f5f7fa;
}

.header {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--mall-surface, #fff);
  border-bottom: 1px solid var(--el-border-color, #e4e7ed);
  height: 56px;
}

.menu-toggle {
  display: none;
  font-size: 20px;
}

.title {
  font-weight: 700;
  color: var(--el-color-primary);
}

.spacer {
  flex: 1;
}

.welcome {
  min-width: 0;
  font-size: 14px;
  color: var(--el-text-color-regular, #606266);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.main {
  overflow-y: auto;
  background: var(--mall-surface-2, #f5f7fa);
}

.drawer-shop {
  padding: 0 4px 12px;
  border-bottom: 1px solid var(--el-fill-color, #f0f2f5);
  margin-bottom: 8px;
}

.drawer-menu {
  border-right: none;
}

.drawer-footer {
  position: absolute;
  bottom: 16px;
  left: 16px;
  right: 16px;
  display: flex;
  gap: 8px;
}

.drawer-footer .el-button {
  flex: 1;
}

/* ---------- 平板：紧凑侧栏 ---------- */
@media (max-width: 1199px) and (min-width: 769px) {
  .aside {
    width: 64px !important;
  }

  .aside .logo {
    font-size: 14px;
  }

  .shop-card {
    display: none;
  }

  .aside :deep(.el-menu-item) {
    padding: 0 12px;
    font-size: 13px;
  }

  .aside-footer {
    flex-direction: column;
    gap: 4px;
  }
}

/* ---------- 手机：抽屉菜单 ---------- */
@media (max-width: 768px) {
  .aside {
    display: none;
  }

  .menu-toggle {
    display: inline-flex;
  }

  .main {
    padding: 12px;
  }
}
</style>
