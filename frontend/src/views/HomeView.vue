<template>
  <div class="home" v-loading="loading">
    <!-- ============ 第一屏：分类竖菜单 + 轮播 + 用户卡 ============ -->
    <section class="container hero-zone">
      <aside class="side-cats desktop-only">
        <div v-for="c in catCells" :key="c.key" class="side-cat" @click="$router.push(c.link)">
          <span class="sc-icon">{{ c.icon }}</span>
          <span class="sc-name">{{ c.name }}</span>
          <span class="sc-arrow">›</span>
        </div>
      </aside>

      <div class="hero-banner">
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
      </div>

      <aside class="side-user tablet-only-none">
        <div class="user-panel mall-card">
          <template v-if="auth.user">
            <el-avatar :size="44" class="up-avatar">{{ auth.user.nickname.slice(0, 1) }}</el-avatar>
            <div class="up-hello">Hi，{{ auth.user.nickname }}</div>
            <div class="up-sub">欢迎回到 AI Mall</div>
          </template>
          <template v-else>
            <div class="up-hello">Hi，欢迎来到 AI Mall</div>
            <div class="up-sub">登录后享专属优惠</div>
            <el-button type="danger" round class="up-login" @click="$router.push('/login')">
              登录 / 注册
            </el-button>
          </template>
          <div class="up-links">
            <span @click="$router.push('/orders')">我的订单</span>
            <span @click="$router.push('/favorites')">我的收藏</span>
            <span @click="$router.push('/cart')">购物车</span>
            <span @click="scrollToCoupons">领券中心</span>
          </div>
        </div>
        <div class="notice-panel mall-card">
          <div class="notice-title">🛎️ 商城公告</div>
          <div class="notice-item">全场满 100 减 20 优惠券限时领取</div>
          <div class="notice-item">品牌秒杀专区每日上新</div>
          <div class="notice-item">AI 助手帮你找货 · 秒回价保咨询</div>
        </div>
      </aside>
    </section>

    <!-- ============ 分类金刚区（平板/手机；桌面在左侧竖菜单） ============ -->
    <section class="container cat-grid-zone mobile-tablet-only">
      <div class="cat-grid">
        <div v-for="c in catCells" :key="c.key" class="cat-cell" @click="$router.push(c.link)">
          <span class="cat-icon">{{ c.icon }}</span>
          <span class="cat-name">{{ c.name }}</span>
        </div>
      </div>
    </section>

    <!-- ============ 限时秒杀专区（模块化：倒计时面板 + 商品网格） ============ -->
    <section v-if="seckills.length" id="seckill-zone" class="container floor">
      <div class="seckill-zone">
        <div class="seckill-side">
          <div class="ss-flash">⚡</div>
          <div class="ss-title">限时秒杀</div>
          <div class="ss-sub">品牌好物 · 低价到底</div>
          <div class="ss-countdown" v-if="countdownText">{{ countdownText }}</div>
        </div>
        <div class="seckill-goods">
          <div v-for="s in seckills.slice(0, 5)" :key="s.seckillId" class="sg-card"
            @click="$router.push(`/products/${s.productId}`)">
            <el-image :src="s.imageUrl" fit="cover" class="sg-pic" lazy decoding="async" />
            <div class="sg-name">{{ s.name }}</div>
            <div class="sg-price-row">
              <span class="sg-now"><i>￥</i>{{ s.seckillPrice }}</span>
              <span class="sg-old">￥{{ s.originalPrice }}</span>
            </div>
            <div class="sg-progress">
              <div class="sg-bar" :style="{ width: stockPercent(s) }" />
            </div>
            <button class="sg-buy" :class="{ soon: !s.started }">
              {{ s.started ? '马上抢' : '即将开始' }}
            </button>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ 领券中心 ============ -->
    <section v-if="coupons.length" id="coupon-zone" class="container floor">
      <div class="floor-head">
        <h3><i class="bar-accent" />领券中心</h3>
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

    <!-- ============ AI 助手入口 ============ -->
    <section class="container floor">
      <div class="ai-entry" @click="$router.push('/assistant')">
        <span class="ai-emoji">🤖</span>
        <div class="ai-text">
          <div class="ai-title">AI 购物助手</div>
          <div class="ai-desc">告诉我想买什么，帮你找商品、查订单、答政策</div>
        </div>
        <el-button type="primary" round>去咨询</el-button>
      </div>
    </section>

    <!-- ============ 商品楼层 ============ -->
    <section v-for="f in floors" :key="f.code" class="container floor">
      <div class="floor-head">
        <h3><i class="bar-accent" />{{ f.name }}</h3>
        <el-button text type="primary" @click="$router.push(`/products?category=${f.code}`)">
          更多 ›
        </el-button>
      </div>
      <div class="floor-grid">
        <ProductCard v-for="p in f.products" :key="p.id" :product="p" />
      </div>
    </section>

    <!-- ============ 猜你喜欢 ============ -->
    <section class="container floor">
      <div class="floor-head">
        <h3><i class="bar-accent" />猜你喜欢</h3>
      </div>
      <div class="floor-grid like-grid">
        <ProductCard v-for="p in likes" :key="p.id" :product="p" />
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiCatalogCategories, apiProducts, apiReceivableCoupons, apiReceiveCoupon, apiSeckills } from '@/api'
import { CATEGORIES, categoryIcon, categoryName } from '@/constants/categories'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import ProductCard from '@/components/product/ProductCard.vue'
import type { CategoryVO, CouponVO, ProductVO, SeckillVO } from '@/types/api'

