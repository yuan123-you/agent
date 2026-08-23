<template>
  <el-container class="console-layout">
    <el-aside width="200px" class="aside">
      <div class="logo">AI Mall 控制台</div>
      <el-menu :default-active="activeMenu" router class="menu">
        <template v-if="auth.isAdmin">
          <el-menu-item index="/admin/products">商品管理</el-menu-item>
          <el-menu-item index="/admin/orders">订单管理</el-menu-item>
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
        <span class="welcome">{{ auth.user?.nickname }}（{{ roleText }}）</span>
        <el-button link type="danger" @click="logout">退出登录</el-button>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const activeMenu = computed(() => {
  if (route.path.startsWith('/workbench')) return '/workbench'
  const base = '/' + route.path.split('/')[2]
  return base
})

const roleText = computed(() =>
  ({ ADMIN: '管理员', AGENT: '人工客服', CUSTOMER: '买家' }[auth.role] || auth.role),
)

async function logout() {
  await auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.console-layout {
  height: 100%;
}

.aside {
  background: #fff;
  border-right: 1px solid #e4e7ed;
}

.logo {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  color: var(--el-color-primary);
  border-bottom: 1px solid #ebeef5;
}

.menu {
  border-right: none;
}

.header {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  height: 56px;
}

.welcome {
  font-size: 14px;
  color: #606266;
}

.main {
  overflow-y: auto;
  background: #f5f7fa;
}
</style>
