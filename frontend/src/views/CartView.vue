<template>
  <el-scrollbar class="cart-scroll-container">
    <div class="page cart-page">
      <header class="cart-header-bar">
        <button class="cart-back-btn" aria-label="返回" @click="goBack">
          <el-icon :size="22"><ArrowLeft /></el-icon>
        </button>
        <h1 class="cart-main-title">购物车<span v-if="items.length" class="cart-count">（{{ items.length }}）</span></h1>
        <button v-if="items.length" class="manage-toggle-btn" @click="isManageMode = !isManageMode">
          {{ isManageMode ? '完成' : '管理' }}
        </button>
        <span v-else aria-hidden="true" />
      </header>

      <LoadingState v-if="loading && !items.length" variant="list" :count="3" label="正在加载购物车" />

      <template v-if="items.length">
        <div class="cart-section-bar">
          <h2 class="cart-section-title">全部商品（{{ items.length }}）</h2>
          <span class="cart-selection-hint">{{ isManageMode ? '选择要删除的商品' : '好物一起买' }}</span>
        </div>
        <div class="shipping-benefit-bar">
          <span class="sbb-text">已选 <strong>{{ checkedCount }}</strong> 件商品</span>
          <button class="sbb-more" @click="$router.push('/coupons')">领券中心 <el-icon><ArrowRight /></el-icon></button>
        </div>

        <section class="shop-group-card" aria-label="购物车商品">
          <div class="shop-group-head">
            <el-checkbox :model-value="allChecked" :indeterminate="checkedCount > 0 && !allChecked" class="shop-checkbox" aria-label="选择店铺全部商品" @change="checkAll"><span class="sr-only">选择店铺全部商品</span></el-checkbox>
            <div class="shop-title-box">
              <el-icon class="shop-icon"><Shop /></el-icon>
              <span class="shop-name">官方自营旗舰店</span>
              <span class="shop-tag">自营</span>
            </div>
          </div>

          <div class="cart-items-list">
            <article v-for="row in items" :key="row.cartItemId" class="cart-goods-row" :class="{ selected: row.checked === 1 }">
              <el-checkbox :model-value="row.checked === 1" class="goods-checkbox" :aria-label="'选择' + row.name" @change="toggleCheck(row)"><span class="sr-only">选择{{ row.name }}</span></el-checkbox>
              <button class="goods-img-box" :aria-label="'查看' + row.name" @click="goDetail(row.productId)">
                <el-image :src="row.imageUrl" :alt="row.name" fit="cover" class="goods-img" lazy decoding="async">
                  <template #error><div class="img-fallback"><el-icon :size="28"><Picture /></el-icon></div></template>
                </el-image>
              </button>
              <div class="goods-content">
                <button class="goods-name" @click="goDetail(row.productId)">{{ row.name }}</button>
                <button class="goods-sku-pill" title="查看商品规格" @click="goDetail(row.productId)">
                  <span>{{ spText(row.skuSp) }}</span><el-icon :size="11"><ArrowRight /></el-icon>
                </button>
                <div class="goods-price-row">
                  <div class="price-box"><span class="symbol">¥</span><span class="num">{{ Number(row.price).toFixed(2) }}</span></div>
                  <div class="stepper-box">
                    <el-input-number :model-value="row.quantity" :min="1" :max="row.stock || 99" size="small" class="custom-stepper" :aria-label="row.name + '数量'" @change="(v: number) => changeQty(row, v)" />
                    <button v-if="isManageMode" class="row-delete-btn" :aria-label="'删除' + row.name" @click.stop="remove(row)"><el-icon :size="16"><Delete /></el-icon></button>
                  </div>
                </div>
              </div>
            </article>
          </div>
        </section>
      </template>

      <section v-if="!loading && !items.length" class="empty-cart-card">
        <div class="ecc-icon"><el-icon :size="48"><ShoppingCart /></el-icon></div>
        <h2 class="ecc-title">购物车空空如也</h2>
        <p class="ecc-sub">去逛逛，把喜欢的好物带回来</p>
        <button class="ecc-btn" @click="$router.push('/')">去逛逛</button>
      </section>

      <section class="cart-recommend-section" aria-labelledby="cart-recommend-title">
        <div class="crs-header"><span class="crs-line" /><h2 id="cart-recommend-title" class="crs-title">猜你喜欢</h2><span class="crs-line" /></div>
        <p v-if="recommendError" class="recommend-error" role="alert">推荐商品加载失败 <button @click="loadRecommendations">重试</button></p>
        <LoadingState v-if="recommendLoading" variant="cards" :count="4" label="正在加载推荐商品" />
        <div class="recommend-grid">
          <a v-for="p in recommendProducts" :key="p.id" class="rec-card" :href="'/products/' + p.id" @click.prevent="goDetail(p.id)">
            <div class="rec-img-box">
              <el-image :src="p.imageUrl" :alt="p.name" fit="cover" class="rec-img" lazy decoding="async">
                <template #error><div class="img-fallback"><el-icon :size="28"><Picture /></el-icon></div></template>
              </el-image>
            </div>
            <div class="rec-info">
              <div class="rec-name">{{ p.name }}</div>
              <div v-if="p.sellingPoints" class="rec-points">{{ p.sellingPoints }}</div>
              <div class="rec-foot"><span class="rec-price"><small>¥</small>{{ Number(p.price).toFixed(2) }}</span><span v-if="p.sales != null" class="rec-sales">已售 {{ formatSales(p.sales) }}</span></div>
            </div>
          </a>
        </div>
      </section>

      <footer v-if="items.length" class="fixed-checkout-bar" aria-label="购物车结算">
        <div class="fcb-inner">
          <el-checkbox :model-value="allChecked" :indeterminate="checkedCount > 0 && !allChecked" class="fcb-checkbox" @change="checkAll">全选</el-checkbox>
          <div v-if="!isManageMode" class="fcb-summary">
            <div class="fcb-total-line"><span class="fcb-label">合计</span><span class="fcb-symbol">¥</span><span class="fcb-price">{{ totalAmount.toFixed(2) }}</span></div>
            <span class="fcb-sub">优惠及运费以结算页为准</span>
          </div>
          <div class="fcb-action-btns">
            <button v-if="!isManageMode" class="checkout-submit-btn" :disabled="checkedCount === 0" @click="openCheckout">去结算<span>（{{ checkedCount }}）</span></button>
            <button v-else class="batch-delete-btn" :disabled="checkedCount === 0" @click="batchRemoveChecked">删除<span>（{{ checkedCount }}）</span></button>
          </div>
        </div>
      </footer>
    </div>
  </el-scrollbar>
