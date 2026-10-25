<template>
  <div class="profile-page">
    <!-- 用户卡片 -->
    <div class="user-card">
      <el-avatar :size="64">{{ (auth.user?.nickname || 'U').slice(0, 1) }}</el-avatar>
      <div class="user-info">
        <div class="nickname" @click="!auth.user && $router.push('/login?redirect=/profile')">
          {{ auth.user?.nickname || '点击登录 / 注册' }}
        </div>
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

    <!-- 我的优惠券 -->
    <div class="coupon-section">
      <h3 class="section-title">🎫 我的优惠券</h3>
      <div v-if="coupons.length" class="coupon-list">
        <div v-for="c in coupons" :key="c.userCouponId" class="my-coupon" :class="c.status.toLowerCase()">
          <div class="mc-amount"><i>￥</i>{{ c.discountValue }}</div>
          <div class="mc-info">
            <div class="mc-name">{{ c.name }}</div>
            <div class="mc-rule">
              {{ (c.minAmount || 0) > 0 ? `满 ${c.minAmount} 可用` : '无门槛' }} · {{ (c.expireAt || '').slice(0, 10) }} 到期
            </div>
          </div>
          <el-tag size="small" :type="c.status === 'UNUSED' ? 'danger' : 'info'" effect="plain">
            {{ c.status === 'UNUSED' ? '可用' : c.status === 'USED' ? '已使用' : '已过期' }}
          </el-tag>
        </div>
      </div>
      <el-empty v-else description="还没有优惠券，去领券中心逛逛" :image-size="56" />
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
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowRight, ChatDotRound, Clock, Goods, Location, ShoppingBag, ShoppingCart, Star, SwitchButton,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { apiMyCoupons } from '@/api'
import type { MyCouponVO } from '@/types/api'
import AddressBook from '@/components/address/AddressBook.vue'

const auth = useAuthStore()
const router = useRouter()
const coupons = ref<MyCouponVO[]>([])

const roleText = computed(
  () => ({ ADMIN: '管理员', AGENT: '人工客服', CUSTOMER: '买家', MERCHANT: '卖家' }[auth.role] || auth.role),
)

async function logout() {
  await auth.logout()
  router.push('/login')
}

onMounted(async () => {
  try {
    const list = await apiMyCoupons()
    if (list && list.length > 0) {
      coupons.value = list
      return
    }
  } catch {}

  // 本地已领卡券回显联动
  try {
    const claimed: number[] = JSON.parse(localStorage.getItem('aimall_claimed_coupons') || '[]')
    if (claimed.length > 0) {
      const MOCK_MAP: Record<number, { name: string; discountValue: number; minAmount: number }> = {
        101: { name: '全场通用大促满减券', discountValue: 20, minAmount: 100 },
        102: { name: '数码数码电器专享券', discountValue: 50, minAmount: 300 },
        103: { name: '品质尖货高额减免券', discountValue: 100, minAmount: 500 },
        104: { name: '旗舰至尊大额立减券', discountValue: 150, minAmount: 1000 },
        105: { name: '无门槛尝鲜立减神券', discountValue: 10, minAmount: 0 },
        106: { name: '新人首单专享补贴券', discountValue: 15, minAmount: 50 },
      }
      coupons.value = claimed.map((id) => {
        const item = MOCK_MAP[id] || { name: '官方精选大促券', discountValue: 20, minAmount: 100 }
        return {
          userCouponId: id,
          couponId: id,
          name: item.name,
          discountValue: item.discountValue,
          minAmount: item.minAmount,
          status: 'UNUSED',
          expireAt: '2026-12-31 23:59:59',
        }
      })
    }
  } catch {}
})
</script>

<style scoped>
.profile-page {
  max-width: 720px;
  margin: 0 auto;
  padding: 20px 16px;
}

/* 我的优惠券 */
.coupon-section {
  background: var(--mall-surface, #fff);
  border-radius: var(--mall-radius);
  padding: 16px;
  margin-bottom: 14px;
}

.section-title {
  margin: 0 0 12px;
  font-size: 15px;
}

.coupon-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.my-coupon {
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid #ffe0d6;
  border-radius: 10px;
  padding: 10px 12px;
  background: linear-gradient(120deg, #fff8f6, #fff);
}

.my-coupon.used,
.my-coupon.expired {
  border-color: #eef0f4;
  background: var(--mall-surface-2, #fafbfc);
  filter: grayscale(0.4);
}

.mc-amount {
  flex: none;
  width: 72px;
  text-align: center;
  color: var(--el-color-danger);
  font-size: 22px;
  font-weight: 700;
}

.mc-amount i {
  font-style: normal;
  font-size: 12px;
}

.mc-info {
  flex: 1;
  min-width: 0;
}

.mc-name {
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mc-rule {
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
  margin-top: 2px;
}

.user-card {
  display: flex;
  align-items: center;
  gap: 16px;
  background: var(--mall-surface, #ffffff);
  border: 1px solid var(--mall-border-light, #f1f5f9);
  border-radius: var(--mall-radius-lg, 14px);
  padding: 24px;
  box-shadow: var(--mall-shadow-card);
}

.nickname {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 6px;
}

.entry-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
  margin-top: 14px;
}

.entry {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  background: var(--mall-surface, #ffffff);
  border: 1px solid var(--mall-border-light, #f1f5f9);
  border-radius: var(--mall-radius, 10px);
  padding: 16px 8px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: #334155;
  box-shadow: var(--mall-shadow-xs);
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.entry:hover {
  color: var(--el-color-primary);
}

.menu-card {
  background: var(--mall-surface, #fff);
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
  color: var(--el-text-color-placeholder, #c0c4cc);
}
@media (max-width: 600px) {
  .profile-page {
    padding: 12px 10px;
  }

  .entry-grid {
    grid-template-columns: repeat(5, 1fr);
    gap: 6px;
  }

  .entry {
    padding: 10px 2px;
    font-size: 11px;
  }

  .entry .el-icon {
    font-size: 20px;
  }

  .user-card {
    padding: 14px;
  }
}
</style>


