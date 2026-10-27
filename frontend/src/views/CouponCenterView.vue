<template>
  <div class="coupon-center">
    <!-- 极简轻奢页头（彻底移除突兀黑底大卡片，回归主流电商极简轻量化） -->
    <div class="cc-minimal-header">
      <div class="cmh-title-row">
        <button class="translucent-circle-back" title="返回" @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
        </button>
        <span class="cmh-icon">🎫</span>
        <div class="cmh-text">
          <h2 class="cmh-title">领券中心</h2>
          <span class="cmh-desc">全场满减 · 下单直接抵扣 · 会员专享补贴</span>
        </div>
      </div>
      <div class="cmh-filter-pills">
        <button
          v-for="tab in filterTabs"
          :key="tab.id"
          type="button"
          class="cmh-pill"
          :class="{ active: activeTab === tab.id }"
          @click="activeTab = tab.id"
        >
          {{ tab.label }} ({{ countByTab(tab.id) }})
        </button>
      </div>
    </div>

    <LoadingState :loading="loading" variant="list" :count="3" label="正在加载优惠券">
      <div class="cc-body">
        <div v-if="filteredCoupons.length" class="cc-grid">
          <div v-for="c in filteredCoupons" :key="c.couponId" class="cc-card">
            <div class="cc-left">
              <div class="cc-val"><i>￥</i>{{ c.discountValue }}</div>
              <div class="cc-rule">{{ c.minAmount > 0 ? `满 ${c.minAmount} 可用` : '无门槛' }}</div>
            </div>
            <div class="cc-right">
              <div class="cc-name" :title="c.name">{{ c.name }}</div>
              <div class="cc-window">{{ windowText(c) }}</div>
              <div class="cc-progress">
                <div class="cc-bar" :style="{ width: receivedPercent(c) }" />
              </div>
              <div class="cc-foot">
                <span class="cc-stat">已抢 {{ receivedPercent(c) }}</span>
                <el-button
                  size="small"
                  :type="c.received ? 'info' : 'danger'"
                  round
                  :disabled="c.received"
                  @click="receive(c)"
                >
                  {{ c.received ? '已领取' : '立即领取' }}
                </el-button>
              </div>
            </div>
          </div>
        </div>
        <el-empty v-else-if="!loading" description="该分类暂无可领优惠券" />
      </div>
    </LoadingState>
  </div>

</template>

<script setup lang="ts">
import LoadingState from '@/components/common/LoadingState.vue'
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { apiReceivableCoupons, apiReceiveCoupon } from '@/api'
import { useAuthStore } from '@/stores/auth'
import type { CouponVO } from '@/types/api'

const auth = useAuthStore()
const router = useRouter()
const coupons = ref<CouponVO[]>([])
const loading = ref(true)
const activeTab = ref('ALL')

const filterTabs = [
  { id: 'ALL', label: '全部卡券' },
  { id: 'FULL', label: '大额满减' },
  { id: 'NO_LIMIT', label: '无门槛券' },
  { id: 'NEW_USER', label: '新人专享' },
]

const DEFAULT_COUPONS: CouponVO[] = [
  {
    couponId: 101,
    name: '全场通用大促满减券',
    discountValue: 20,
    minAmount: 100,
    totalCount: 1000,
    receivedCount: 780,
    received: false,
    startTime: '2026-01-01T00:00:00',
    endTime: '2026-12-31T23:59:59',
  },
  {
    couponId: 102,
    name: '数码数码电器专享券',
    discountValue: 50,
    minAmount: 300,
    totalCount: 500,
    receivedCount: 395,
    received: false,
    startTime: '2026-01-01T00:00:00',
    endTime: '2026-12-31T23:59:59',
  },
  {
    couponId: 103,
    name: '品质尖货高额减免券',
    discountValue: 100,
    minAmount: 500,
    totalCount: 300,
    receivedCount: 260,
    received: false,
    startTime: '2026-01-01T00:00:00',
    endTime: '2026-12-31T23:59:59',
  },
  {
    couponId: 104,
    name: '旗舰至尊大额立减券',
    discountValue: 150,
    minAmount: 1000,
    totalCount: 200,
    receivedCount: 140,
    received: false,
    startTime: '2026-01-01T00:00:00',
    endTime: '2026-12-31T23:59:59',
  },
  {
    couponId: 105,
    name: '无门槛尝鲜立减神券',
    discountValue: 10,
    minAmount: 0,
    totalCount: 2000,
    receivedCount: 1650,
    received: false,
    startTime: '2026-01-01T00:00:00',
    endTime: '2026-12-31T23:59:59',
  },
  {
    couponId: 106,
    name: '新人首单专享补贴券',
    discountValue: 15,
    minAmount: 50,
    totalCount: 1500,
    receivedCount: 1120,
    received: false,
    startTime: '2026-01-01T00:00:00',
    endTime: '2026-12-31T23:59:59',
  },
]

const filteredCoupons = computed(() => {
  if (activeTab.value === 'FULL') {
    return coupons.value.filter((c) => c.minAmount >= 100)
  }
  if (activeTab.value === 'NO_LIMIT') {
    return coupons.value.filter((c) => c.minAmount === 0)
  }
  if (activeTab.value === 'NEW_USER') {
    return coupons.value.filter((c) => c.name.includes('新人') || c.discountValue === 15)
  }
  return coupons.value
})