</template>

<script setup lang="ts">
import LoadingState from '@/components/common/LoadingState.vue'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, ArrowRight, Delete, Picture, Shop, ShoppingCart } from '@element-plus/icons-vue'
import {
  apiCartCheckAll, apiCartList, apiCartRemove, apiCartUpdate, apiProducts, type CartRow,
} from '@/api'
import type { ProductVO } from '@/types/api'

const router = useRouter()
const route = useRoute()

const items = ref<CartRow[]>([])
const loading = ref(false)
const totalAmount = ref(0)
const checkedCount = ref(0)
const isManageMode = ref(false)
const allChecked = computed(
  () => items.value.length > 0 && items.value.every((i) => i.checked === 1),
)

// 猜你喜欢推荐池
const recommendProducts = ref<ProductVO[]>([])
const recommendError = ref(false)
const recommendLoading = ref(false)
let disposed = false
async function loadRecommendations() {
  recommendLoading.value = true
  recommendError.value = false
  try {
    const result = await apiProducts({ page: 1, size: 8 })
    if (!disposed) recommendProducts.value = result.records
  } catch {
    if (!disposed) { recommendProducts.value = []; recommendError.value = true }
  } finally {
    if (!disposed) recommendLoading.value = false
  }
}
onUnmounted(() => { disposed = true })

