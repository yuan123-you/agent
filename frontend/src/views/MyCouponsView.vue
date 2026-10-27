<template>
  <el-scrollbar class="page-scroll">
    <div class="my-coupons-page">
      <!-- 页面顶栏：半透明圆形返回按钮 + 标题 + 去领券中心链接 -->
      <div class="page-header-row">
        <button class="translucent-circle-back" title="返回" @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
        </button>
        <h3 class="page-title">我的优惠券</h3>
        <div style="flex: 1;" />
        <el-button text type="primary" size="small" @click="$router.push('/coupons')">
          去领券中心 ›
        </el-button>
      </div>

      <!-- 状态筛选 Tabs -->
      <el-tabs v-model="statusTab" class="coupon-filter-tabs">
        <el-tab-pane label="待使用" name="UNUSED" />
        <el-tab-pane label="已使用" name="USED" />
        <el-tab-pane label="已过期" name="EXPIRED" />
        <el-tab-pane label="全部" name="ALL" />
      </el-tabs>

      <!-- 卡券列表 -->
      <LoadingState :loading="loading" variant="list" :count="3" label="正在加载我的优惠券">
        <div class="coupon-list">
          <div
            v-for="c in filteredCoupons"
            :key="c.userCouponId"
            class="coupon-card"
            :class="c.status.toLowerCase()"
          >
            <div class="cc-left">
              <div class="cc-val"><i>￥</i>{{ c.discountValue }}</div>
              <div class="cc-rule">
                {{ (c.minAmount || 0) > 0 ? `满 ${c.minAmount} 可用` : '无门槛' }}
              </div>
            </div>
            <div class="cc-right">
              <div class="cc-name">{{ c.name }}</div>
              <div class="cc-expire">有效期至 {{ (c.expireAt || '').slice(0, 16).replace('T', ' ') || '2026-12-31 23:59' }}</div>
              <div class="cc-foot">
                <el-tag size="small" :type="statusTagType(c.status)" effect="plain">
                  {{ statusText(c.status) }}
                </el-tag>
                <el-button
                  v-if="c.status === 'UNUSED'"
                  size="small"
                  type="danger"
                  round
                  @click="$router.push('/products')"
                >
                  去使用
                </el-button>
              </div>
            </div>
          </div>

          <el-empty
            v-if="!loading && filteredCoupons.length === 0"
            :description="statusTab === 'UNUSED' ? '暂无可用的优惠券' : '暂无相关优惠券'"
          >
            <el-button type="primary" round @click="$router.push('/coupons')">前往领券中心</el-button>
          </el-empty>
        </div>
      </LoadingState>

    </div>
  </el-scrollbar>
</template>

<script setup lang="ts">
import LoadingState from '@/components/common/LoadingState.vue'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { apiMyCoupons } from '@/api'
import type { MyCouponVO } from '@/types/api'

const router = useRouter()
const coupons = ref<MyCouponVO[]>([])
const loading = ref(true)
const statusTab = ref('UNUSED')

function goBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/profile')
  }
}

function statusTagType(status: string): 'danger' | 'info' | 'success' {
  if (status === 'UNUSED') return 'danger'
  if (status === 'USED') return 'info'
  return 'info'
}

function statusText(status: string): string {
  if (status === 'UNUSED') return '待使用'
  if (status === 'USED') return '已使用'
  if (status === 'EXPIRED') return '已过期'
  return status
}

const filteredCoupons = computed(() => {
  if (statusTab.value === 'ALL') return coupons.value
  return coupons.value.filter((c) => c.status === statusTab.value)
})

onMounted(async () => {
  try {
    const list = await apiMyCoupons()
    if (list && list.length > 0) {
      coupons.value = list
      loading.value = false
      return
    }
  } catch {}

  // 本地已领优惠券回显联动
  try {
    const claimed: number[] = JSON.parse(localStorage.getItem('aimall_claimed_coupons') || '[]')
    const MOCK_MAP: Record<number, { name: string; discountValue: number; minAmount: number }> = {
      101: { name: '全场通用大促满减券', discountValue: 20, minAmount: 100 },
      102: { name: '数码电器专享立减券', discountValue: 50, minAmount: 300 },
      103: { name: '品质尖货高额减免券', discountValue: 100, minAmount: 500 },
      104: { name: '旗舰至尊大额立减券', discountValue: 150, minAmount: 1000 },
      105: { name: '无门槛尝鲜立减神券', discountValue: 10, minAmount: 0 },
      106: { name: '新人首单专享补贴券', discountValue: 15, minAmount: 50 },
    }
    // 默认赠送新人券
    const combinedIds = Array.from(new Set([106, ...claimed]))
    coupons.value = combinedIds.map((id) => {
      const item = MOCK_MAP[id] || { name: '官方甄选大促券', discountValue: 20, minAmount: 100 }
      return {
        userCouponId: id,
        couponId: id,
        name: item.name,
        discountValue: item.discountValue,
        minAmount: item.minAmount,
        status: 'UNUSED',
        expireAt: '2026-12-31T23:59:59',
      }
    })
  } catch {}
  loading.value = false
})
</script>

<style scoped>
.page-scroll {
  height: 100%;
}

.my-coupons-page {
  max-width: 760px;
  margin: 0 auto;
  padding: 16px 14px 40px;
}

.coupon-filter-tabs :deep(.el-tabs__header) {
  margin: 0 0 16px 0 !important;
}

.coupon-filter-tabs :deep(.el-tabs__nav-wrap) {
  padding: 0 !important;
}

.coupon-filter-tabs :deep(.el-tabs__nav) {
  display: flex !important;
  width: 100% !important;
}

.coupon-filter-tabs :deep(.el-tabs__item) {
  flex: 1 1 0% !important;
  text-align: center !important;
  font-size: 13px !important;
}

.coupon-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.coupon-card {
  display: flex;
  align-items: stretch;
  background: var(--mall-surface, #ffffff);
  border: 1px solid var(--mall-border-light, #f4f4f5);
  border-radius: var(--mall-radius, 10px);
  overflow: hidden;
  box-shadow: var(--mall-shadow-card);
  transition: transform 0.2s ease;
}

.coupon-card:hover {
  transform: translateY(-2px);
}

.cc-left {
  width: 110px;
  flex: none;
  background: linear-gradient(135deg, #fff1f2 0%, #ffe4e6 100%);
  color: var(--mall-price, #e11d48);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 16px 8px;
  border-right: 1px dashed #fecdd3;
}

html.dark .cc-left {
  background: linear-gradient(135deg, #2d1419 0%, #3f1922 100%);
  border-right-color: #4c1d29;
}

.coupon-card.used .cc-left,
.coupon-card.expired .cc-left {
  background: var(--mall-surface-2, #f4f4f5);
  color: #a1a1aa;
  border-right-color: #e4e4e7;
}

.cc-val {
  font-size: 30px;
  font-weight: 800;
  line-height: 1;
}

.cc-val i {
  font-style: normal;
  font-size: 14px;
}

.cc-rule {
  font-size: 11px;
  font-weight: 600;
  margin-top: 4px;
}

.cc-right {
  flex: 1;
  min-width: 0;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 6px;
}

.cc-name {
  font-size: 14px;
  font-weight: 700;
  color: #18181b;
}

html.dark .cc-name {
  color: #f4f4f5;
}

.cc-expire {
  font-size: 11px;
  color: #71717a;
}

.cc-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 4px;
}
</style>
