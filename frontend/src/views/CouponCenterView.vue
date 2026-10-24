<template>
  <div class="coupon-center">
    <!-- 页头横幅 -->
    <div class="cc-hero">
      <div>
        <div class="cc-title">🎫 领券中心</div>
        <div class="cc-sub">领券下单更划算 · 在「个人中心」查看已领优惠券</div>
      </div>
    </div>

    <div v-loading="loading" class="cc-body">
      <div v-if="coupons.length" class="cc-grid">
        <div v-for="c in coupons" :key="c.couponId" class="cc-card">
          <div class="cc-left">
            <div class="cc-val"><i>￥</i>{{ c.discountValue }}</div>
            <div class="cc-rule">{{ c.minAmount > 0 ? `满${c.minAmount}可用` : '无门槛' }}</div>
          </div>
          <div class="cc-right">
            <div class="cc-name">{{ c.name }}</div>
            <div class="cc-window">{{ windowText(c) }}</div>
            <div class="cc-progress">
              <div class="cc-bar" :style="{ width: receivedPercent(c) }" />
            </div>
            <div class="cc-foot">
              <span class="cc-left">已领 {{ c.receivedCount }}/{{ c.totalCount }}</span>
              <el-button size="small" type="danger" round :disabled="c.received" @click="receive(c)">
                {{ c.received ? '已领取' : '立即领取' }}
              </el-button>
            </div>
          </div>
        </div>
      </div>
      <el-empty v-else-if="!loading" description="暂时没有可领取的优惠券" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiReceivableCoupons, apiReceiveCoupon } from '@/api'
import { useAuthStore } from '@/stores/auth'
import type { CouponVO } from '@/types/api'

const auth = useAuthStore()
const router = useRouter()
const coupons = ref<CouponVO[]>([])
const loading = ref(true)

function windowText(c: CouponVO): string {
  const s = (c.startTime || '').slice(5, 16).replace('T', ' ')
  const e = (c.endTime || '').slice(5, 16).replace('T', ' ')
  return s ? `领取时间 ${s} ~ ${e}` : '长期可领'
}

function receivedPercent(c: CouponVO): string {
  const total = Math.max(1, c.totalCount)
  return `${Math.min(100, Math.round((c.receivedCount / total) * 100))}%`
}

async function receive(c: CouponVO) {
  if (!auth.isCustomer) {
    ElMessage.warning('请先登录后领券')
    void router.push({ path: '/login', query: { redirect: '/coupons' } })
    return
  }
  await apiReceiveCoupon(c.couponId)
  c.received = true
  ElMessage.success(`已领取「${c.name}」，下单时可在支付页选择使用`)
}

onMounted(async () => {
  try {
    coupons.value = (await apiReceivableCoupons()) || []
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.coupon-center {
  max-width: var(--mall-container, 1200px);
  margin: 0 auto;
  padding: 16px 16px 32px;
}

.cc-hero {
  background: linear-gradient(120deg, #e4393c, #ff7a59);
  border-radius: var(--mall-radius-lg, 12px);
  color: #fff;
  padding: 24px 28px;
  margin-bottom: 20px;
}

.cc-title {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: 1px;
}

.cc-sub {
  font-size: 13px;
  opacity: 0.9;
  margin-top: 4px;
}

.cc-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.cc-card {
  display: flex;
  align-items: stretch;
  border-radius: var(--mall-radius, 8px);
  overflow: hidden;
  background: var(--mall-surface, #fff);
  border: 1px solid #ffd7d7;
  box-shadow: var(--mall-shadow-card);
}

.cc-left {
  flex: none;
  width: 130px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #fff1f0, #ffe3e0);
  color: var(--mall-price, #e4393c);
  padding: 18px 8px;
}

.cc-val {
  font-size: 34px;
  font-weight: 700;
  line-height: 1;
}

.cc-val i {
  font-style: normal;
  font-size: 15px;
}

.cc-rule {
  font-size: 12px;
  margin-top: 6px;
}

.cc-right {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
}

.cc-name {
  font-size: 15px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cc-window {
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
}

.cc-progress {
  height: 6px;
  border-radius: 3px;
  background: #fde2e2;
  overflow: hidden;
}

.cc-bar {
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, #ff6034, var(--mall-price, #e4393c));
}

.cc-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.cc-left {
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
}

@media (max-width: 768px) {
  .coupon-center {
    padding: 12px 12px 24px;
  }

  .cc-hero {
    padding: 16px;
  }

  .cc-title {
    font-size: 20px;
  }

  .cc-grid {
    grid-template-columns: 1fr;
    gap: 10px;
  }
}
</style>
