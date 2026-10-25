<template>
  <el-drawer
    v-model="visible"
    direction="ltr"
    size="82%"
    :with-header="false"
    class="mobile-nav-drawer"
    append-to-body
  >
    <div class="m-drawer-inner">
      <!-- 头部 -->
      <div class="m-drawer-header">
        <div class="m-brand">
          <span class="m-logo-badge">{{ config.site.logoBadge }}</span>
          <div class="m-logo-text">{{ config.site.name }}</div>
        </div>
        <button class="m-close-btn" @click="visible = false">
          <el-icon :size="20"><Close /></el-icon>
        </button>
      </div>

      <!-- 用户卡 -->
      <div class="m-user-strip" @click="handleUserClick">
        <template v-if="auth.user">
          <el-avatar :size="36" class="m-avatar">{{ auth.user.nickname.slice(0, 1) }}</el-avatar>
          <div class="m-user-info">
            <span class="m-nick">{{ auth.user.nickname }}</span>
            <span class="m-role">个人中心 ›</span>
          </div>
        </template>
        <template v-else>
          <div class="m-avatar guest">👤</div>
          <div class="m-user-info">
            <span class="m-nick">点击登录 / 注册</span>
            <span class="m-role">享新客立减券与专属权益</span>
          </div>
        </template>
      </div>

      <!-- 快捷入口 -->
      <div class="m-nav-section">
        <div class="m-sec-title">快捷频道</div>
        <div class="m-nav-links">
          <div class="m-nav-item" @click="navigate('/')">
            <span>🏠 首页</span>
            <span class="m-arrow">›</span>
          </div>
          <div class="m-nav-item" @click="navigate('/products')">
            <span>🛍️ 全部商品</span>
            <span class="m-arrow">›</span>
          </div>
          <div class="m-nav-item" @click="navigate('/seckill')">
            <span>⚡ 限时秒杀专区</span>
            <span class="m-badge-hot">HOT</span>
          </div>
          <div class="m-nav-item" @click="navigate('/coupons')">
            <span>🎫 超值领券中心</span>
            <span class="m-arrow">›</span>
          </div>
          <div class="m-nav-item" @click="navigate('/assistant')">
            <span>✨ AI 购物助手</span>
            <span class="m-badge-ai">AI</span>
          </div>
        </div>
      </div>

      <!-- 商品分类 -->
      <div class="m-nav-section">
        <div class="m-sec-title">商品分类</div>
        <div class="m-cat-grid">
          <div
            v-for="c in categories"
            :key="c.code"
            class="m-cat-chip"
            @click="navigate(`/products?category=${c.code}`)"
          >
            <span class="m-chip-icon">{{ c.icon }}</span>
            <span class="m-chip-name">{{ c.name }}</span>
          </div>
        </div>
      </div>

      <!-- 底部系统设置 -->
      <div class="m-drawer-footer">
        <div class="m-footer-item">
          <span>外观主题</span>
          <ThemeToggle />
        </div>
        <div class="m-footer-contact">
          <span>客服热线：{{ config.site.supportPhone }}</span>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Close } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useMallConfig } from '@/composables/useMallConfig'
import { CATEGORIES } from '@/constants/categories'
import ThemeToggle from '@/components/layout/ThemeToggle.vue'

const router = useRouter()
const auth = useAuthStore()
const { config } = useMallConfig()

const visible = ref(false)
const categories = ref(CATEGORIES)

function open() {
  visible.value = true
}

function navigate(path: string) {
  visible.value = false
  router.push(path)
}

function handleUserClick() {
  visible.value = false
  if (auth.user) {
    router.push('/profile')
  } else {
    router.push('/login')
  }
}

defineExpose({
  open,
})
</script>

<style scoped>
.m-drawer-inner {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--mall-surface, #ffffff);
}

.m-drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid var(--mall-border-light, #f1f5f9);
}

.m-brand {
  display: flex;
  align-items: center;
  gap: 8px;
}

.m-logo-badge {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: var(--mall-gradient, linear-gradient(135deg, #0f172a 0%, #1e293b 100%));
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 13px;
}

.m-logo-text {
  font-size: 16px;
  font-weight: 800;
  color: #0f172a;
}

html.dark .m-logo-text {
  color: #f8fafc;
}

.m-close-btn {
  border: none;
  background: transparent;
  padding: 4px;
  color: #94a3b8;
  cursor: pointer;
}

.m-user-strip {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: var(--mall-surface-2, #f8fafc);
  cursor: pointer;
  border-bottom: 1px solid var(--mall-border-light, #f1f5f9);
}

.m-avatar {
  background: var(--el-color-primary, #2563eb);
  color: #fff;
  font-weight: 700;
}

.m-avatar.guest {
  width: 36px;
  height: 36px;
  border-radius: 9999px;
  background: #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}

.m-user-info {
  display: flex;
  flex-direction: column;
}

.m-nick {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

html.dark .m-nick {
  color: #f1f5f9;
}

.m-role {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}

.m-nav-section {
  padding: 14px 16px;
  border-bottom: 1px solid var(--mall-border-light, #f1f5f9);
}

.m-sec-title {
  font-size: 11px;
  font-weight: 700;
  color: #94a3b8;
  letter-spacing: 0.05em;
  margin-bottom: 10px;
}

.m-nav-links {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.m-nav-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 14px;
  color: #334155;
  cursor: pointer;
}

html.dark .m-nav-item {
  color: #cbd5e1;
}

.m-nav-item:active {
  background: var(--mall-surface-2, #f1f5f9);
}

.m-arrow {
  color: #94a3b8;
}

.m-badge-hot {
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  background: var(--mall-price, #e11d48);
  padding: 1px 6px;
  border-radius: 4px;
}

.m-badge-ai {
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  background: var(--el-color-primary, #2563eb);
  padding: 1px 6px;
  border-radius: 4px;
}

.m-cat-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.m-cat-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  background: var(--mall-surface-2, #f8fafc);
  border-radius: 6px;
  font-size: 12px;
  color: #475569;
  cursor: pointer;
}

html.dark .m-cat-chip {
  color: #cbd5e1;
}

.m-cat-chip:active {
  background: #e2e8f0;
}

.m-drawer-footer {
  margin-top: auto;
  padding: 16px;
  background: var(--mall-surface-2, #f8fafc);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.m-footer-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: #475569;
}

.m-footer-contact {
  font-size: 11px;
  color: #94a3b8;
  text-align: center;
}
</style>