function formatSales(sales?: number): string {
  const s = Number(sales) || 0
  if (s < 100) return String(s)
  if (s < 1000) return `${Math.floor(s / 100) * 100}+`
  return `${Math.floor(s / 1000)}000+`
}

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/')
}

async function load() {
  loading.value = true
  try {
    const data = await apiCartList()
    items.value = data.items || []
    totalAmount.value = data.totalAmount || 0
    checkedCount.value = data.checkedCount || 0
  } finally {
    loading.value = false
  }
}

async function toggleCheck(row: CartRow) {
  const newChecked = row.checked === 1 ? 0 : 1
  await apiCartUpdate(row.cartItemId, { checked: newChecked === 1 })
  await load()
}

async function checkAll(val: boolean | string | number) {
  await apiCartCheckAll(Boolean(val))
  await load()
}

async function changeQty(row: CartRow, qty: number) {
  await apiCartUpdate(row.cartItemId, { quantity: qty, checked: row.checked === 1 })
  await load()
}

async function remove(row: CartRow) {
  await apiCartRemove(row.cartItemId)
  ElMessage.success('已移出购物车')
  await load()
}

async function batchRemoveChecked() {
  const checkedItems = items.value.filter((i) => i.checked === 1)
  if (!checkedItems.length) return
  await ElMessageBox.confirm(`确认删除选中的 ${checkedItems.length} 件商品吗？`, '批量删除', { type: 'warning' })
  for (const item of checkedItems) {
    await apiCartRemove(item.cartItemId)
  }
  ElMessage.success('已批量删除')
  isManageMode.value = false
  await load()
}

function openCheckout() {
  if (checkedCount.value === 0) return
  router.push('/order/confirm')
}

function goDetail(id: number) {
  router.push(`/products/${id}`)
}

function spText(spData?: string): string {
  try {
    const arr = JSON.parse(spData || '[]') as { key: string; value: string }[]
    return arr.map((x) => x.value).join(' / ') || '官方标配'
  } catch {
    return spData || '官方标配'
  }
}

onMounted(async () => {
  void loadRecommendations()
  await load()
  if (route.query.checkout === '1' && items.value.length > 0) {
    openCheckout()
  }
})
</script>

<style scoped>
/* Hallmark · commerce / compact · Pinduoduo-inspired · red anchor
 * Structure: centered utility header → product list → recommendations → fixed checkout.
 * Scoped to the cart; existing brand, APIs and navigation remain unchanged. */
