<template>
  <div class="home">
    <!-- ============ 现代电商主流方案：金刚区快捷入口 (5列图标导航) ============ -->
    <section class="mainstream-quick-nav container">
      <div class="quick-nav-grid">
        <div class="qn-item" @click="$router.push('/seckill')">
          <div class="qn-icon-box qn-seckill"><span class="qn-emoji">⚡</span></div>
          <span class="qn-label">限时秒杀</span>
        </div>
        <div class="qn-item" @click="$router.push('/coupons')">
          <div class="qn-icon-box qn-coupon"><span class="qn-emoji">🎫</span></div>
          <span class="qn-label">领券中心</span>
        </div>
        <div class="qn-item" @click="$router.push('/assistant')">
          <div class="qn-icon-box qn-ai"><span class="qn-emoji">✨</span></div>
          <span class="qn-label">AI 导购</span>
        </div>
        <div class="qn-item" @click="$router.push('/products')">
          <div class="qn-icon-box qn-cat"><span class="qn-emoji">🛍️</span></div>
          <span class="qn-label">全部分类</span>
        </div>
        <div class="qn-item" @click="goToOrders">
          <div class="qn-icon-box qn-order"><span class="qn-emoji">📦</span></div>
          <span class="qn-label">我的订单</span>
        </div>
      </div>
    </section>

    <!-- ============ 现代电商主流方案：双子星特惠/活动微卡片 (紧凑单行自适应，绝不换行) ============ -->
    <section class="mainstream-dual-promo container">
      <div class="dual-promo-grid">
        <!-- 专区 1: 限时秒杀 -->
        <div class="dp-card dp-seckill" @click="$router.push('/seckill')">
          <div class="dp-card-head">
            <span class="dp-title">⚡ 秒杀</span>
            <span class="dp-timer">{{ countdownText }}</span>
          </div>
          <div class="dp-sub">品牌尖货 · 整点直降</div>
        </div>

        <!-- 专区 2: 超值礼券 -->
        <div class="dp-card dp-coupon" @click="$router.push('/coupons')">
          <div class="dp-card-head">
            <span class="dp-title">🎫 领券</span>
            <span class="dp-badge-free">最高减 100</span>
          </div>
          <div class="dp-sub">每日神券 · 下单立减</div>
        </div>
      </div>
    </section>

    <!-- ============ 核心商品真实双列瀑布流 (Masonry Waterfall，严格一行2列) ============ -->
    <main class="feed-container container">
      <!-- 初始全屏骨架屏测试 -->
      <div v-if="initialLoading" class="waterfall-container">
        <div class="waterfall-column">
          <div v-for="n in 3" :key="'sk-l-' + n" class="skeleton-card">
            <div class="sk-img mall-skeleton" :style="{ aspectRatio: n % 2 === 0 ? '3/4' : '1/1' }" />
            <div class="sk-info">
              <div class="sk-line-1 mall-skeleton" />
              <div class="sk-line-2 mall-skeleton" />
              <div class="sk-line-3 mall-skeleton" />
            </div>
          </div>
        </div>
        <div class="waterfall-column">
          <div v-for="n in 3" :key="'sk-r-' + n" class="skeleton-card">
            <div class="sk-img mall-skeleton" :style="{ aspectRatio: n % 2 === 0 ? '1/1' : '4/5' }" />
            <div class="sk-info">
              <div class="sk-line-1 mall-skeleton" />
              <div class="sk-line-2 mall-skeleton" />
              <div class="sk-line-3 mall-skeleton" />
            </div>
          </div>
        </div>
      </div>

      <!-- 真实高低错落双列瀑布流 -->
      <div v-else class="waterfall-container">
        <!-- 左列瀑布流 -->
        <div class="waterfall-column">
          <div
            v-for="p in leftColumnProducts"
            :key="p.id"
            class="pdd-card"
            @click="$router.push(`/products/${p.id}`)"
          >
            <div class="pdd-pic-wrap" :style="{ aspectRatio: p.aspectRatio || '1/1' }">
              <el-image
                :src="p.imageUrl"
                fit="cover"
                class="pdd-pic"
                lazy
                decoding="async"
              >
                <template #placeholder>
                  <div class="pdd-placeholder mall-skeleton" />
                </template>
                <template #error>
                  <div class="pdd-error-fallback">{{ p.name.slice(0, 1) }}</div>
                </template>
              </el-image>
              </div>

            <div class="pdd-info">
              <div class="pdd-brand" v-if="p.brand">{{ p.brand }}</div>
              <div class="pdd-title" :title="p.name">{{ p.name }}</div>

              <div class="pdd-bottom">
                <div class="pdd-price-group">
                  <span class="pdd-price"><i>￥</i>{{ p.price }}</span>
                  </div>
                <span class="pdd-sales">销量 {{ formatSales(p.sales) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 右列瀑布流 -->
        <div class="waterfall-column">
          <div
            v-for="p in rightColumnProducts"
            :key="p.id"
            class="pdd-card"
            @click="$router.push(`/products/${p.id}`)"
          >
            <div class="pdd-pic-wrap" :style="{ aspectRatio: p.aspectRatio || '1/1' }">
              <el-image
                :src="p.imageUrl"
                fit="cover"
                class="pdd-pic"
                lazy
                decoding="async"
              >
                <template #placeholder>
                  <div class="pdd-placeholder mall-skeleton" />
                </template>
                <template #error>
                  <div class="pdd-error-fallback">{{ p.name.slice(0, 1) }}</div>
                </template>
              </el-image>
              </div>

            <div class="pdd-info">
              <div class="pdd-brand" v-if="p.brand">{{ p.brand }}</div>
              <div class="pdd-title" :title="p.name">{{ p.name }}</div>

              <div class="pdd-bottom">
                <div class="pdd-price-group">
                  <span class="pdd-price"><i>￥</i>{{ p.price }}</span>
                  </div>
                <span class="pdd-sales">销量 {{ formatSales(p.sales) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 滑动触底加载中过渡骨架屏 (左右各一卡片) -->
      <div v-if="loadingMore" class="waterfall-container loading-more-waterfall">
        <div class="waterfall-column">
          <div class="skeleton-card">
            <div class="sk-img mall-skeleton" style="aspect-ratio: 4/5" />
            <div class="sk-info">
              <div class="sk-line-1 mall-skeleton" />
              <div class="sk-line-2 mall-skeleton" />
              <div class="sk-line-3 mall-skeleton" />
            </div>
          </div>
        </div>
        <div class="waterfall-column">
          <div class="skeleton-card">
            <div class="sk-img mall-skeleton" style="aspect-ratio: 1/1" />
            <div class="sk-info">
              <div class="sk-line-1 mall-skeleton" />
              <div class="sk-line-2 mall-skeleton" />
              <div class="sk-line-3 mall-skeleton" />
            </div>
          </div>
        </div>
      </div>

      <!-- 触底状态提示 -->
      <div v-if="isFinished && displayedProducts.length > 0" class="feed-end">
        — 已经到底了 · 甄选好物已全部加载完毕 (共 {{ displayedProducts.length }} 款) —
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { MASSIVE_PRODUCTS, type EnhancedProduct } from '@/data/products'

const router = useRouter()

const initialLoading = ref(true)
const loadingMore = ref(false)
const currentPage = ref(1)
const PAGE_SIZE = 12

// 实时倒计时计算
const nowTick = ref(Date.now())
let timer: number | undefined

const countdownText = computed(() => {
  const diff = Math.max(0, 10800000 - (nowTick.value % 10800000))
  const h = Math.floor(diff / 3600000)
  const m = Math.floor((diff % 3600000) / 60000)
  const s = Math.floor((diff % 60000) / 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(h)}:${pad(m)}:${pad(s)}`
})

function goToOrders() {
  const token = localStorage.getItem('token')
  if (!token) {
    ElMessage.warning('请先登录后查看订单')
    router.push({ path: '/login', query: { redirect: '/orders' } })
    return
  }
  router.push('/orders')
}

// 520 款商品分页展示
const allFilteredProducts = computed(() => MASSIVE_PRODUCTS)

const displayedProducts = computed(() => {
  return allFilteredProducts.value.slice(0, currentPage.value * PAGE_SIZE)
})

const leftColumnProducts = computed(() => {
  return displayedProducts.value.filter((_, idx) => idx % 2 === 0)
})

const rightColumnProducts = computed(() => {
  return displayedProducts.value.filter((_, idx) => idx % 2 === 1)
})

const isFinished = computed(() => {
  return displayedProducts.value.length >= allFilteredProducts.value.length
})

async function loadNextPage() {
  if (loadingMore.value || isFinished.value) return
  loadingMore.value = true
  await new Promise((resolve) => setTimeout(resolve, 300))
  currentPage.value++
  loadingMore.value = false
}

function handleScroll() {
  if (initialLoading.value || loadingMore.value || isFinished.value) return
  const scrollY = window.scrollY || document.documentElement.scrollTop
  const windowHeight = window.innerHeight
  const docHeight = document.documentElement.scrollHeight
  if (scrollY + windowHeight >= docHeight - 350) {
    loadNextPage()
  }
}

function formatSales(sales?: number): string {
  const s = Number(sales) || 0
  if (s < 100) return '100+'
  if (s < 1000) return `${Math.floor(s / 100) * 100}+`
  if (s < 10000) return `${Math.floor(s / 1000)}000+`
  return `${Math.floor(s / 10000)}w+`
}

onMounted(() => {
  timer = window.setInterval(() => (nowTick.value = Date.now()), 1000)
  window.addEventListener('scroll', handleScroll, { passive: true })
  setTimeout(() => {
    initialLoading.value = false
  }, 250)
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
  window.removeEventListener('scroll', handleScroll)
})
</script>

<style scoped>
.home {
  min-height: 100%;
  padding-bottom: 60px;
  background: var(--mall-page-bg, #fafafa);
}

/* ================= 现代主流方案 1：金刚区 5 列快捷入口 ================= */
.mainstream-quick-nav {
  max-width: 860px;
  margin: 12px auto 0;
  padding: 0 12px;
}

.quick-nav-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
  padding: 10px 6px;
  background: var(--mall-surface, #ffffff);
  border: 1px solid var(--mall-border-light, #f4f4f5);
  border-radius: var(--mall-radius-lg, 14px);
  box-shadow: var(--mall-shadow-xs);
}

.qn-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  transition: transform 0.15s ease;
}

.qn-item:active {
  transform: scale(0.92);
}

.qn-icon-box {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  transition: transform 0.2s ease;
}

.qn-item:hover .qn-icon-box {
  transform: translateY(-2px);
}

.qn-seckill {
  background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
}

.qn-coupon {
  background: linear-gradient(135deg, #ffedd5 0%, #fed7aa 100%);
}

.qn-ai {
  background: linear-gradient(135deg, #e0e7ff 0%, #c7d2fe 100%);
}

.qn-cat {
  background: linear-gradient(135deg, #f3e8ff 0%, #e9d5ff 100%);
}

.qn-order {
  background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%);
}

.qn-label {
  font-size: 12px;
  font-weight: 600;
  color: #3f3f46;
}

html.dark .qn-label {
  color: #e4e4e7;
}

/* ================= 现代主流方案 2：双子星特惠微卡片 (紧凑单行无折行) ================= */
.mainstream-dual-promo {
  max-width: 860px;
  margin: 8px auto 12px;
  padding: 0 12px;
}

.dual-promo-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.dp-card {
  padding: 8px 12px;
  border-radius: var(--mall-radius, 10px);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  justify-content: center;
  border: 1px solid var(--mall-border-light, #f4f4f5);
  background: var(--mall-surface, #ffffff);
  box-shadow: var(--mall-shadow-xs);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  min-width: 0;
  overflow: hidden;
}

.dp-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--mall-shadow-hover);
}

.dp-seckill {
  background: radial-gradient(circle at 90% 10%, rgba(225, 29, 72, 0.08), transparent 60%), var(--mall-surface, #ffffff);
}

.dp-coupon {
  background: radial-gradient(circle at 90% 10%, rgba(249, 115, 22, 0.08), transparent 60%), var(--mall-surface, #ffffff);
}

.dp-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
  white-space: nowrap;
}

.dp-title {
  font-size: 13px;
  font-weight: 800;
  color: #18181b;
  white-space: nowrap;
}

html.dark .dp-title {
  color: #f4f4f5;
}

.dp-timer {
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  background: var(--mall-price, #e11d48);
  padding: 1px 5px;
  border-radius: 4px;
  letter-spacing: 0.02em;
  white-space: nowrap;
  flex-shrink: 0;
}

.dp-badge-free {
  font-size: 10px;
  font-weight: 700;
  color: #c2410c;
  background: #ffedd5;
  padding: 1px 5px;
  border-radius: 4px;
  white-space: nowrap;
  flex-shrink: 0;
}

.dp-sub {
  font-size: 11px;
  color: #a1a1aa;
  margin-top: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ================= 真实双列瀑布流容器 (Masonry Waterfall) ================= */
.feed-container {
  margin-top: 10px;
}

.waterfall-container {
  display: flex;
  gap: 12px;
  max-width: 860px;
  margin: 0 auto;
  align-items: flex-start;
}

.waterfall-column {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.loading-more-waterfall {
  margin-top: 12px;
}

/* 瀑布流卡片 */
.pdd-card {
  background: var(--mall-surface, #ffffff);
  border: 1px solid var(--mall-border-light, #f4f4f5);
  border-radius: var(--mall-radius, 10px);
  overflow: hidden;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.pdd-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--mall-shadow-hover);
  border-color: var(--mall-border, #e4e4e7);
}

.pdd-pic-wrap {
  position: relative;
  width: 100%;
  background: var(--mall-surface-2, #f4f4f5);
  overflow: hidden;
}

.pdd-pic {
  width: 100%;
  height: 100%;
  transition: transform 0.4s ease;
}

.pdd-card:hover .pdd-pic :deep(img) {
  transform: scale(1.04);
}

.pdd-placeholder {
  width: 100%;
  height: 100%;
}

.pdd-error-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  font-weight: 700;
  color: #a1a1aa;
}


.pdd-info {
  padding: 10px 12px 12px;
  display: flex;
  flex-direction: column;
}

.pdd-brand {
  font-size: 10px;
  font-weight: 700;
  color: #a1a1aa;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 3px;
}

.pdd-title {
  font-size: 13px;
  font-weight: 600;
  color: #18181b;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

html.dark .pdd-title {
  color: #f4f4f5;
}

.pdd-bottom {
  margin-top: 10px;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.pdd-price-group {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.pdd-price {
  font-size: 18px;
  font-weight: 800;
  color: var(--mall-price, #e11d48);
  letter-spacing: -0.02em;
  white-space: nowrap;
  word-break: keep-all;
  flex-shrink: 0;
}

.pdd-price i {
  font-style: normal;
  font-size: 12px;
  margin-right: 1px;
}


.pdd-sales {
  font-size: 11px;
  color: #a1a1aa;
}

/* ================= 骨架屏 ================= */
.skeleton-card {
  background: var(--mall-surface, #ffffff);
  border: 1px solid var(--mall-border-light, #f4f4f5);
  border-radius: var(--mall-radius, 10px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.sk-img {
  width: 100%;
}

.sk-info {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sk-line-1 {
  width: 40%;
  height: 12px;
}

.sk-line-2 {
  width: 90%;
  height: 16px;
}

.sk-line-3 {
  width: 60%;
  height: 18px;
  margin-top: 4px;
}

.feed-end {
  text-align: center;
  font-size: 12px;
  color: #a1a1aa;
  padding: 36px 0 24px;
}

@media (max-width: 768px) {
  .mainstream-quick-nav,
  .mainstream-dual-promo {
    padding: 0 8px;
  }
  .qn-icon-box {
    width: 40px;
    height: 40px;
    font-size: 18px;
  }
  .qn-label {
    font-size: 11px;
  }
  .dp-card {
    padding: 10px 10px;
  }
  .dp-title {
    font-size: 13px;
  }
  .dp-action {
    padding: 3px 8px;
    font-size: 10px;
  }
  .waterfall-container {
    gap: 8px;
  }
  .waterfall-column {
    gap: 8px;
  }
  .pdd-info {
    padding: 8px 10px 10px;
  }
  .pdd-title {
    font-size: 12px;
  }
  .pdd-price {
    font-size: 16px;
  }
}
</style>
