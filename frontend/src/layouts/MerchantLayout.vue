<template>
  <el-container class="merchant-layout">
    <el-aside width="200px" class="aside">
      <div class="logo">🏪 商家中心</div>
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
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { apiMerchantProfile } from '@/api'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const profile = ref<{ shopName: string; onSaleCount: number; totalProducts: number } | null>(null)

const activeMenu = computed(() => '/' + (route.path.split('/')[2] || 'products'))

async function logout() {
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
  background: #fff;
  border-right: 1px solid #e4e7ed;
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
  border-bottom: 1px solid #ebeef5;
}

.shop-card {
  padding: 14px 16px;
  border-bottom: 1px solid #f5f7fa;
}

.shop-name {
  font-weight: 600;
  font-size: 15px;
}

.shop-meta {
  font-size: 12px;
  color: #909399;
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

.main {
  overflow-y: auto;
  background: #f5f7fa;
}

@media (max-width: 768px) {
  .aside {
    width: 64px;
  }

  .shop-card,
  .aside-footer {
    display: none;
  }

  :deep(.el-menu-item) {
    padding: 0 16px;
  }
}
</style>
