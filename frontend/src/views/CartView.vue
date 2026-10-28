<template>
  <el-scrollbar class="cart-scroll-container">
    <div class="page cart-page">
      <!-- 1. 顶部操作栏：半透明圆形返回按钮 + 购物车标题 + 管理/完成切换 -->
      <div class="cart-header-bar">
        <div class="chb-left">
          <button class="translucent-circle-back" title="返回" @click="goBack">
            <el-icon :size="16"><ArrowLeft /></el-icon>
          </button>
          <h2 class="cart-main-title">购物车 <span v-if="items.length" class="cart-count">({{ items.length }})</span></h2>
        </div>
        <div class="chb-right">
          <button v-if="items.length > 0" class="manage-toggle-btn" @click="isManageMode = !isManageMode">
            {{ isManageMode ? '完成' : '管理' }}
          </button>
        </div>
      </div>

      <LoadingState v-if="loading && !items.length" variant="list" :count="3" label="正在加载购物车" />

      <!-- 2. 包邮与权益提示条 (对标拼多多/京东满减包邮提醒) -->
      <div v-if="items.length > 0" class="shipping-benefit-bar mall-card">
        <div class="sbb-left">
          <span class="sbb-badge">售后服务</span>
          <span class="sbb-text">退款、退换货可在订单中申请并查看处理进度</span>
        </div>
        <span class="sbb-more" @click="$router.push('/coupons')">领券 ›</span>
      </div>

      <!-- 3. 店铺与商品卡片组 (三大电商经典卡片结构) -->
      <div v-if="items.length > 0" class="shop-group-card mall-card">
        <div class="shop-group-head">
          <el-checkbox
            :model-value="allChecked"
            class="shop-checkbox"
            @change="checkAll"
          >
            <div class="shop-title-box">
              <el-icon class="shop-icon"><Shop /></el-icon>
              <span class="shop-name">官方自营旗舰店</span>
              <el-icon class="shop-arrow"><ArrowRight /></el-icon>
            </div>
          </el-checkbox>
          <span class="shop-tag">官方自营</span>
        </div>

        <div class="cart-items-list">
          <div
            v-for="row in items"
            :key="row.cartItemId"
            class="cart-goods-row"
            :class="{ selected: row.checked === 1 }"
          >
            <!-- 勾选框 -->
            <el-checkbox
              :model-value="row.checked === 1"
              class="goods-checkbox"
              @change="toggleCheck(row)"
            />

            <!-- 商品主图 -->
            <div class="goods-img-box" @click="goDetail(row.productId)">
              <el-image :src="row.imageUrl" fit="cover" class="goods-img" lazy decoding="async">
                <template #error>
                  <div class="img-fallback">🛍️</div>
                </template>
              </el-image>
            </div>

            <!-- 商品信息与操作 -->
            <div class="goods-content">
              <div class="goods-name" @click="goDetail(row.productId)">
                {{ row.name }}
              </div>
              <div class="goods-sku-pill" @click="goDetail(row.productId)">
                <span>{{ row.skuSp ? spText(row.skuSp) : '官方正品 · 标配' }}</span>
                <el-icon :size="10"><ArrowRight /></el-icon>
              </div>

              <div class="goods-price-row">
                <div class="price-box">
                  <span class="symbol">￥</span>
                  <span class="num">{{ row.price }}</span>
                </div>

                <!-- 步进器与删除 -->
                <div class="stepper-box">
                  <el-input-number
                    :model-value="row.quantity"
                    :min="1"
                    :max="row.stock || 99"
                    size="small"
                    class="custom-stepper"
                    @change="(v: number) => changeQty(row, v)"
                  />
                  <button v-if="isManageMode" class="row-delete-btn" title="删除" @click.stop="remove(row)">
                    <el-icon :size="14"><Delete /></el-icon>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 4. 空购物车缺省页 -->
      <div v-if="!loading && items.length === 0" class="empty-cart-card mall-card">
        <div class="ecc-icon">🛒</div>
        <div class="ecc-title">购物车空空如也</div>
        <p class="ecc-sub">精选好物正在热卖中，去挑一件心仪的商品吧</p>
        <el-button type="danger" round class="ecc-btn" @click="$router.push('/')">
          去逛逛爆款好物
        </el-button>
      </div>

      <!-- 5. 猜你喜欢推荐瀑布流 (拼多多/京东/淘宝购物车底栏标配) -->
      <section class="cart-recommend-section">
        <div class="crs-header">
          <span class="crs-line" />
          <span class="crs-title">🔥 猜你喜欢 · 精选推荐</span>
          <span class="crs-line" />
        </div>

        <p v-if="recommendError" role="alert">推荐商品加载失败 <button @click="loadRecommendations">重试</button></p>
        <LoadingState v-if="recommendLoading" variant="cards" :count="4" label="正在加载推荐商品" />
        <div class="recommend-grid">
          <div
            v-for="p in recommendProducts"
            :key="p.id"
            class="rec-card mall-card"
            @click="$router.push(`/products/${p.id}`)"
          >
            <div class="rec-img-box">
              <el-image :src="p.imageUrl" fit="cover" class="rec-img" lazy decoding="async">
                <template #error><div class="rec-fb">🛍️</div></template>
              </el-image>
            </div>
            <div class="rec-info">
              <div class="rec-name">{{ p.name }}</div>
              <div class="rec-points">{{ p.sellingPoints || '品质认证 · 顺丰直达' }}</div>
              <div class="rec-foot">
                <span class="rec-price">￥{{ p.price }}</span>
                <span class="rec-sales">已拼 {{ formatSales(p.sales) }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 6. 底部固定吸底结算栏 (对标三大电商悬浮吸底标准) -->
      <div v-if="items.length > 0" class="fixed-checkout-bar">
        <div class="fcb-inner">
          <el-checkbox
            :model-value="allChecked"
            class="fcb-checkbox"
            @change="checkAll"
          >
            全选
          </el-checkbox>

          <div v-if="!isManageMode" class="fcb-summary">
            <div class="fcb-total-line">
              <span class="fcb-label">合计:</span>
              <span class="fcb-symbol">￥</span>
              <span class="fcb-price">{{ totalAmount.toFixed(2) }}</span>
            </div>
            <span class="fcb-sub">顺丰速运免运费</span>
          </div>

          <div class="fcb-action-btns">
            <template v-if="!isManageMode">
              <button
                class="checkout-submit-btn"
                :disabled="checkedCount === 0"
                @click="openCheckout"
              >
                结算 ({{ checkedCount }})
              </button>
            </template>
            <template v-else>
              <button
                class="batch-delete-btn"
                :disabled="checkedCount === 0"
                @click="batchRemoveChecked"
              >
                删除选中的商品 ({{ checkedCount }})
              </button>
            </template>
          </div>
        </div>
      </div>

      <!-- 7. 确认订单弹窗 (三大电商专业收银台设计) -->
      <el-dialog
        v-model="showCheckout"
        title="确认订单"
        width="min(500px, 94vw)"
        class="checkout-pro-dialog"
        destroy-on-close
      >
        <div class="checkout-pro-body">
          <!-- 收货地址 -->
          <div class="cp-section-card">
            <div class="cp-card-label">📍 收货地址</div>
            <CheckoutAddressPicker v-model="selectedAddressId" />
          </div>

          <!-- 商品清单与履约 -->
          <div class="cp-section-card">
            <div class="cp-card-label">🛍️ 选购商品 ({{ checkedCount }}件)</div>
            <div class="cp-items-scroll">
              <div
                v-for="row in items.filter(i => i.checked === 1)"
                :key="row.cartItemId"
                class="cp-item-row"
              >
                <el-image :src="row.imageUrl" fit="cover" class="cp-item-img" lazy decoding="async">
                  <template #error><div class="cp-fb">🛍️</div></template>
                </el-image>
                <div class="cp-item-info">
                  <div class="cpi-name">{{ row.name }}</div>
                  <div class="cpi-spec">{{ row.skuSp ? spText(row.skuSp) : '官方标配' }}</div>
                  <div class="cpi-bottom">
                    <span class="cpi-price">￥{{ row.price }}</span>
                    <span class="cpi-qty">× {{ row.quantity }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="cp-delivery-badge">
              <span>配送信息以订单登记为准</span>
              <span>退换货与运费安排以审核及协商结果为准</span>
            </div>
          </div>

          <!-- 优惠券选择 -->
          <div class="cp-section-card">
            <div class="cp-card-label">🎫 优惠券抵扣</div>
            <CouponPicker
              v-model="selectedCouponId"
              :amount="totalAmount"
              @discount="(v) => (couponDiscountValue = v)"
            />
          </div>

          <!-- 费用明细 -->
          <div class="cp-calc-card">
            <div class="cpc-row">
              <span>商品总额</span>
              <span>￥{{ totalAmount.toFixed(2) }}</span>
            </div>
            <div class="cpc-row">
              <span>运费</span>
              <span class="free-text">免运费</span>
            </div>
            <div v-if="couponDiscountValue > 0" class="cpc-row discount">
              <span>优惠券立减</span>
              <span>-￥{{ couponDiscountValue.toFixed(2) }}</span>
            </div>
            <div class="cpc-row total">
              <span>实付款</span>
              <span class="cpc-total-val">￥{{ payableAmount }}</span>
            </div>
          </div>
        </div>

        <template #footer>
          <div class="checkout-footer-row">
            <div class="cfr-left">
              <span class="cfr-label">实付：</span>
              <span class="cfr-price">￥{{ payableAmount }}</span>
            </div>
            <div class="cfr-right">
              <el-button @click="showCheckout = false">取消</el-button>
              <el-button
                type="danger"
                class="cfr-pay-btn"
                :loading="submitting"
                :disabled="!selectedAddressId"
                @click="submit"
              >
                模拟支付 ￥{{ payableAmount }}
              </el-button>
            </div>
          </div>
        </template>
      </el-dialog>
    </div>
  </el-scrollbar>
</template>

<script setup lang="ts">
import LoadingState from '@/components/common/LoadingState.vue'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, ArrowRight, Delete, Shop } from '@element-plus/icons-vue'
import CheckoutAddressPicker from '@/components/address/CheckoutAddressPicker.vue'
import CouponPicker from '@/components/mall/CouponPicker.vue'
import {
  apiCartCheckAll, apiCartCheckout, apiCartList, apiCartRemove, apiCartUpdate,
  apiPayOrder, apiProducts, type CartRow,
} from '@/api'
import type { ProductVO } from '@/types/api'

const router = useRouter()
const route = useRoute()

const items = ref<CartRow[]>([])
const loading = ref(false)
const totalAmount = ref(0)
const checkedCount = ref(0)
const showCheckout = ref(false)
const submitting = ref(false)
const isManageMode = ref(false)
const selectedAddressId = ref<number>()
const selectedCouponId = ref<number>()
const couponDiscountValue = ref(0)

const payableAmount = computed(() =>
  Math.max(0, Number((totalAmount.value - couponDiscountValue.value).toFixed(2))),
)

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

async function openCheckout() {
  showCheckout.value = true
  selectedAddressId.value = undefined
  selectedCouponId.value = undefined
  couponDiscountValue.value = 0
}

async function submit() {
  if (!selectedAddressId.value) {
    ElMessage.warning('请先选择或新增收货地址')
    return
  }
  submitting.value = true
  try {
    const order = await apiCartCheckout({
      addressId: selectedAddressId.value,
      couponUserId: selectedCouponId.value,
    })
    // 结算后直接完成模拟支付
    await apiPayOrder(order.orderId)
    ElMessage.success(`下单并模拟支付成功：${order.orderNo}`)
    showCheckout.value = false
    router.push(`/orders/${order.orderId}`)
  } catch {
    // 拦截器已处理
  } finally {
    submitting.value = false
  }
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
.cart-scroll-container {
  height: 100%;
  background: var(--mall-page-bg, #f8fafc);
}

.cart-page {
  max-width: 760px;
  margin: 0 auto;
  padding: 12px 14px 100px; /* 留出底部吸底结算栏高度 */
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 顶部操作条 */
.cart-header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 2px;
}

.chb-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.cart-main-title {
  font-size: 18px;
  font-weight: 800;
  color: #18181b;
  margin: 0;
}

html.dark .cart-main-title {
  color: #f4f4f5;
}

.cart-count {
  font-size: 13px;
  font-weight: 600;
  color: #71717a;
}

.manage-toggle-btn {
  border: none;
  background: transparent;
  color: #71717a;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: color 0.15s ease;
}

.manage-toggle-btn:hover {
  color: var(--mall-price, #e11d48);
}

/* 包邮福利条 */
.shipping-benefit-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--mall-surface, #ffffff);
  border-radius: var(--mall-radius, 10px);
  font-size: 11px;
}

.sbb-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.sbb-badge {
  background: #ecfdf5;
  color: #059669;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 4px;
}

.sbb-text {
  color: #52525b;
}

html.dark .sbb-text {
  color: #a1a1aa;
}

.sbb-more {
  color: var(--mall-price, #e11d48);
  font-weight: 600;
  cursor: pointer;
}

/* 店铺卡片 */
.shop-group-card {
  background: var(--mall-surface, #ffffff);
  border-radius: var(--mall-radius, 10px);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
}

.shop-group-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--mall-border-light, #f4f4f5);
}

.shop-title-box {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: 6px;
}

.shop-icon {
  font-size: 14px;
  color: #18181b;
}

html.dark .shop-icon {
  color: #f4f4f5;
}

.shop-name {
  font-size: 13px;
  font-weight: 700;
  color: #18181b;
}

html.dark .shop-name {
  color: #f4f4f5;
}

.shop-arrow {
  font-size: 11px;
  color: #a1a1aa;
}

.shop-tag {
  font-size: 10px;
  font-weight: 600;
  color: #fff;
  background: #18181b;
  padding: 2px 6px;
  border-radius: 3px;
}

html.dark .shop-tag {
  background: #ffffff;
  color: #18181b;
}

.cart-items-list {
  display: flex;
  flex-direction: column;
}

.cart-goods-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 0;
  border-bottom: 1px solid var(--mall-border-light, #f4f4f5);
}

.cart-goods-row:last-child {
  border-bottom: none;
}

.goods-checkbox {
  margin-right: 0;
}

.goods-img-box {
  width: 76px;
  height: 76px;
  border-radius: 8px;
  overflow: hidden;
  background: var(--mall-surface-2, #f4f4f5);
  flex-shrink: 0;
  cursor: pointer;
}

.goods-img {
  width: 100%;
  height: 100%;
}

.img-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.goods-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.goods-name {
  font-size: 13px;
  font-weight: 600;
  color: #18181b;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  cursor: pointer;
}

html.dark .goods-name {
  color: #f4f4f5;
}

.goods-sku-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: var(--mall-surface-2, #f4f4f5);
  color: #71717a;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  align-self: flex-start;
  cursor: pointer;
}

html.dark .goods-sku-pill {
  background: #27272a;
  color: #a1a1aa;
}

.goods-price-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 2px;
}

.price-box {
  display: flex;
  align-items: baseline;
  color: var(--mall-price, #e11d48);
}

.price-box .symbol {
  font-size: 12px;
  font-weight: 700;
}

.price-box .num {
  font-size: 17px;
  font-weight: 800;
}

.stepper-box {
  display: flex;
  align-items: center;
  gap: 8px;
}

.custom-stepper {
  width: 90px;
}

.row-delete-btn {
  border: none;
  background: transparent;
  color: #ef4444;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
}

/* 空购物车 */
.empty-cart-card {
  padding: 40px 20px;
  background: var(--mall-surface, #ffffff);
  border-radius: var(--mall-radius, 10px);
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.ecc-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.ecc-title {
  font-size: 16px;
  font-weight: 700;
  color: #18181b;
}

html.dark .ecc-title {
  color: #f4f4f5;
}

.ecc-sub {
  font-size: 12px;
  color: #71717a;
  margin: 6px 0 16px;
}

.ecc-btn {
  font-weight: 700;
  padding: 8px 24px;
}

/* 猜你喜欢瀑布流 */
.cart-recommend-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 8px;
}

.crs-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 6px 0;
}

.crs-line {
  height: 1px;
  width: 40px;
  background: var(--mall-border, #e4e4e7);
}

.crs-title {
  font-size: 13px;
  font-weight: 700;
  color: #71717a;
}

.recommend-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.rec-card {
  background: var(--mall-surface, #ffffff);
  border-radius: var(--mall-radius, 10px);
  overflow: hidden;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  transition: transform 0.2s ease;
}

.rec-card:hover {
  transform: translateY(-2px);
}

.rec-img-box {
  width: 100%;
  aspect-ratio: 1;
  background: #f4f4f5;
}

.rec-img {
  width: 100%;
  height: 100%;
}

.rec-fb {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
}

.rec-info {
  padding: 8px 10px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.rec-name {
  font-size: 12px;
  font-weight: 600;
  color: #18181b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

html.dark .rec-name {
  color: #f4f4f5;
}

.rec-points {
  font-size: 10px;
  color: #71717a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rec-foot {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-top: 4px;
}

.rec-price {
  font-size: 14px;
  font-weight: 800;
  color: var(--mall-price, #e11d48);
}

.rec-sales {
  font-size: 10px;
  color: #a1a1aa;
}

/* ================= 底部固定吸底结算栏 (大厂标配) ================= */
.fixed-checkout-bar {
  position: fixed;
  bottom: calc(56px + env(safe-area-inset-bottom));
  left: 0;
  right: 0;
  background: rgba(255, 255, 255, 0.98);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-top: 1px solid var(--mall-border-light, #f4f4f5);
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.04);
  z-index: 80;
}

html.dark .fixed-checkout-bar {
  background: rgba(18, 18, 21, 0.98);
  border-top-color: var(--mall-border, #27272a);
}

.fcb-inner {
  max-width: 760px;
  margin: 0 auto;
  padding: 8px 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.fcb-checkbox {
  margin-right: 0;
}

.fcb-summary {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  margin-left: auto;
}

.fcb-total-line {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.fcb-label {
  font-size: 12px;
  font-weight: 600;
  color: #71717a;
}

.fcb-symbol {
  font-size: 12px;
  font-weight: 700;
  color: var(--mall-price, #e11d48);
  margin-left: 2px;
}

.fcb-price {
  font-size: 19px;
  font-weight: 800;
  color: var(--mall-price, #e11d48);
  letter-spacing: -0.02em;
}

.fcb-sub {
  font-size: 10px;
  color: #059669;
}

.checkout-submit-btn {
  height: 40px;
  padding: 0 24px;
  border-radius: 9999px;
  border: none;
  background: linear-gradient(135deg, #e11d48 0%, #f43f5e 100%);
  color: #ffffff;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(225, 29, 72, 0.3);
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.checkout-submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  box-shadow: none;
}

.checkout-submit-btn:not(:disabled):active {
  transform: scale(0.97);
}

.batch-delete-btn {
  height: 40px;
  padding: 0 20px;
  border-radius: 9999px;
  border: 1px solid #ef4444;
  background: #fef2f2;
  color: #ef4444;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.batch-delete-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (min-width: 769px) {
  .fixed-checkout-bar {
    bottom: 0;
  }
}

/* ================= 确认订单收银台 (三大电商平台专业重构) ================= */
.checkout-pro-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cp-section-card {
  padding: 12px 14px;
  background: var(--mall-surface-2, #f4f4f5);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

html.dark .cp-section-card {
  background: #18181b;
}

.cp-card-label {
  font-size: 12px;
  font-weight: 700;
  color: #71717a;
}

.cp-items-scroll {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 180px;
  overflow-y: auto;
}

.cp-item-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
}

.cp-item-img {
  width: 44px;
  height: 44px;
  border-radius: 6px;
  flex-shrink: 0;
}

.cp-fb {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e4e4e7;
  font-size: 16px;
}

.cp-item-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.cpi-name {
  font-size: 12px;
  font-weight: 600;
  color: #18181b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

html.dark .cpi-name {
  color: #f4f4f5;
}

.cpi-spec {
  font-size: 10px;
  color: #a1a1aa;
}

.cpi-bottom {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.cpi-price {
  font-size: 12px;
  font-weight: 700;
  color: var(--mall-price, #e11d48);
}

.cpi-qty {
  font-size: 11px;
  color: #71717a;
}

.cp-delivery-badge {
  display: flex;
  gap: 10px;
  font-size: 10px;
  color: #059669;
  padding-top: 4px;
}

.cp-calc-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 14px;
  background: var(--mall-surface-2, #f4f4f5);
  border-radius: 8px;
  font-size: 12px;
  color: #71717a;
}

html.dark .cp-calc-card {
  background: #18181b;
}

.cpc-row {
  display: flex;
  justify-content: space-between;
}

.cpc-row .free-text {
  color: #059669;
}

.cpc-row.discount {
  color: var(--mall-price, #e11d48);
}

.cpc-row.total {
  font-size: 13px;
  font-weight: 700;
  color: #18181b;
  padding-top: 4px;
  border-top: 1px dashed #d4d4d8;
}

html.dark .cpc-row.total {
  color: #f4f4f5;
  border-top-color: #27272a;
}

.cpc-total-val {
  font-size: 16px;
  font-weight: 800;
  color: var(--mall-price, #e11d48);
}

.checkout-footer-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.cfr-left {
  display: flex;
  align-items: baseline;
}

.cfr-label {
  font-size: 12px;
  color: #71717a;
}

.cfr-price {
  font-size: 18px;
  font-weight: 800;
  color: var(--mall-price, #e11d48);
}

.cfr-right {
  display: flex;
  gap: 8px;
}

.cfr-pay-btn {
  background: var(--mall-price, #e11d48) !important;
  border-color: var(--mall-price, #e11d48) !important;
  color: #ffffff !important;
  font-weight: 700 !important;
  border-radius: 9999px !important;
  padding: 0 18px !important;
}
</style>