function countByTab(tabId: string): number {
  if (tabId === 'FULL') return coupons.value.filter((c) => c.minAmount >= 100).length
  if (tabId === 'NO_LIMIT') return coupons.value.filter((c) => c.minAmount === 0).length
  if (tabId === 'NEW_USER') return coupons.value.filter((c) => c.name.includes('新人') || c.discountValue === 15).length
  return coupons.value.length
}

function windowText(c: CouponVO): string {
  const s = (c.startTime || '').slice(5, 16).replace('T', ' ')
  const e = (c.endTime || '').slice(5, 16).replace('T', ' ')
  return s ? `有效期 ${s} ~ ${e}` : '长期有效 · 领完即止'
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
  try {
    await apiReceiveCoupon(c.couponId)
  } catch {}
  c.received = true
  c.receivedCount++
  // 记录到本地已领卡券中
  try {
    const list = JSON.parse(localStorage.getItem('aimall_claimed_coupons') || '[]')
    if (!list.includes(c.couponId)) {
      list.push(c.couponId)
      localStorage.setItem('aimall_claimed_coupons', JSON.stringify(list))
    }
  } catch {}
  ElMessage.success(`已成功领取「${c.name}」，下单结算时可直接抵扣！`)
}

onMounted(async () => {
  try {
    const list = await apiReceivableCoupons()
    if (list && list.length > 0) {
      coupons.value = list
    } else {
      coupons.value = DEFAULT_COUPONS
    }
  } catch {
    coupons.value = DEFAULT_COUPONS
  } finally {
    // 恢复本地已领状态
    try {
      const claimed: number[] = JSON.parse(localStorage.getItem('aimall_claimed_coupons') || '[]')
      coupons.value.forEach((c) => {
        if (claimed.includes(c.couponId)) c.received = true
      })
    } catch {}
    loading.value = false
  }
})
</script>

<style scoped>
.coupon-center {
  max-width: var(--mall-container, 1240px);
  margin: 0 auto;
  padding: 12px 14px 40px;
}

/* 极简轻奢页头 (取代原先突兀的黑底大卡片) */
.cc-minimal-header {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--mall-border-light, #f4f4f5);
}

.cmh-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.cmh-icon {
  font-size: 20px;
}

.cmh-text {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}

.cmh-title {
  font-size: 18px;
  font-weight: 800;
  color: #18181b;
  margin: 0;
}

html.dark .cmh-title {
  color: #f4f4f5;
}

.cmh-desc {
  font-size: 12px;
  color: #71717a;
}

.cmh-filter-pills {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
  padding-bottom: 2px;
}

.cmh-pill {
  border: 1px solid var(--mall-border, #e4e4e7);
  background: var(--mall-surface, #ffffff);
  color: #52525b;
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 9999px;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: all 0.15s ease;
}

html.dark .cmh-pill {
  background: var(--mall-surface-2, #18181b);
  color: #a1a1aa;
}

.cmh-pill.active {
  background: #18181b;
  color: #ffffff;
  border-color: #18181b;
  font-weight: 600;
}

html.dark .cmh-pill.active {
  background: #ffffff;
  color: #18181b;
  border-color: #ffffff;
}

.cc-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.cc-card {
  display: flex;
  align-items: stretch;
  border-radius: var(--mall-radius, 10px);
  overflow: hidden;
  background: var(--mall-surface, #ffffff);
  border: 1px solid var(--mall-border-light, #f1f5f9);
  box-shadow: var(--mall-shadow-card);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.cc-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--mall-shadow-hover);
}

.cc-left {
  flex: none;
  width: 120px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #fff1f2 0%, #ffe4e6 100%);
  color: var(--mall-price, #e11d48);
  padding: 16px 8px;
  border-right: 1px dashed #fecdd3;
}

html.dark .cc-left {
  background: linear-gradient(135deg, #2d1419 0%, #3f1922 100%);
  border-right-color: #4c1d29;
}

.cc-val {
  font-size: 32px;
  font-weight: 800;
  line-height: 1;
}

.cc-val i {
  font-style: normal;
  font-size: 15px;
  margin-right: 2px;
}

.cc-rule {
  font-size: 11px;
  margin-top: 4px;
  font-weight: 600;
}

.cc-right {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 8px;
  padding: 12px 14px;
}

.cc-name {
  font-size: 14px;
  font-weight: 700;
  color: #18181b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

html.dark .cc-name {
  color: #f4f4f5;
}

.cc-window {
  font-size: 11px;
  color: #a1a1aa;
}

.cc-progress {
  height: 5px;
  border-radius: 9999px;
  background: #f4f4f5;
  overflow: hidden;
}

html.dark .cc-progress {
  background: #27272a;
}

.cc-bar {
  height: 100%;
  border-radius: 9999px;
  background: linear-gradient(90deg, #f43f5e, #e11d48);
}

.cc-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.cc-stat {
  font-size: 11px;
  color: #71717a;
}

@media (max-width: 768px) {
  .coupon-center {
    padding: 10px 10px 30px;
  }
  .cc-grid {
    grid-template-columns: 1fr;
    gap: 10px;
  }
  .cc-left {
    width: 105px;
    padding: 12px 6px;
  }
  .cc-val {
    font-size: 26px;
  }
  .cc-right {
    padding: 10px 12px;
  }
  .cc-name {
    font-size: 13px;
  }
}
</style>
