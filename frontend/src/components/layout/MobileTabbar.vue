<template>
  <!-- 移动端底部导航（<768px 显示） -->
  <nav class="mobile-tabbar">
    <div
      v-for="tab in tabs"
      :key="tab.path"
      class="tab-item"
      :class="{ active: isActive(tab) }"
      @click="$router.push(tab.path)"
    >
      <el-icon :size="22"><component :is="tab.icon" /></el-icon>
      <span class="tab-label">{{ tab.label }}</span>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { ChatDotRound, HomeFilled, Menu, ShoppingCart, User } from '@element-plus/icons-vue'

const route = useRoute()

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
    background: #fff;
    border-top: 1px solid #ebeef5;
    padding: 4px 0 calc(4px + env(safe-area-inset-bottom));
    z-index: 100;
  }

  .tab-item {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1px;
    color: #909399;
    cursor: pointer;
    padding: 2px 0;
  }

  .tab-item.active {
    color: var(--el-color-primary);
  }

  .tab-label {
    font-size: 11px;
  }
}
</style>