const auth = useAuthStore()
const router = useRouter()
const loading = ref(false)
const windowWidth = ref(window.innerWidth)
const onResize = () => (windowWidth.value = window.innerWidth)
window.addEventListener('resize', onResize)

const bannerHeight = computed(() =>
  windowWidth.value <= 768 ? '150px' : windowWidth.value <= 1199 ? '200px' : '320px',
)

const banners = [
  { title: '数码焕新季', desc: '旗舰影像 · 折上折', emoji: '📱', bg: 'linear-gradient(120deg, #4f7cff, #8f6bff)', link: '/products?category=PHONE' },
  { title: '家电狂欢周', desc: '一级能效 · 以旧换新', emoji: '🧺', bg: 'linear-gradient(120deg, #12b7a3, #48c9b0)', link: '/products?category=APPLIANCE' },
  { title: '生鲜直达', desc: '产地直发 · 新鲜到家', emoji: '🍎', bg: 'linear-gradient(120deg, #ff7a59, #ffb347)', link: '/products?category=FOOD' },
]

// 楼层：4 个主力分类，每层 8 件
const floorCodes = ['PHONE', 'APPLIANCE', 'CLOTHING', 'SPORTS']
const floors = ref<{ code: string; name: string; icon: string; products: ProductVO[] }[]>([])
const likes = ref<ProductVO[]>([])

// 分类（宫格 + 左侧竖菜单共用）：商城目录优先，为空时回落到内置常量
interface CatCell { key: string; name: string; icon: string; link: string }
const catCells = ref<CatCell[]>(
  CATEGORIES.map((c) => ({ key: c.code, name: c.name, icon: c.icon, link: `/products?category=${c.code}` })),
)

// ---------- 秒杀专区 ----------
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
  return `${pad(h)}:${pad(m)}:${pad(s)}`
})

function stockPercent(s: SeckillVO): string {
  const original = Math.max(1, s.seckillStock + 1)
  return `${Math.min(100, Math.round((s.seckillStock / original) * 100))}%`
}

// ---------- 领券中心 ----------
const coupons = ref<CouponVO[]>([])

function scrollToCoupons() {
  document.getElementById('coupon-zone')?.scrollIntoView({ behavior: 'smooth' })
}

async function receive(c: CouponVO) {
  if (!auth.isCustomer) {
    ElMessage.warning('请先登录后领券')
    void router.push({ path: '/login', query: { redirect: '/' } })
    return
  }
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
          name: categoryName(c.name),
          icon: c.icon || categoryIcon(c.name),
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

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  if (timer) window.clearInterval(timer)
})

</script>

<style scoped>
.home {
  min-height: 100%;
  padding-top: 12px;
}

.home .container {
  margin-bottom: 20px;
}

