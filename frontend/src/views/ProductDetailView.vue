<template>
  <el-scrollbar class="page-scroll" :distance="30" @end-reached="direction => direction === 'bottom' && loadReviews()">
    <div v-if="product" class="page detail">
    <div class="main">
      <el-image :src="product.imageUrl" fit="cover" class="pic" fetchpriority="high" decoding="async" :preview-src-list="[product.imageUrl]">
        <template #placeholder>
          <div class="pic-fallback">{{ product.name.slice(0, 1) }}</div>
        </template>
        <template #error>
          <div class="pic-fallback">{{ product.name.slice(0, 1) }}</div>
        </template>
      </el-image>
      <div class="info">
        <h2 class="name">{{ product.name }}</h2>
        <div class="sub-row">
          <el-tag size="small" effect="plain">{{ categoryName(product.category) }}</el-tag>
          <span class="brand">{{ product.brand }}</span>
          <span class="sales">已售 {{ product.sales || 0 }} 件</span>
        </div>
        <div class="price" :class="{ 'seckill-price': seckill }">
          <span v-if="seckill" class="seckill-tag">⚡ 秒杀价</span>
          <template v-if="selectedSku">￥{{ selectedSku.price }}<span class="price-range" v-if="skus.length > 1 && !seckill"> 起 ￥{{ minSkuPrice }}</span></template>
          <template v-else>￥{{ displayPrice }}</template>
          <span v-if="seckill" class="price-origin">￥{{ selectedSku?.price || product.price }}</span>
        </div>
        <!-- SKU 规格选择（对标 mall：按销售属性分组，选中组合定位 SKU） -->
        <div v-if="skuGroups.length" class="sku-block">
          <div v-for="g in skuGroups" :key="g.key" class="sku-group">
            <span class="sku-label">{{ g.key }}</span>
            <div class="sku-vals">
              <button v-for="v in g.values" :key="v" type="button" class="sku-val"
                :class="{ active: selectedSpecs[g.key] === v }" @click="pickSpec(g.key, v)">
                {{ v }}
              </button>
            </div>
          </div>
          <div v-if="!selectedSku" class="sku-hint">请选择完整规格</div>
          <div v-else-if="selectedSku.stock === 0" class="sku-hint warn">该规格暂时缺货</div>
        </div>
        <div class="points">
          <el-tag v-for="(p, i) in points" :key="i" type="info" effect="plain" class="point-tag">
            {{ p }}
          </el-tag>
        </div>
        <!-- 服务信息 -->
        <div class="service-row">
          <span class="svc">📦 发货地：{{ product.shipFrom || '—' }}</span>
          <span class="svc">🏭 产地：{{ product.origin || '—' }}</span>
          <span class="svc">🛡️ 7天无理由退货</span>
        </div>
        <div class="qty-row">
          <span class="qty-label">数量</span>
          <el-input-number v-model="quantity" :min="1" :max="stockLimit" />
          <span class="stock">库存 {{ stockLimit }} {{ stockLimit === 0 ? '（暂时缺货）' : '' }}</span>
        </div>
        <div class="btn-row">
          <el-button size="large" class="act-btn" :disabled="stockLimit === 0 || buyBlocked" @click="addToCart">
            加入购物车
          </el-button>
          <el-button type="danger" size="large" class="act-btn" :disabled="stockLimit === 0 || buyBlocked"
            @click="buyNow">
            立即购买
          </el-button>
          <el-button size="large" :type="favorited ? 'warning' : 'default'" circle @click="toggleFavorite">
            <el-icon><Star /></el-icon>
          </el-button>
        </div>
      </div>
    </div>

    <!-- 规格参数 -->
    <el-card shadow="never" class="card">
      <template #header>商品信息</template>
      <el-descriptions :column="isMobile ? 1 : 2" border>
        <el-descriptions-item label="品牌">{{ product.brand }}</el-descriptions-item>
        <el-descriptions-item label="类目">{{ categoryName(product.category) }}</el-descriptions-item>
        <el-descriptions-item v-if="product.material" label="材质">{{ product.material }}</el-descriptions-item>
        <el-descriptions-item v-if="product.origin" label="产地">{{ product.origin }}</el-descriptions-item>
        <el-descriptions-item v-if="product.shipFrom" label="发货地">{{ product.shipFrom }}</el-descriptions-item>
        <el-descriptions-item v-if="product.productionDate" label="生产日期">
          {{ product.productionDate }}
        </el-descriptions-item>
        <el-descriptions-item v-for="s in specs" :key="s.k" :label="s.k">{{ s.v }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 商品介绍 -->
    <el-card shadow="never" class="card">
      <template #header>商品介绍</template>
      <div class="md-content" v-html="descHtml"></div>
    </el-card>

    <!-- 商品评论 -->
    <el-card shadow="never" class="card">
      <template #header>
        <div class="review-head">
          <span>商品评论（{{ reviewTotal }}）</span>
          <span class="avg">平均 {{ avgRating }} 分</span>
        </div>
      </template>
      <div>
        <div v-for="r in reviews" :key="r.reviewId" class="review-item">
          <div class="r-head">
            <el-avatar :size="28">{{ r.nickname.slice(0, 1) }}</el-avatar>
            <span class="r-nick">{{ r.nickname }}</span>
            <el-rate :model-value="r.rating" disabled size="small" />
            <span class="r-time">{{ shortTime(r.createdAt) }}</span>
          </div>
          <div class="r-content">{{ r.content }}</div>
          <div v-if="r.specInfo" class="r-spec">购买规格：{{ r.specInfo }}</div>
          <div v-if="r.merchantReply" class="r-reply">
            <b>商家回复：</b>{{ r.merchantReply }}
          </div>
        </div>
        <el-empty v-if="!reviewLoading && reviews.length === 0" description="暂无评论，快来抢沙发" :image-size="60" />
        <div v-if="reviewLoading" class="load-state">加载中...</div>
        <div v-else-if="reviewFinished && reviews.length > 0" class="load-state">— 没有更多了 —</div>
      </div>
      <!-- 发表评论 -->
      <div class="review-form">
        <el-rate v-model="myRating" />
        <el-input v-model="myContent" type="textarea" :rows="2" placeholder="写下你的使用感受..." />
        <el-button type="primary" :disabled="!myContent.trim()" @click="submitReview">发表评论</el-button>
      </div>
    </el-card>

    <!-- 移动端底部固定操作栏 -->
    <div class="mobile-action-bar">
      <div class="mobile-icon-btn" @click="$router.push('/')">
        <el-icon :size="18"><HomeFilled /></el-icon>
        <span>首页</span>
      </div>
      <div class="mobile-icon-btn" @click="toggleFavorite">
        <el-icon :size="18" :class="{ 'is-favorited': favorited }">
          <StarFilled v-if="favorited" />
          <Star v-else />
        </el-icon>
        <span>{{ favorited ? '已收藏' : '收藏' }}</span>
      </div>
      <div class="mobile-icon-btn" @click="$router.push('/cart')">
        <el-icon :size="18"><ShoppingCart /></el-icon>
        <span>购物车</span>
      </div>
      <div class="mobile-act-btns">
        <el-button class="m-cart-btn" :disabled="stockLimit === 0 || buyBlocked" @click="addToCart">
          加入购物车
        </el-button>
        <el-button type="danger" class="m-buy-btn" :disabled="stockLimit === 0 || buyBlocked" @click="buyNow">
          立即购买
        </el-button>
      </div>
    </div>

    <!-- 规格与数量选择弹窗 -->
    <el-dialog v-model="showSpec" title="选择规格与数量" width="min(440px, 94vw)">
      <div class="spec-head">
        <el-image :src="product.imageUrl" fit="cover" class="spec-pic" lazy decoding="async">
          <template #placeholder>
            <div class="pic-fallback">{{ product.name.slice(0, 1) }}</div>
          </template>
          <template #error>
            <div class="pic-fallback">{{ product.name.slice(0, 1) }}</div>
          </template>
        </el-image>
        <div class="spec-info">
          <div class="spec-name">{{ product.name }}</div>
          <div class="spec-price">￥{{ unitPrice }}</div>
          <div class="spec-stock">库存 {{ stockLimit }}</div>
        </div>
      </div>
      <div v-if="specAttrs.length" class="spec-block">
        <div class="spec-label">规格参数</div>
        <div class="attr-grid">
          <div v-for="s in specAttrs" :key="s.k" class="attr-item">
            <span class="attr-key">{{ s.k }}</span>
            <span class="attr-val">{{ s.v }}</span>
          </div>
        </div>
      </div>
      <div class="spec-qty">
        <span class="qty-t">数量</span>
        <el-input-number v-model="specQty" :min="1" :max="stockLimit" />
      </div>
      <template #footer>
        <el-button @click="showSpec = false">取消</el-button>
        <el-button type="danger" :disabled="stockLimit === 0 || buyBlocked" @click="confirmSpec">确定</el-button>
      </template>
    </el-dialog>

    <!-- 收货信息 + 下单弹窗 -->
    <el-dialog v-model="showBuy" title="确认订单" width="min(440px, 94vw)">
      <el-form label-width="80px">
        <el-form-item label="商品">
          <span>{{ product.name }} × {{ quantity }}</span>
        </el-form-item>
        <el-form-item label="优惠券">
          <CouponPicker v-model="selectedCouponId" :amount="subtotalAmount"
            @discount="(v) => (couponDiscountValue = v)" />
        </el-form-item>
        <el-form-item label="合计">
          <span class="total">￥{{ payableAmount }}</span>
          <span v-if="couponDiscountValue > 0" class="discount-note">已优惠 ￥{{ couponDiscountValue }}</span>
        </el-form-item>
        <el-form-item label="收货地址" class="addr-form-item">
          <CheckoutAddressPicker v-model="selectedAddressId" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBuy = false">取消</el-button>
        <el-button type="danger" :loading="submitting" :disabled="!selectedAddressId" @click="submitOrder">模拟支付</el-button>
      </template>
    </el-dialog>
    </div>
  </el-scrollbar>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { HomeFilled, ShoppingCart, Star, StarFilled } from '@element-plus/icons-vue'
import CheckoutAddressPicker from '@/components/address/CheckoutAddressPicker.vue'
import CouponPicker from '@/components/mall/CouponPicker.vue'
import {
  apiCartAdd, apiCatalogProductSkus, apiCreateOrder, apiFavoriteStatus, apiFavoriteToggle, apiHistoryRecord,
  apiPayOrder, apiProductDetail, apiReviewCreate, apiReviews, apiSeckills, type ReviewVO,
} from '@/api'
import { renderMarkdown } from '@/components/mall/link'
import { categoryName } from '@/constants/categories'
import type { ProductVO, SkuVO } from '@/types/api'

const route = useRoute()
const router = useRouter()

const product = ref<ProductVO | null>(null)
const quantity = ref(1)
const favorited = ref(false)
const showSpec = ref(false)
const showBuy = ref(false)
const specQty = ref(1)
const submitting = ref(false)
const selectedAddressId = ref<number>()

// 评论
const reviews = ref<ReviewVO[]>([])
const reviewLoading = ref(false)
const reviewFinished = ref(false)
const reviewPage = ref(1)
const reviewTotal = ref(0)
const avgRating = ref(5)
const myRating = ref(5)
const myContent = ref('')

const isMobile = ref(typeof window !== 'undefined' ? window.innerWidth <= 768 : false)
function updateMobile() {
  isMobile.value = window.innerWidth <= 768
}

const points = computed(() => (product.value?.sellingPoints || '').split(/\s+/).filter(Boolean))
const specs = computed(() => {
  try {
    const obj = JSON.parse(product.value?.specs || '{}')
    return Object.entries(obj).map(([k, v]) => ({ k, v: String(v) }))
  } catch {
    return []
  }
})
/** 规格弹窗内展示的商品参数 */
const specAttrs = computed(() => {
  const attrs = [...specs.value]
  if (product.value?.material) attrs.push({ k: '材质', v: product.value.material })
  if (product.value?.origin) attrs.push({ k: '产地', v: product.value.origin })
  return attrs
})
const totalAmount = computed(() => (unitPrice.value * quantity.value).toFixed(2))
const descHtml = computed(() => renderMarkdown(product.value?.description || '暂无介绍'))

// ---------- SKU 规格选择（对标 mall） ----------
const skus = ref<SkuVO[]>([])
const selectedSpecs = ref<Record<string, string>>({})

interface SpEntry { key: string; value: string }

function parseSp(spData?: string): SpEntry[] {
  try {
    const arr = JSON.parse(spData || '[]') as SpEntry[]
    return Array.isArray(arr) ? arr.filter((e) => e && e.key && e.value != null) : []
  } catch {
    return []
  }
}

/** 销售属性分组：[{key:'颜色', values:['黑色','白色']}, ...] */
const skuGroups = computed(() => {
  const map = new Map<string, string[]>()
  for (const s of skus.value) {
    for (const e of parseSp(s.spData)) {
      const list = map.get(e.key) || []
      if (!list.includes(String(e.value))) list.push(String(e.value))
      map.set(e.key, list)
    }
  }
  return [...map.entries()].map(([key, values]) => ({ key, values }))
})

/** 当前选中组合对应的 SKU（全部属性命中才算选中） */
const selectedSku = computed<SkuVO | null>(() => {
  if (!skuGroups.value.length) return null
  return skus.value.find((s) => {
    const sp = parseSp(s.spData)
    return sp.length === skuGroups.value.length
      && sp.every((e) => selectedSpecs.value[e.key] === String(e.value))
  }) || null
})

const unitPrice = computed(() => {
  if (seckill.value) return seckill.value.seckillPrice
  return selectedSku.value?.price ?? product.value?.price ?? 0
})
const minSkuPrice = computed(() => {
  const prices = skus.value.map((s) => s.price).filter((p) => p != null)
  return prices.length ? Math.min(...prices) : product.value?.price || 0
})
/** 秒杀展示原价（无 SKU 商品为商品价） */
const displayPrice = computed(() => seckill.value ? minSkuPrice.value : product.value?.price || 0)
const stockLimit = computed(() => {
  const limit = selectedSku.value ? selectedSku.value.stock : product.value?.stock || 0
  const capped = Math.min(99, Math.max(0, limit))
  // 秒杀限购优先
  return seckill.value ? Math.min(capped, seckill.value.seckillLimit) : capped
})
/** 有规格但未选完整 或 选中规格缺货 → 阻断购买 */
const buyBlocked = computed(() => skuGroups.value.length > 0 && (!selectedSku.value || selectedSku.value.stock === 0))

function pickSpec(key: string, value: string) {
  selectedSpecs.value = { ...selectedSpecs.value, [key]: selectedSpecs.value[key] === value ? '' : value }
  quantity.value = 1
}

// ---------- 秒杀与优惠券 ----------
const seckill = ref<{ seckillId: number; seckillPrice: number; seckillLimit: number } | null>(null)
const selectedCouponId = ref<number>()
const couponDiscountValue = ref(0)

const subtotalAmount = computed(() => Number((unitPrice.value * quantity.value).toFixed(2)))
const payableAmount = computed(() =>
  Math.max(0, Number((subtotalAmount.value - couponDiscountValue.value).toFixed(2))),
)

onMounted(async () => {
  window.addEventListener('resize', updateMobile)
  const id = Number(route.params.id)
  try {
    product.value = await apiProductDetail(id)
  } catch {
    router.replace('/404')
    return
  }
  // 收藏状态 + 浏览历史上报 + SKU 列表 + 秒杀（失败不影响页面）
  apiFavoriteStatus(id).then((s) => (favorited.value = s.favorited)).catch(() => {})
  apiHistoryRecord(id).catch(() => {})
  apiCatalogProductSkus(id).then((list) => {
    skus.value = list || []
    // 默认选中第一个有库存的 SKU 组合
    const first = skus.value.find((s) => s.stock > 0) || skus.value[0]
    if (first) {
      for (const e of parseSp(first.spData)) {
        selectedSpecs.value[e.key] = String(e.value)
      }
    }
  }).catch(() => {})
  apiSeckills().then((list) => {
    const mine = (list || []).find((s) => s.productId === id && s.started)
    if (mine) {
      seckill.value = {
        seckillId: mine.seckillId,
        seckillPrice: mine.seckillPrice,
        seckillLimit: mine.seckillLimit,
      }
    }
  }).catch(() => {})
  loadReviews()
})

onUnmounted(() => {
  window.removeEventListener('resize', updateMobile)
})

async function loadReviews() {
  if (reviewLoading.value || reviewFinished.value || !product.value) return
  reviewLoading.value = true
  try {
    const result = await apiReviews(product.value.id, { page: reviewPage.value, size: 10 })
    reviews.value.push(...result.records)
    reviewTotal.value = result.total
    avgRating.value = result.avgRating
    if (result.records.length === 0 || reviews.value.length >= result.total) {
      reviewFinished.value = true
    } else {
      reviewPage.value++
    }
  } finally {
    reviewLoading.value = false
  }
}

async function addToCart() {
  await apiCartAdd(product.value!.id, quantity.value, selectedSku.value?.id)
  ElMessage.success('已加入购物车')
}

async function toggleFavorite() {
  const res = await apiFavoriteToggle(product.value!.id)
  favorited.value = res.favorited
  ElMessage.success(res.favorited ? '已收藏' : '已取消收藏')
}

async function buyNow() {
  // 先弹出规格与数量选择，确认后再进入收货地址与支付
  specQty.value = quantity.value
  showSpec.value = true
}

function confirmSpec() {
  quantity.value = specQty.value
  showSpec.value = false
  selectedAddressId.value = undefined
  showBuy.value = true
}

async function submitOrder() {
  if (!selectedAddressId.value) {
    ElMessage.warning('请先选择或新增收货地址')
    return
  }
  submitting.value = true
  try {
    const order = await apiCreateOrder({
      productId: product.value!.id,
      skuId: selectedSku.value?.id,
      couponUserId: selectedCouponId.value,
      quantity: quantity.value,
      addressId: selectedAddressId.value,
    })
    // 下单后直接完成支付，无需用户再次确认
    await apiPayOrder(order.orderId)
    ElMessage.success(`下单并模拟支付成功：${order.orderNo}`)
    showBuy.value = false
    router.push(`/orders/${order.orderId}`)
  } catch {
    // 拦截器已提示
  } finally {
    submitting.value = false
  }
}

async function submitReview() {
  if (!myContent.value.trim()) return
  await apiReviewCreate(product.value!.id, {
    rating: myRating.value,
    content: myContent.value.trim(),
    specInfo: `×${quantity.value}`,
  })
  ElMessage.success('评论成功')
  myContent.value = ''
  // 重载评论
  reviews.value = []
  reviewPage.value = 1
  reviewFinished.value = false
  loadReviews()
}

function shortTime(t?: string): string {
  return (t || '').replace('T', ' ').slice(5, 16)
}
</script>

<style scoped>
.page-scroll { height: 100%; }
.detail {
  min-height: 100%;
  box-sizing: border-box;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  padding: 16px;
}

.main {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  background: var(--mall-surface, #fff);
  padding: 20px;
  border-radius: 8px;
}

.pic {
  width: 400px;
  height: 400px;
  border-radius: 8px;
  flex-shrink: 0;
}

.pic-fallback {
  width: 400px;
  height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 90px;
  font-weight: 700;
  color: var(--el-text-color-placeholder, #c0c4cc);
  background: linear-gradient(135deg, #e8f0fe, #f5f7fa);
}

.info {
  flex: 1 1 300px;
  min-width: 0;
}

.name {
  margin: 0 0 8px;
}

.sub-row {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--el-text-color-secondary, #909399);
  font-size: 13px;
}

.price {
  color: var(--el-color-danger);
  font-size: 30px;
  font-weight: 700;
  margin: 14px 0;
}

.price-range {
  font-size: 13px;
  font-weight: 400;
  color: var(--el-text-color-secondary);
  margin-left: 8px;
}

/* 秒杀价 */
.seckill-price {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.seckill-tag {
  background: var(--el-color-danger);
  color: #fff;
  font-size: 12px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 4px;
}

.price-origin {
  font-size: 14px;
  font-weight: 400;
  color: var(--el-text-color-secondary);
  text-decoration: line-through;
}

.discount-note {
  margin-left: 10px;
  font-size: 12px;
  color: var(--el-color-danger);
}

/* SKU 规格选择 */
.sku-block {
  margin: 4px 0 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sku-group {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.sku-label {
  flex: none;
  width: 56px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 32px;
}

.sku-vals {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.sku-val {
  min-width: 44px;
  padding: 5px 14px;
  border-radius: 16px;
  border: 1px solid var(--el-border-color);
  background: var(--el-fill-color-blank);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}

.sku-val:hover {
  border-color: var(--el-color-primary);
  color: var(--el-color-primary);
}

.sku-val.active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-weight: 600;
}

.sku-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.sku-hint.warn {
  color: var(--el-color-danger);
}

.point-tag {
  line-height: 1.5;
  padding: 4px 8px;
  margin: 0 8px 6px 0;
}

.service-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  padding: 10px 0;
  border-top: 1px dashed var(--el-border-color-lighter, #ebeef5);
  border-bottom: 1px dashed var(--el-border-color-lighter, #ebeef5);
  color: var(--el-text-color-regular, #606266);
  font-size: 13px;
}

.qty-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin: 16px 0;
}

.qty-label {
  color: var(--el-text-color-secondary, #909399);
  font-size: 14px;
}

.stock {
  font-size: 13px;
  color: var(--el-text-color-secondary, #909399);
}

.btn-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.act-btn {
  width: 180px;
}

.card {
  margin-top: 16px;
}

.review-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.avg {
  color: #ff9900;
  font-weight: 700;
}

.review-item {
  padding: 12px 0;
  border-bottom: 1px solid #f5f7fa;
}

.r-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.r-nick {
  font-weight: 600;
  font-size: 14px;
}

.r-time {
  margin-left: auto;
  font-size: 12px;
  color: var(--el-text-color-placeholder, #c0c4cc);
}

.r-content {
  margin: 8px 0 0 36px;
  line-height: 1.6;
}

.r-spec {
  margin: 4px 0 0 36px;
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
}

.r-reply {
  margin: 8px 0 0 36px;
  padding: 8px 12px;
  background: var(--mall-surface-2, #f5f7fa);
  border-radius: 6px;
  font-size: 13px;
}

.review-form {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color-lighter, #ebeef5);
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: flex-end;
}

.review-form .el-input {
  width: 100%;
}

.review-form .el-rate {
  align-self: flex-start;
}

.load-state {
  text-align: center;
  color: var(--el-text-color-secondary, #909399);
  font-size: 13px;
  padding: 12px 0;
}

.total {
  color: var(--el-color-danger);
  font-size: 18px;
  font-weight: 700;
}

.spec-head {
  display: flex;
  gap: 12px;
  align-items: center;
}

.spec-pic {
  width: 88px;
  height: 88px;
  border-radius: 8px;
  flex-shrink: 0;
}

.spec-pic .el-image__error {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  font-weight: 700;
  color: var(--el-text-color-placeholder, #c0c4cc);
  background: linear-gradient(135deg, #e8f0fe, #f5f7fa);
}

.spec-info {
  flex: 1;
  min-width: 0;
}

.spec-name {
  font-weight: 600;
  font-size: 15px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.spec-price {
  color: var(--el-color-danger);
  font-size: 20px;
  font-weight: 700;
  margin-top: 4px;
}

.spec-stock {
  color: var(--el-text-color-secondary, #909399);
  font-size: 12px;
  margin-top: 2px;
}

.spec-block {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px dashed var(--el-border-color-lighter, #ebeef5);
}

.spec-label {
  font-weight: 600;
  margin-bottom: 8px;
}

.attr-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.attr-item {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 10px;
  background: var(--mall-surface-2, #f5f7fa);
  border-radius: 6px;
  font-size: 13px;
}

.attr-key {
  color: var(--el-text-color-secondary, #909399);
  flex-shrink: 0;
}

.attr-val {
  color: var(--el-text-color-primary, #303133);
  text-align: right;
}

.spec-qty {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
}

.qty-t {
  color: var(--el-text-color-primary, #303133);
  font-weight: 600;
}

.addr-form-item :deep(.el-form-item__content) {
  width: 100%;
}

.mobile-action-bar {
  display: none;
}

@media (max-width: 768px) {
  .detail {
    padding: 10px;
    padding-bottom: calc(64px + env(safe-area-inset-bottom));
  }

  .main {
    flex-direction: column;
    padding: 12px;
    gap: 14px;
  }

  .pic,
  .pic-fallback {
    width: 100%;
    height: auto;
    aspect-ratio: 1;
  }

  .btn-row {
    flex-wrap: wrap;
  }

  .act-btn {
    flex: 1;
    min-width: 140px;
  }

  .mobile-action-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    display: flex;
    align-items: center;
    gap: 6px;
    background: var(--mall-surface, #fff);
    border-top: 1px solid var(--el-border-color-lighter, #ebeef5);
    padding: 8px 12px calc(8px + env(safe-area-inset-bottom));
    z-index: 100;
    box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.05);
  }

  .mobile-icon-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    font-size: 11px;
    color: var(--el-text-color-regular, #606266);
    cursor: pointer;
    min-width: 38px;
    padding: 2px 4px;
    user-select: none;
  }

  .mobile-icon-btn .is-favorited {
    color: #e6a23c;
  }

  .mobile-act-btns {
    flex: 1;
    display: flex;
    gap: 8px;
    align-items: center;
    margin-left: 4px;
  }

  .m-cart-btn,
  .m-buy-btn {
    flex: 1;
    height: 40px;
    margin: 0 !important;
    font-weight: 600;
    border-radius: 20px;
    font-size: 13px;
  }

  .m-cart-btn {
    background: #fff0f0;
    color: var(--el-color-danger);
    border-color: #ffc2c2;
  }
}

.point-tag {
  line-height: 1.5;
  padding: 4px 8px;
  max-width: 100%;
  height: auto;
  white-space: normal;
}
</style>