.cart-scroll-container {
  --cart-accent: #e02e24;
  --cart-accent-hover: #c8251c;
  --cart-on-accent: #fff;
  --cart-canvas: var(--mall-surface-2, #f4f4f5);
  --cart-surface: var(--mall-surface, #fff);
  --cart-ink: var(--el-text-color-primary, #303133);
  --cart-muted: var(--el-text-color-secondary, #909399);
  --cart-border: var(--mall-border-light, #f4f4f5);
  --el-color-primary: var(--cart-accent);
  --el-color-primary-light-9: var(--mall-price-bg, #fff1f2);
  height: 100%;
  background: var(--cart-canvas);
  color: var(--cart-ink);
}
.cart-page {
  max-width: 1040px;
  margin: 0 auto;
  padding: 0 20px 100px;
}
.cart-page button { font-family: inherit; cursor: pointer; }
.cart-page button:focus-visible, .rec-card:focus-visible {
  outline: 2px solid var(--cart-accent);
  outline-offset: 3px;
}
.cart-header-bar {
  display: grid;
  grid-template-columns: 64px 1fr 64px;
  align-items: center;
  min-height: 64px;
  margin: 0 -20px;
  padding: 0 20px;
  background: var(--cart-surface);
}
.cart-main-title { margin: 0; text-align: center; font-size: 20px; font-weight: 600; }
.cart-count { font-size: 16px; font-weight: 400; }
.cart-back-btn, .manage-toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  padding: 0;
  border: 0;
  color: var(--cart-ink);
  background: none;
}
.cart-back-btn { justify-self: start; width: 40px; }
.manage-toggle-btn { justify-self: end; min-width: 44px; font-size: 14px; }
.manage-toggle-btn:hover, .goods-name:hover { color: var(--cart-accent); }
.cart-section-bar { display: flex; align-items: center; justify-content: space-between; padding: 20px 0 12px; }
.cart-section-title { position: relative; margin: 0; padding-bottom: 8px; color: var(--cart-accent); font-size: 16px; font-weight: 600; }
.cart-section-title::after { position: absolute; bottom: 0; left: 0; width: 28px; height: 3px; background: var(--cart-accent); content: ''; }
.cart-selection-hint { color: var(--cart-muted); font-size: 12px; }
.shipping-benefit-bar { display: flex; align-items: center; justify-content: space-between; min-height: 40px; margin-bottom: 10px; padding: 0 16px; border-radius: 6px; background: var(--mall-price-bg, #fff1f2); font-size: 12px; }
.sbb-text strong { color: var(--cart-accent); font-weight: 500; }
.sbb-more { display: inline-flex; align-items: center; gap: 4px; min-height: 40px; padding: 0; border: 0; background: none; color: var(--cart-accent); font-size: 12px; }
.shop-group-card { padding: 0 20px; border-radius: 8px; background: var(--cart-surface); }
.shop-group-head { display: flex; align-items: center; gap: 14px; min-height: 56px; border-bottom: 1px solid var(--cart-border); }
.shop-title-box { display: flex; align-items: center; gap: 7px; min-width: 0; }
.shop-icon { font-size: 18px; }
.shop-name { font-size: 14px; font-weight: 600; }
.shop-tag { padding: 1px 4px; border: 1px solid var(--cart-accent); border-radius: 3px; color: var(--cart-accent); font-size: 10px; line-height: 1.3; }
.cart-goods-row { display: flex; align-items: center; gap: 14px; padding: 20px 0; }
.cart-goods-row + .cart-goods-row { border-top: 1px solid var(--cart-border); }
.cart-page :deep(.el-checkbox) { margin-right: 0; --el-checkbox-checked-bg-color: var(--cart-accent); --el-checkbox-checked-input-border-color: var(--cart-accent); --el-checkbox-checked-text-color: var(--cart-ink); --el-checkbox-checked-icon-color: var(--cart-on-accent); }
.cart-page :deep(.el-checkbox__inner) { width: 20px; height: 20px; border-radius: 50%; }
.cart-page :deep(.el-checkbox__inner::after) { height: 9px; }
.cart-page :deep(.el-checkbox__input.is-indeterminate .el-checkbox__inner::before) { top: 8px; }
.cart-page :deep(.el-checkbox__label) { padding-left: 8px; font-size: 13px; }
.goods-checkbox :deep(.el-checkbox__label), .shop-checkbox :deep(.el-checkbox__label) { position: absolute; width: 1px; height: 1px; overflow: hidden; padding: 0; clip-path: inset(50%); }
.goods-img-box { width: 112px; height: 112px; flex-shrink: 0; overflow: hidden; padding: 0; border: 0; border-radius: 5px; background: var(--cart-canvas); }
.goods-img, .rec-img { display: block; width: 100%; height: 100%; }
.img-fallback { display: grid; place-items: center; width: 100%; height: 100%; color: var(--cart-muted); background: var(--cart-canvas); }
.goods-content { display: flex; flex: 1; flex-direction: column; align-items: flex-start; min-width: 0; align-self: stretch; gap: 8px; }
.goods-name { display: -webkit-box; overflow: hidden; padding: 0; border: 0; color: var(--cart-ink); background: none; font-size: 15px; font-weight: 400; line-height: 1.5; text-align: left; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow-wrap: anywhere; }
.goods-sku-pill { display: inline-flex; align-items: center; gap: 8px; max-width: 100%; padding: 4px 7px; border: 0; border-radius: 3px; background: var(--cart-canvas); color: var(--cart-muted); font-size: 12px; }
.goods-sku-pill span { overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.goods-sku-pill .el-icon { flex-shrink: 0; }
.goods-price-row { display: flex; align-items: flex-end; justify-content: space-between; gap: 8px; width: 100%; margin-top: auto; }
.price-box { flex-shrink: 0; color: var(--cart-accent); white-space: nowrap; }
.symbol { margin-right: 2px; font-size: 13px; }
.num { font-size: 24px; font-weight: 600; font-variant-numeric: tabular-nums; }
.stepper-box { display: flex; align-items: center; gap: 8px; }
.custom-stepper { width: 100px; }
.custom-stepper :deep(.el-input__wrapper) { border-radius: 3px; padding-right: 28px; padding-left: 28px; box-shadow: 0 0 0 1px var(--mall-border, #e4e4e7) inset; }
.custom-stepper :deep(.el-input-number__increase), .custom-stepper :deep(.el-input-number__decrease) { width: 27px; background: var(--cart-surface); }
.row-delete-btn { display: grid; place-items: center; width: 30px; height: 30px; padding: 0; border: 0; color: var(--cart-muted); background: none; }
.row-delete-btn:hover { color: var(--cart-accent); }
.empty-cart-card { display: flex; flex-direction: column; align-items: center; margin-top: 12px; padding: 42px 16px; border-radius: 8px; background: var(--cart-surface); text-align: center; }
.ecc-icon { display: grid; place-items: center; width: 84px; height: 84px; margin-bottom: 18px; border-radius: 50%; background: var(--cart-canvas); color: var(--cart-muted); }
.ecc-title { margin: 0; font-size: 18px; font-weight: 500; }
.ecc-sub { margin: 10px 0 22px; color: var(--cart-muted); font-size: 13px; }
.ecc-btn { min-width: 132px; height: 40px; border: 0; border-radius: 5px; background: var(--cart-accent); color: var(--cart-on-accent); font-size: 14px; }
.cart-recommend-section { padding-top: 26px; }
.crs-header { display: flex; justify-content: center; align-items: center; gap: 14px; margin-bottom: 18px; }
.crs-title { margin: 0; color: var(--cart-accent); font-size: 16px; font-weight: 600; }
.crs-line { width: 28px; height: 1px; background: var(--cart-accent); opacity: .25; }
.recommend-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.rec-card { display: flex; flex-direction: column; min-width: 0; overflow: hidden; border-radius: 6px; background: var(--cart-surface); color: inherit; text-decoration: none; }
.rec-img-box { width: 100%; aspect-ratio: 1; overflow: hidden; background: var(--cart-canvas); }
.rec-info { display: flex; flex: 1; flex-direction: column; gap: 6px; padding: 10px; }
.rec-name { display: -webkit-box; overflow: hidden; font-size: 13px; line-height: 1.5; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow-wrap: anywhere; }
.rec-points { overflow: hidden; color: var(--cart-muted); font-size: 11px; white-space: nowrap; text-overflow: ellipsis; }
.rec-foot { display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 8px; margin-top: auto; padding-top: 3px; }
.rec-price { color: var(--cart-accent); font-size: 20px; font-weight: 600; }
.rec-price small { margin-right: 2px; font-size: 12px; font-weight: 400; }
.rec-sales { color: var(--cart-muted); font-size: 11px; }
.recommend-error { color: var(--cart-muted); font-size: 13px; text-align: center; }
.recommend-error button { padding: 6px; border: 0; color: var(--cart-accent); background: none; }
.fixed-checkout-bar { position: fixed; z-index: 80; right: 0; bottom: 0; left: 0; border-top: 1px solid var(--cart-border); background: var(--cart-surface); }
.fcb-inner { display: flex; align-items: center; gap: 18px; min-height: 72px; max-width: 1040px; margin: 0 auto; padding: 10px 20px; }
.fcb-summary { display: flex; flex-direction: column; gap: 3px; align-items: flex-end; min-width: 0; margin-left: auto; }
.fcb-total-line { display: flex; align-items: baseline; white-space: nowrap; }
.fcb-label { margin-right: 6px; font-size: 13px; }
.fcb-symbol { color: var(--cart-accent); font-size: 13px; }
.fcb-price { color: var(--cart-accent); font-size: 24px; font-weight: 600; font-variant-numeric: tabular-nums; }
.fcb-sub { color: var(--cart-muted); font-size: 11px; white-space: nowrap; }
.fcb-action-btns { flex-shrink: 0; margin-left: auto; }
.fcb-summary + .fcb-action-btns { margin-left: 0; }
.checkout-submit-btn, .batch-delete-btn { min-width: 156px; height: 46px; padding: 0 18px; border: 0; border-radius: 5px; background: var(--cart-accent); color: var(--cart-on-accent); font-size: 16px; font-weight: 500; }
.checkout-submit-btn:not(:disabled):hover, .ecc-btn:hover { background: var(--cart-accent-hover); }
.checkout-submit-btn:disabled, .batch-delete-btn:disabled { opacity: .45; cursor: not-allowed; }
.batch-delete-btn { border: 1px solid var(--cart-accent); background: var(--cart-surface); color: var(--cart-accent); }
html.dark .cart-scroll-container { --cart-accent: var(--mall-price, #fb7185); --cart-accent-hover: #f58e9c; --cart-on-accent: #18181b; }
@media (max-width: 768px) {
  .cart-page { padding: 0 10px 90px; }
  .cart-header-bar { min-height: 52px; margin: 0 -10px; padding: 0 10px; }
  .cart-main-title { font-size: 18px; }
  .cart-count { font-size: 15px; }
  .cart-section-bar { padding: 16px 4px 8px; }
  .cart-section-title { font-size: 15px; }
  .cart-selection-hint { font-size: 11px; }
  .shipping-benefit-bar { min-height: 36px; padding: 0 12px; margin-bottom: 8px; }
  .sbb-more { min-height: 36px; }
  .shop-group-card { padding: 0 12px; }
  .shop-group-head { min-height: 48px; gap: 10px; }
  .shop-name { font-size: 13px; }
  .cart-goods-row { gap: 10px; padding: 15px 0; }
  .goods-img-box { width: 96px; height: 96px; }
  .goods-content { gap: 6px; }
  .goods-name { font-size: 13px; line-height: 1.45; }
  .goods-sku-pill { padding: 3px 6px; font-size: 11px; }
  .num { font-size: 20px; }
  .custom-stepper { width: 88px; }
  .custom-stepper :deep(.el-input__wrapper) { padding-right: 23px; padding-left: 23px; }
  .custom-stepper :deep(.el-input-number__increase), .custom-stepper :deep(.el-input-number__decrease) { width: 22px; }
  .goods-price-row { flex-wrap: wrap; row-gap: 4px; }
  .stepper-box { gap: 2px; margin-left: auto; }
  .row-delete-btn { width: 24px; }
  .recommend-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .cart-recommend-section { padding-top: 24px; }
  .crs-header { margin-bottom: 14px; }
  .fixed-checkout-bar { bottom: calc(56px + env(safe-area-inset-bottom)); }
  .fcb-inner { min-height: 62px; gap: 10px; padding: 8px 12px; }
  .fcb-price { font-size: 22px; }
  .fcb-sub { font-size: 10px; }
  .checkout-submit-btn, .batch-delete-btn { min-width: 116px; height: 42px; padding: 0 12px; font-size: 15px; }
}
@media (max-width: 374px) {
  .goods-img-box { width: 80px; height: 80px; }
  .cart-goods-row { gap: 8px; }
  .goods-price-row { flex-wrap: wrap; gap: 4px; }
  .stepper-box { margin-left: auto; }
  .fcb-inner { gap: 6px; padding-right: 8px; padding-left: 8px; }
  .fcb-label { margin-right: 2px; font-size: 12px; }
  .fcb-price { font-size: 19px; }
  .checkout-submit-btn, .batch-delete-btn { min-width: 100px; padding: 0 8px; font-size: 14px; }
}
</style>
