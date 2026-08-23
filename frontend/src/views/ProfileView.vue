<template>
  <div class="profile-page">
    <!-- 用户卡片 -->
    <div class="user-card">
      <el-avatar :size="64">{{ (auth.user?.nickname || 'U').slice(0, 1) }}</el-avatar>
      <div class="user-info">
        <div class="nickname">{{ auth.user?.nickname }}</div>
        <el-tag size="small" type="info">{{ roleText }}</el-tag>
      </div>
    </div>

    <!-- 订单/资产入口 -->
    <div class="entry-grid">
      <div class="entry" @click="$router.push('/orders')">
        <el-icon :size="22"><ShoppingBag /></el-icon>
        <span>我的订单</span>
      </div>
      <div class="entry" @click="$router.push('/favorites')">
        <el-icon :size="22"><Star /></el-icon>
        <span>我的收藏</span>
      </div>
      <div class="entry" @click="$router.push('/history')">
        <el-icon :size="22"><Clock /></el-icon>
        <span>浏览历史</span>
      </div>
      <div class="entry" @click="$router.push('/cart')">
        <el-icon :size="22"><ShoppingCart /></el-icon>
        <span>购物车</span>
      </div>
      <div class="entry" @click="$router.push('/addresses')">
        <el-icon :size="22"><Location /></el-icon>
        <span>收货地址</span>
      </div>
    </div>

    <AddressBook compact title="我的常用收货地址" />

    <!-- 菜单 -->
    <div class="menu-card">
      <div class="menu-item" @click="$router.push('/assistant')">
        <el-icon><ChatDotRound /></el-icon>
        <span>AI 购物助手</span>
        <el-icon class="arrow"><ArrowRight /></el-icon>
      </div>
      <div class="menu-item" @click="$router.push('/products')">
        <el-icon><Goods /></el-icon>
        <span>逛逛商城</span>
        <el-icon class="arrow"><ArrowRight /></el-icon>
      </div>
      <div class="menu-item danger" @click="logout">
        <el-icon><SwitchButton /></el-icon>
        <span>退出登录</span>
        <el-icon class="arrow"><ArrowRight /></el-icon>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowRight, ChatDotRound, Clock, Goods, Location, ShoppingBag, ShoppingCart, Star, SwitchButton,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import AddressBook from '@/components/address/AddressBook.vue'

const auth = useAuthStore()
const router = useRouter()

const roleText = computed(
  () => ({ ADMIN: '管理员', AGENT: '人工客服', CUSTOMER: '买家', MERCHANT: '卖家' }[auth.role] || auth.role),
)

async function logout() {
  await auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.profile-page {
  max-width: 720px;
  margin: 0 auto;
  padding: 20px 16px;
}

.user-card {
  display: flex;
  align-items: center;
  gap: 16px;
  background: #fff;
  border-radius: 12px;
  padding: 20px;
}

.nickname {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 6px;
}

.entry-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-top: 14px;
}

.entry {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  background: #fff;
  border-radius: 10px;
  padding: 14px 6px;
  cursor: pointer;
  font-size: 12px;
  color: #606266;
}

.entry:hover {
  color: var(--el-color-primary);
}

.menu-card {
  background: #fff;
  border-radius: 12px;
  margin-top: 14px;
  overflow: hidden;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 15px 20px;
  cursor: pointer;
  border-bottom: 1px solid #f5f7fa;
}

.menu-item:last-child {
  border-bottom: none;
}

.menu-item:hover {
  background: #f9fafc;
}

.menu-item span {
  flex: 1;
}

.menu-item.danger span,
.menu-item.danger .el-icon:first-child {
  color: var(--el-color-danger);
}

.arrow {
  color: #c0c4cc;
}
</style>

