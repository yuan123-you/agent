<template>
  <div class="home" v-loading="loading">
    <!-- 轮播 Banner -->
    <section class="banner-section container">
      <el-carousel :interval="4500" trigger="click" arrow="hover" :height="bannerHeight">
        <el-carousel-item v-for="b in banners" :key="b.title">
          <div class="banner" :style="{ background: b.bg }" @click="$router.push(b.link)">
            <div class="banner-content">
              <h2>{{ b.title }}</h2>
              <p>{{ b.desc }}</p>
              <span class="banner-cta">立即查看 →</span>
            </div>
            <div class="banner-emoji">{{ b.emoji }}</div>
          </div>
        </el-carousel-item>
      </el-carousel>
    </section>

    <!-- 分类宫格（来自商城目录；接口为空时回落到内置常量） -->
    <section class="container">
      <div class="cat-grid">
        <div v-for="c in catCells" :key="c.key" class="cat-cell" @click="$router.push(c.link)">
          <span class="cat-icon">{{ c.icon }}</span>
          <span class="cat-name">{{ c.name }}</span>
        </div>
      </div>
    </section>

    <!-- 限时秒杀楼层 -->
    <section v-if="seckills.length" class="container floor">
      <div class="floor-head">
        <h3>⚡ 限时秒杀 <span v-if="countdownText" class="countdown">{{ countdownText }}</span></h3>
      </div>
      <div class="seckill-track">
        <div v-for="s in seckills" :key="s.seckillId" class="seckill-card mall-card"
          @click="$router.push(`/products/${s.productId}`)">
          <el-image :src="s.imageUrl" fit="cover" class="seckill-pic" lazy decoding="async" />
          <div class="seckill-name">{{ s.name }}</div>
          <div class="seckill-prices">
            <span class="seckill-now">￥{{ s.seckillPrice }}</span>
            <span class="seckill-old">￥{{ s.originalPrice }}</span>
          </div>
          <div class="seckill-stock">
            <div class="bar" :style="{ width: stockPercent(s) }" />
          </div>
          <span class="seckill-state" :class="{ soon: !s.started }">
            {{ s.started ? '抢' : '即将开始' }}
          </span>
        </div>
      </div>
    </section>

    <!-- 领券中心 -->
    <section v-if="coupons.length" class="container floor">
      <div class="floor-head">
        <h3>🎫 领券中心</h3>
      </div>
      <div class="coupon-row">
        <div v-for="c in coupons" :key="c.couponId" class="coupon-card">
          <div class="coupon-left">
            <div class="coupon-val"><i>￥</i>{{ c.discountValue }}</div>
            <div class="coupon-rule">{{ c.minAmount > 0 ? `满${c.minAmount}可用` : '无门槛' }}</div>
          </div>
          <div class="coupon-right">
            <div class="coupon-name">{{ c.name }}</div>
            <el-button size="small" type="danger" round :disabled="c.received" @click="receive(c)">
              {{ c.received ? '已领取' : '立即领取' }}
            </el-button>
          </div>
        </div>
      </div>
    </section>

    <!-- AI 助手入口横幅 -->
    <section class="container">
      <div class="ai-entry" @click="$router.push('/assistant')">
        <span class="ai-emoji">🤖</span>
        <div class="ai-text">
          <div class="ai-title">AI 购物助手</div>
          <div class="ai-desc">告诉我想买什么，帮你找商品、查订单、答政策</div>
        </div>
        <el-button type="primary" round>去咨询</el-button>
      </div>
    </section>

    <!-- 商品楼层（按分类） -->
    <section v-for="f in floors" :key="f.code" class="container floor">
      <div class="floor-head">
        <h3>{{ f.icon }} {{ f.name }}</h3>
        <el-button text type="primary" @click="$router.push(`/products?category=${f.code}`)">
          更多 ›
        </el-button>
      </div>
      <div class="floor-grid">
        <ProductCard v-for="p in f.products" :key="p.id" :product="p" />
      </div>
    </section>

    <!-- 猜你喜欢 -->
    <section class="container floor">
      <div class="floor-head">
        <h3>✨ 猜你喜欢</h3>
      </div>
      <div class="floor-grid like-grid">
        <ProductCard v-for="p in likes" :key="p.id" :product="p" />
      </div>
    </section>

    <footer class="home-footer">AI Mall · 智能电商平台 · 演示环境</footer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiCatalogCategories, apiProducts, apiReceivableCoupons, apiReceiveCoupon, apiSeckills } from '@/api'
import { CATEGORIES } from '@/constants/categories'
import ProductCard from '@/components/product/ProductCard.vue'
import type { CategoryVO, CouponVO, ProductVO, SeckillVO } from '@/types/api'