/* ================= 第一屏三栏 ================= */
.hero-zone {
  display: flex;
  gap: 12px;
  align-items: stretch;
}

/* 左侧分类竖菜单 */
.side-cats {
  width: 190px;
  flex-shrink: 0;
  background: var(--mall-surface, #fff);
  border-radius: var(--mall-radius);
  overflow: hidden;
  box-shadow: var(--mall-shadow-card);
  padding: 6px 0;
}

.side-cat {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 40px;
  padding: 0 14px;
  font-size: 13px;
  color: var(--el-text-color-primary, #303133);
  cursor: pointer;
  transition: all 0.12s;
}

.side-cat:hover {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  padding-left: 18px;
}

.sc-icon {
  font-size: 15px;
}

.sc-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sc-arrow {
  color: var(--el-text-color-placeholder, #c0c4cc);
}

.hero-banner {
  flex: 1;
  min-width: 0;
  border-radius: var(--mall-radius);
  overflow: hidden;
}

.banner {
  height: 100%;
  border-radius: var(--mall-radius);
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
  font-size: 32px;
  font-weight: 700;
}

.banner-content p {
  margin: 0 0 14px;
  opacity: 0.9;
}

.banner-cta {
  font-size: 14px;
  border: 1px solid rgba(255, 255, 255, 0.7);
  padding: 6px 18px;
  border-radius: 18px;
}

.banner-emoji {
  font-size: 92px;
  filter: drop-shadow(0 8px 16px rgba(0, 0, 0, 0.2));
}

/* 右侧用户卡 */
.side-user {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.user-panel {
  padding: 18px 16px;
  text-align: center;
}

.up-avatar {
  background: var(--mall-gradient);
  color: #fff;
  font-weight: 700;
}

.up-hello {
  font-weight: 700;
  font-size: 15px;
  margin-top: 8px;
}

.up-sub {
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
  margin-top: 2px;
}

.up-login {
  margin-top: 10px;
  width: 100%;
}

.up-links {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed var(--el-border-color-lighter, #ebeef5);
}

.up-links span {
  font-size: 12px;
  color: var(--el-text-color-regular, #606266);
  cursor: pointer;
  padding: 4px 0;
}

.up-links span:hover {
  color: var(--el-color-primary);
}

.notice-panel {
  padding: 14px 16px;
}

.notice-title {
  font-weight: 700;
  font-size: 13px;
  margin-bottom: 8px;
}

.notice-item {
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
  line-height: 1.9;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ================= 分类金刚区（平板/手机） ================= */
.mobile-tablet-only {
  display: none;
}

@media (max-width: 1199px) {
  .mobile-tablet-only {
    display: block;
  }

  .side-cats {
    display: none;
  }

  .side-user {
    width: 200px;
  }
}

@media (max-width: 768px) {
  .side-user {
    display: none;
  }
}

/* 分类宫格 */
.cat-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 6px;
  background: var(--mall-surface, #fff);
  border-radius: var(--mall-radius);
  padding: 12px 8px;
  box-shadow: var(--mall-shadow-card);
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
  background: var(--el-color-primary-light-9);
}

.cat-icon {
  font-size: 26px;
}

.cat-name {
  font-size: 12px;
  color: var(--el-text-color-regular, #606266);
}

/* ================= 楼层标题条 ================= */
.floor-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.floor-head h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 20px;
  font-weight: 700;
}

.bar-accent {
  display: inline-block;
  width: 4px;
  height: 18px;
  border-radius: 2px;
  background: var(--mall-gradient);
}

/* ================= 秒杀专区 ================= */
.seckill-zone {
  display: flex;
  gap: 12px;
  background: var(--mall-surface, #fff);
  border-radius: var(--mall-radius);
  overflow: hidden;
  box-shadow: var(--mall-shadow-card);
}

.seckill-side {
  width: 200px;
  flex-shrink: 0;
  background: linear-gradient(160deg, #ee0a24, #ff6034);
  color: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px 16px;
}

.ss-flash {
  font-size: 40px;
  filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.25));
}

.ss-title {
  font-size: 24px;
  font-weight: 800;
  letter-spacing: 2px;
}

.ss-sub {
  font-size: 12px;
  opacity: 0.85;
}

.ss-countdown {
  margin-top: 8px;
  background: #2b2b33;
  border-radius: 6px;
  padding: 6px 14px;
  font-size: 18px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  letter-spacing: 1px;
}

.seckill-goods {
  flex: 1;
  min-width: 0;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 1px;
  background: #f0f1f4;
}

.sg-card {
  background: var(--mall-surface, #fff);
  padding: 14px 12px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  transition: box-shadow 0.15s;
}

.sg-card:hover {
  box-shadow: var(--mall-shadow-hover);
  z-index: 1;
}

.sg-pic {
  width: 100%;
  aspect-ratio: 1;
  border-radius: 8px;
  background: var(--mall-surface-2, #f5f7fa);
}

.sg-name {
  font-size: 13px;
  margin-top: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sg-price-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-top: 6px;
}

.sg-now {
  color: var(--mall-price, #e4393c);
  font-size: 20px;
  font-weight: 700;
}

.sg-now i {
  font-style: normal;
  font-size: 12px;
}

.sg-old {
  font-size: 12px;
  color: var(--el-text-color-placeholder, #c0c4cc);
  text-decoration: line-through;
}

.sg-progress {
  height: 6px;
  border-radius: 3px;
  background: #fde2e2;
  overflow: hidden;
  margin: 8px 0;
}

.sg-bar {
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, #ff6034, var(--mall-price, #e4393c));
}

.sg-buy {
  border: 0;
  border-radius: 14px;
  padding: 6px 0;
  background: linear-gradient(90deg, #ff6034, var(--mall-price, #e4393c));
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.sg-buy:hover {
  filter: brightness(1.08);
}

.sg-buy.soon {
  background: linear-gradient(120deg, #b8c4ff, #8f9dff);
}

/* ================= 领券中心 ================= */
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
  background: var(--mall-surface, #fff);
  border: 1px solid #ffd7d7;
}

.coupon-left {
  flex: none;
  width: 92px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #fff1f0, #ffe3e0);
  color: var(--mall-price, #e4393c);
  padding: 14px 6px;
}

.coupon-val {
  font-size: 24px;
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

/* ================= AI 入口 ================= */
.ai-entry {
  display: flex;
  align-items: center;
  gap: 14px;
  background: linear-gradient(120deg, #eef3ff, #f6efff);
  border: 1px solid #dde6ff;
  border-radius: var(--mall-radius);
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
  color: var(--el-text-color-secondary, #909399);
  margin-top: 2px;
}

/* ================= 楼层栅格 ================= */
.floor-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.like-grid {
  grid-template-columns: repeat(6, minmax(0, 1fr));
}

/* ================= 平板 ================= */
@media (max-width: 1199px) and (min-width: 769px) {
  .hero-zone {
    flex-wrap: wrap;
  }

  .hero-banner {
    flex: 1;
  }

  .side-user {
    display: none;
  }

  .seckill-goods {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .sg-card:nth-child(n + 4) {
    display: none;
  }

  .coupon-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .floor-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .like-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

/* ================= 手机 ================= */
@media (max-width: 768px) {
  .home {
    padding-top: 8px;
  }

  .hero-zone {
    gap: 0;
  }

  .banner {
    padding: 0 24px;
  }

  .banner-content h2 {
    font-size: 20px;
  }

  .banner-emoji {
    font-size: 52px;
  }

  .cat-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .seckill-zone {
    flex-direction: column;
  }

  .seckill-side {
    width: 100%;
    flex-direction: row;
    padding: 12px 16px;
    gap: 12px;
  }

  .ss-flash {
    font-size: 26px;
  }

  .ss-title {
    font-size: 17px;
  }

  .ss-sub {
    display: none;
  }

  .ss-countdown {
    margin: 0 0 0 auto;
    font-size: 14px;
    padding: 4px 10px;
  }

  .seckill-goods {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1px;
  }

  .sg-card:nth-child(n + 3) {
    display: none;
  }

  .coupon-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .floor-grid,
  .like-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .floor-head h3 {
    font-size: 16px;
  }
}
</style>
