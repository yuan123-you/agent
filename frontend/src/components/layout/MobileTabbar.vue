<template>
  <!-- 移动端底部导航（<768px 显示） -->
  <nav class="mobile-tabbar">
    <div
      v-for="tab in tabs"
      :key="tab.path"
      class="tab-item"
      :class="{ active: isActive(tab) }"
      @click="onTabClick(tab)"
    >
      <el-icon :size="21"><component :is="tab.icon" /></el-icon>
      <span class="tab-label">{{ tab.label }}</span>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { ChatDotRound, HomeFilled, Menu, ShoppingCart, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()

const tabs = [
  { path: '/', label: '首页', icon: HomeFilled, exact: true },
  { path: '/products', label: '分类', icon: Menu, prefix: true },
  { path: '/assistant', label: 'AI助手', icon: ChatDotRound, prefix: true },
  { path: '/cart', label: '购物车', icon: ShoppingCart, prefix: true },
  { path: '/profile', label: '我的', icon: User, prefix: true },
]

function isActive(tab: (typeof tabs)[number]): boolean {
  if (tab.exact) return route.path === '/'
  return route.path.startsWith(tab.path)
}

function onTabClick(tab: (typeof tabs)[number]) {
  if (tab.path === '/cart') {
    const token = localStorage.getItem('token')
    if (!token) {
      ElMessage.warning('请先登录后查看购物车')
      router.push({ path: '/login', query: { redirect: '/cart' } })
      return
    }
  }
  router.push(tab.path)
}
</script>

<style scoped>
.mobile-tabbar {
  display: none;
}

/* 移动端 */
@media (max-width: 768px) {
  .mobile-tabbar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    display: flex;
    background: rgba(255, 255, 255, 0.96);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-top: 1px solid var(--el-border-color-lighter, #eef1f6);
    padding: 4px 0 calc(4px + env(safe-area-inset-bottom));
    z-index: 100;
  }

  .tab-item {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1px;
    color: var(--el-text-color-secondary, #909399);
    cursor: pointer;
    padding: 3px 0;
    transition: color 0.15s, transform 0.15s;
  }

  .tab-item:active {
    transform: scale(0.92);
  }

  .tab-item.active {
    color: var(--el-color-primary, #2563eb);
    font-weight: 500;
  }

  .tab-label {
    font-size: 11px;
  }
}
</style>