const loading = ref(false)
const windowWidth = ref(window.innerWidth)
const onResize = () => (windowWidth.value = window.innerWidth)
window.addEventListener('resize', onResize)
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  if (timer) window.clearInterval(timer)
})

const bannerHeight = computed(() => (windowWidth.value <= 768 ? '140px' : '240px'))

const banners = [
  { title: '数码焕新季', desc: '旗舰影像 · 折上折', emoji: '📱', bg: 'linear-gradient(120deg, #4f7cff, #8f6bff)', link: '/products?category=PHONE' },
  { title: '家电狂欢周', desc: '一级能效 · 以旧换新', emoji: '🧺', bg: 'linear-gradient(120deg, #12b7a3, #48c9b0)', link: '/products?category=APPLIANCE' },
  { title: '生鲜直达', desc: '产地直发 · 新鲜到家', emoji: '🍎', bg: 'linear-gradient(120deg, #ff7a59, #ffb347)', link: '/products?category=FOOD' },
]

// 楼层：4 个主力分类，每层 8 件
const floorCodes = ['PHONE', 'APPLIANCE', 'CLOTHING', 'SPORTS']
const floors = ref<{ code: string; name: string; icon: string; products: ProductVO[] }[]>([])
const likes = ref<ProductVO[]>([])

// 分类宫格：优先商城目录（nav_status=1），为空时回落到内置常量
interface CatCell { key: string; name: string; icon: string; link: string }
const catCells = ref<CatCell[]>(
  CATEGORIES.map((c) => ({ key: c.code, name: c.name, icon: c.icon, link: `/products?category=${c.code}` })),
)

// ---------- 秒杀楼层 ----------
const seckills = ref<SeckillVO[]>([])
const nowTick = ref(Date.now())
let timer: number | undefined

