<template>
  <!-- 仅在首页(/)与分类页(/products)出现，其他页面彻底不显示 -->
  <div v-if="showDock" class="floating-dock">
    <!-- AI 助手快速入口 -->
    <el-tooltip content="AI 智能导购顾问" placement="left">
      <button class="dock-btn dock-ai" @click="$router.push('/assistant')">
        <span class="ai-spark">✨</span>
      </button>
    </el-tooltip>

    <!-- 侧边栏购物车开关 (未登录时拦截跳登录) -->
    <el-tooltip content="我的购物车" placement="left">
      <button class="dock-btn dock-cart" @click="handleCartClick">
        <el-icon :size="18"><ShoppingCart /></el-icon>
        <span v-if="cart.cartCount > 0" class="dock-badge">{{ cart.cartCount > 99 ? '99+' : cart.cartCount }}</span>
      </button>
    </el-tooltip>

    <!-- 返回顶部 -->
    <transition name="dock-fade">
      <button v-if="showBackTop" class="dock-btn dock-top" @click="scrollToTop">
        <el-icon :size="18"><Top /></el-icon>
      </button>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ShoppingCart, Top } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useCartStore } from '@/stores/cart'

const router = useRouter()
const route = useRoute()
const cart = useCartStore()
const showBackTop = ref(false)

// 严格限定：只在首页与分类页显示
const showDock = computed(() => {
  return route.path === '/' || route.path === '/products'
})

function handleCartClick() {
  const token = localStorage.getItem('token')
  if (!token) {
    ElMessage.warning('请先登录后查看购物车')
    router.push({ path: '/login', query: { redirect: route.fullPath } })
    return
  }
  cart.openDrawer()
}

function onScroll() {
  const scroller = document.querySelector('.client-layout .main') as HTMLElement | null
  const top = scroller ? scroller.scrollTop : window.scrollY
  showBackTop.value = top > 350
}

function scrollToTop() {
  const scroller = document.querySelector('.client-layout .main') as HTMLElement | null
  if (scroller && scroller.scrollHeight > scroller.clientHeight) {
    scroller.scrollTo({ top: 0, behavior: 'smooth' })
  }
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
})

onUnmounted(() => {
  window.removeEventListener('scroll', onScroll)
})
</script>

<style scoped>
.floating-dock {
  position: fixed;
  right: 20px;
  bottom: 84px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  z-index: 85;
}

.dock-btn {
  width: 44px;
  height: 44px;
  border-radius: 9999px;
  background: var(--mall-surface, #ffffff);
  border: 1px solid var(--mall-border, #e2e8f0);
  box-shadow: var(--mall-shadow-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  position: relative;
  color: #334155;
  transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1);
}

html.dark .dock-btn {
  color: #f1f5f9;
  border-color: var(--mall-border, #232734);
}

.dock-btn:hover {
  transform: translateY(-2px);
  border-color: var(--el-color-primary, #2563eb);
  color: var(--el-color-primary, #2563eb);
}

.dock-ai {
  background: radial-gradient(circle at 70% 30%, rgba(37, 99, 235, 0.15), transparent 70%), var(--mall-surface, #ffffff);
  border-color: rgba(37, 99, 235, 0.3);
}

.ai-spark {
  font-size: 18px;
}

.dock-badge {
  position: absolute;
  top: -3px;
  right: -3px;
  background: var(--mall-price, #e11d48);
  color: #ffffff;
  font-size: 10px;
  font-weight: 700;
  height: 18px;
  min-width: 18px;
  padding: 0 4px;
  border-radius: 9999px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--mall-surface, #ffffff);
}

.dock-fade-enter-active,
.dock-fade-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}

.dock-fade-enter-from,
.dock-fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

@media (max-width: 768px) {
  .floating-dock {
    right: 14px;
    bottom: calc(64px + env(safe-area-inset-bottom));
  }
  .dock-btn {
    width: 40px;
    height: 40px;
  }
}
</style>
