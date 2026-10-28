<template>
  <el-container class="console-layout">
    <!-- 桌面/平板侧栏 -->
    <el-aside width="200px" class="aside">
      <div class="logo">AI Mall 控制台</div>
      <el-menu :default-active="activeMenu" router class="menu">
        <template v-if="auth.isAdmin">
          <el-menu-item index="/admin/dashboard">数据看板</el-menu-item>
          <el-menu-item index="/admin/products">商品管理</el-menu-item>
          <el-menu-item index="/admin/orders">订单管理</el-menu-item>
          <el-menu-item index="/admin/after-sales">售后管理</el-menu-item>
          <el-menu-item index="/admin/kb">知识库</el-menu-item>
          <el-menu-item index="/admin/users">用户管理</el-menu-item>
          <el-menu-item index="/admin/stats">使用统计</el-menu-item>
        </template>
        <template v-else-if="auth.isAgent">
          <el-menu-item index="/workbench">客服工作台</el-menu-item>
        </template>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <!-- 移动端汉堡入口 -->
        <el-button class="menu-toggle" text :icon="Menu" @click="drawer = true" />
        <span class="title mobile-only">AI Mall 控制台</span>
        <span class="spacer" />
        <span class="welcome">{{ auth.user?.nickname }}（{{ roleText }}）</span>
        <el-button link type="danger" @click="logout">退出登录</el-button>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>

    <!-- 移动端抽屉菜单 -->
    <el-drawer v-model="drawer" title="AI Mall 控制台" direction="ltr" size="72vw">
      <el-menu :default-active="activeMenu" router class="drawer-menu" @select="drawer = false">
        <template v-if="auth.isAdmin">
          <el-menu-item index="/admin/dashboard">数据看板</el-menu-item>
          <el-menu-item index="/admin/products">商品管理</el-menu-item>
          <el-menu-item index="/admin/orders">订单管理</el-menu-item>
          <el-menu-item index="/admin/after-sales">售后管理</el-menu-item>
          <el-menu-item index="/admin/kb">知识库</el-menu-item>
          <el-menu-item index="/admin/users">用户管理</el-menu-item>
          <el-menu-item index="/admin/stats">使用统计</el-menu-item>
        </template>
        <template v-else-if="auth.isAgent">
          <el-menu-item index="/workbench">客服工作台</el-menu-item>
        </template>
      </el-menu>
      <div class="drawer-footer">
        <el-button @click="$router.push('/'); drawer = false">回商城</el-button>
        <el-button type="danger" plain @click="logout">退出登录</el-button>
      </div>
    </el-drawer>
  </el-container>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Menu } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { consoleActiveMenu } from './consoleLayout'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const drawer = ref(false)

const activeMenu = computed(() => consoleActiveMenu(route.path))

const roleText = computed(() =>
  ({ ADMIN: '管理员', AGENT: '人工客服', CUSTOMER: '买家' }[auth.role] || auth.role),
)

async function logout() {
  drawer.value = false
  await auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.console-layout {
  height: 100%;
}

.console-layout > :deep(.el-container),
.main {
  min-width: 0;
}

.aside {
  background: var(--mall-surface, #fff);
  border-right: 1px solid var(--el-border-color, #e4e7ed);
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

.menu {
  border-right: none;
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
}

.main {
  overflow-y: auto;
  background: var(--mall-surface-2, #f5f7fa);
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
    font-size: 13px;
    padding: 0 6px;
    text-align: center;
  }

  .aside :deep(.el-menu-item) {
    padding: 0 10px;
    font-size: 13px;
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

  .welcome {
    font-size: 13px;
  }

  .main {
    padding: 12px;
  }
}
</style>