const countdownText = computed(() => {
  const active = seckills.value.find((s) => s.started)
  if (!active) return ''
  const diff = Math.max(0, new Date(active.endTime).getTime() - nowTick.value)
  const h = Math.floor(diff / 3600000)
  const m = Math.floor((diff % 3600000) / 60000)
  const s = Math.floor((diff % 60000) / 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `距结束 ${pad(h)}:${pad(m)}:${pad(s)}`
})

function stockPercent(s: SeckillVO): string {
  const original = Math.max(1, s.seckillStock + 1)
  return `${Math.min(100, Math.round((s.seckillStock / original) * 100))}%`
}

// ---------- 领券中心 ----------
const coupons = ref<CouponVO[]>([])

async function receive(c: CouponVO) {
  await apiReceiveCoupon(c.couponId)
  c.received = true
  ElMessage.success(`已领取「${c.name}」，可在个人中心查看`)
}

onMounted(async () => {
  timer = window.setInterval(() => (nowTick.value = Date.now()), 1000)
  apiSeckills().then((list) => (seckills.value = (list || []).slice(0, 10))).catch(() => {})
  apiReceivableCoupons().then((list) => (coupons.value = (list || []).slice(0, 8))).catch(() => {})
  loading.value = true
  apiCatalogCategories()
    .then((tree) => {
      if (tree && tree.length) {
        catCells.value = tree.slice(0, 16).map((c: CategoryVO) => ({
          key: String(c.id),
          name: c.name,
          icon: c.icon || '🛍️',
          link: `/products?categoryId=${c.id}`,
        }))
      }
    })
    .catch(() => {})
  try {
    const results = await Promise.all([
      ...floorCodes.map((code) =>
        apiProducts({ category: code, size: 8, sort: 'created_desc' })
          .catch(() => ({ records: [] as ProductVO[] })),
      ),
      apiProducts({ size: 12, sort: 'price_asc' }).catch(() => ({ records: [] as ProductVO[] })),
    ])
    floors.value = floorCodes.map((code, i) => {
      const def = CATEGORIES.find((c) => c.code === code)!
      return { code, name: def.name, icon: def.icon, products: results[i].records }
    })
    likes.value = results[results.length - 1].records
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.home {
  min-height: 100%;
}

.home .container {
  margin-bottom: 24px;
}

.banner {
  height: 100%;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 48px;
  cursor: pointer;
  color: #fff;
  overflow: hidden;
}

.banner-content h2 {
  margin: 0 0 8px;
  font-size: 30px;
}

.banner-content p {
  margin: 0 0 14px;
  opacity: 0.9;
}

.banner-cta {
  font-size: 14px;
  border: 1px solid rgba(255, 255, 255, 0.7);
  padding: 6px 16px;
  border-radius: 16px;
}

.banner-emoji {
  font-size: 88px;
  filter: drop-shadow(0 8px 16px rgba(0, 0, 0, 0.2));
}

/* 分类宫格：PC 10 列，平板 5 列，手机 5 列（两行） */
.cat-grid {
  display: grid;
  grid-template-columns: repeat(10, minmax(0, 1fr));
  gap: 8px;
  background: #fff;
  border-radius: 12px;
  padding: 16px 12px;
}

.cat-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 8px 4px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.cat-cell:hover {
  background: #f5f7fa;
}

.cat-icon {
  font-size: 26px;
}

.cat-name {
  font-size: 12px;
  color: #606266;
}

/* AI 助手入口 */
.ai-entry {
  display: flex;
  align-items: center;
  gap: 14px;
  background: linear-gradient(120deg, #eef3ff, #f6efff);
  border: 1px solid #dde6ff;
  border-radius: 12px;
  padding: 16px 20px;
  cursor: pointer;
}

.ai-emoji {
  font-size: 34px;
}

.ai-text {
  flex: 1;
}

.ai-title {
  font-weight: 700;
  color: var(--el-color-primary);
}

.ai-desc {
  font-size: 13px;
  color: #909399;
  margin-top: 2px;
}

/* 楼层 */
.floor-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

/* 秒杀楼层 */
.countdown {
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  background: var(--el-color-danger);
  padding: 2px 10px;
  border-radius: 12px;
  margin-left: 8px;
  font-variant-numeric: tabular-nums;
}

.seckill-track {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 6px;
  scrollbar-width: none;
}

.seckill-track::-webkit-scrollbar {
  display: none;
}

.seckill-card {
  flex: none;
  width: 170px;
  padding: 10px;
  cursor: pointer;
  position: relative;
}

.seckill-pic {
  width: 100%;
  aspect-ratio: 1;
  border-radius: 8px;
  background: #f5f7fa;
}

.seckill-name {
  font-size: 13px;
  font-weight: 600;
  margin-top: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.seckill-prices {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-top: 4px;
}

.seckill-now {
  color: var(--el-color-danger);
  font-size: 19px;
  font-weight: 700;
}

.seckill-old {
  font-size: 12px;
  color: #c0c4cc;
  text-decoration: line-through;
}

.seckill-stock {
  height: 6px;
  border-radius: 3px;
  background: #fde2e2;
  overflow: hidden;
  margin: 8px 0;
}

.seckill-stock .bar {
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, #ff7a59, var(--el-color-danger));
}

.seckill-state {
  display: block;
  text-align: center;
  background: linear-gradient(90deg, #ff7a59, var(--el-color-danger));
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  border-radius: 14px;
  padding: 4px 0;
}

.seckill-state.soon {
  background: linear-gradient(120deg, #b8c4ff, #8f9dff);
}

/* 领券中心 */
.coupon-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.coupon-card {
  display: flex;
  align-items: stretch;
  border-radius: var(--mall-radius);
  overflow: hidden;
  background: #fff;
  border: 1px solid #ffd7d7;
}

.coupon-left {
  flex: none;
  width: 88px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #fff1f0, #ffe3e0);
  color: var(--el-color-danger);
  padding: 12px 6px;
}

.coupon-val {
  font-size: 22px;
  font-weight: 700;
  line-height: 1;
}

.coupon-val i {
  font-style: normal;
  font-size: 12px;
}

.coupon-rule {
  font-size: 11px;
  margin-top: 4px;
}

.coupon-right {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  padding: 10px 12px;
}

.coupon-name {
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

@media (max-width: 1199px) {
  .coupon-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .seckill-card {
    width: 140px;
  }

  .coupon-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .coupon-left {
    width: 72px;
  }
}


.floor-head h3 {
  margin: 0;
  font-size: 18px;
}

.floor-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.like-grid {
  grid-template-columns: repeat(6, minmax(0, 1fr));
}

.home-footer {
  text-align: center;
  color: #c0c4cc;
  font-size: 12px;
  padding: 8px 0 24px;
}

/* 平板 */
@media (max-width: 1199px) {
  .cat-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .floor-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .like-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .banner {
    padding: 0 28px;
  }

  .banner-content h2 {
    font-size: 24px;
  }

  .banner-emoji {
    font-size: 64px;
  }
}

/* 手机 */
@media (max-width: 768px) {
  .container {
    padding: 0 10px;
    margin-bottom: 14px;
  }

  .cat-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    padding: 10px 6px;
  }

  .cat-icon {
    font-size: 22px;
  }

  .floor-grid,
  .like-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .floor-head h3 {
    font-size: 16px;
  }

  .banner {
    padding: 0 20px;
    border-radius: 8px;
  }

  .banner-content h2 {
    font-size: 18px;
    margin-bottom: 4px;
  }

  .banner-content p {
    margin-bottom: 8px;
    font-size: 12px;
  }

  .banner-emoji {
    font-size: 44px;
  }

  .ai-entry {
    padding: 12px 14px;
  }

  .ai-desc {
    display: none;
  }
}
</style>
