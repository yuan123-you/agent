<template>
  <div class="page cart-page">
    <div class="page-header-row" style="padding: 10px 14px 0;">
      <button class="translucent-circle-back" title="返回" @click="goBack">
        <el-icon><ArrowLeft /></el-icon>
      </button>
      <h3 class="page-title">我的购物车</h3>
    </div>
    <div class="cart-body">
      <!-- 商品列表 -->
      <div class="list">
        <div v-for="row in items" :key="row.cartItemId" class="cart-item">
          <el-checkbox :model-value="row.checked === 1" @change="toggleCheck(row)" />
          <el-image :src="row.imageUrl" fit="cover" class="pic" @click="goDetail(row.productId)" lazy decoding="async">
            <template #error>
              <div class="pic-fb">{{ row.name.slice(0, 1) }}</div>
            </template>
          </el-image>
          <div class="info">
            <div class="name" @click="goDetail(row.productId)">{{ row.name }}</div>
            <div v-if="row.skuSp" class="sku-tag">{{ spText(row.skuSp) }}</div>
            <div class="price">￥{{ row.price }}</div>
          </div>
          <div class="ops">
            <el-input-number :model-value="row.quantity" :min="1" :max="row.stock" size="small"
              @change="(v: number) => changeQty(row, v)" />
            <div class="subtotal">￥{{ row.subtotal }}</div>
            <el-button text type="danger" size="small" @click="remove(row)">删除</el-button>
          </div>
        </div>
        <el-empty v-if="!loading && items.length === 0" description="购物车空空如也，去逛逛吧">
          <el-button type="primary" @click="$router.push('/')">去逛逛</el-button>
        </el-empty>
      </div>
    </div>

    <!-- 结算栏（吸底） -->
    <div v-if="items.length > 0" class="checkout-bar">
      <el-checkbox :model-value="allChecked" @change="checkAll">全选</el-checkbox>
      <span class="total">合计：<b>￥{{ totalAmount }}</b></span>
      <el-button type="danger" :disabled="checkedCount === 0" @click="openCheckout">
        结算（{{ checkedCount }}）
      </el-button>
    </div>

    <!-- 确认订单弹窗 (对标三大电商平台专业收银台设计) -->
    <el-dialog
      v-model="showCheckout"
      title="确认订单"
      width="min(500px, 94vw)"
      class="checkout-pro-dialog"
      destroy-on-close
    >
      <div class="checkout-pro-body">
        <!-- 1. 收货地址卡片 -->
        <div class="cp-section-card">
          <div class="cp-card-label">📍 收货地址</div>
          <CheckoutAddressPicker v-model="selectedAddressId" />
        </div>

        <!-- 2. 商品清单与配送履约 -->
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
            <span>🚚 顺丰速运 · 极速出库</span>
            <span>📦 赠退货运费险</span>
          </div>
        </div>

        <!-- 3. 优惠券选择 -->
        <div class="cp-section-card">
          <div class="cp-card-label">🎫 优惠券抵扣</div>
          <CouponPicker
            v-model="selectedCouponId"
            :amount="totalAmount"
            @discount="(v) => (couponDiscountValue = v)"
          />
        </div>

        <!-- 4. 金额明细 -->
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
              立即支付 ￥{{ payableAmount }}
            </el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import CheckoutAddressPicker from '@/components/address/CheckoutAddressPicker.vue'
import CouponPicker from '@/components/mall/CouponPicker.vue'
import {
  apiCartCheckAll, apiCartCheckout, apiCartList, apiCartRemove, apiCartUpdate,
  apiPayOrder, type CartRow,
} from '@/api'

const router = useRouter()
const route = useRoute()
const items = ref<CartRow[]>([])
const loading = ref(false)
const totalAmount = ref(0)
const checkedCount = ref(0)
const showCheckout = ref(false)
const submitting = ref(false)
const selectedAddressId = ref<number>()
const selectedCouponId = ref<number>()
const couponDiscountValue = ref(0)
const payableAmount = computed(() =>
  Math.max(0, Number((totalAmount.value - couponDiscountValue.value).toFixed(2))),
)

const allChecked = computed(() => items.value.length > 0 && checkedCount.value === items.value.length)

async function load() {
  loading.value = true
  try {
    const data = await apiCartList()
    items.value = data.items
    totalAmount.value = data.totalAmount
    checkedCount.value = data.checkedCount
  } finally {
    loading.value = false
  }
}

async function toggleCheck(row: CartRow) {
  await apiCartUpdate(row.cartItemId, { checked: row.checked !== 1 })
  load()
}

async function checkAll(checked: unknown) {
  await apiCartCheckAll(Boolean(checked))
  load()
}

async function changeQty(row: CartRow, qty: number) {
  await apiCartUpdate(row.cartItemId, { quantity: qty })
  load()
}

async function remove(row: CartRow) {
  await apiCartRemove(row.cartItemId)
  ElMessage.success('已删除')
  load()
}

/** 打开结算：地址簿由 <CheckoutAddressPicker> 自行加载并自动选中默认地址 */
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
    // 结算后直接完成支付，无需用户再次确认
    await apiPayOrder(order.orderId)
    ElMessage.success(`下单并模拟支付成功：${order.orderNo}`)
    showCheckout.value = false
    router.push(`/orders/${order.orderId}`)
  } catch {
    // 拦截器已提示
  } finally {
    submitting.value = false
  }
}

function goDetail(id: number) {
  router.push(`/products/${id}`)
}

/** SKU 属性 JSON 转 "颜色:黑色，容量:256G" */
function spText(spData?: string): string {
  try {
    const arr = JSON.parse(spData || '[]') as { key: string; value: string }[]
    return arr.map((e) => `${e.key}:${e.value}`).join('，')
  } catch {
    return spData || ''
  }
}

onMounted(async () => {
  await load()
  if (route.query.checkout === '1' && items.value.length > 0) {
    openCheckout()
  }
})
</script>

<style scoped>
.cart-page {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.cart-body {
  flex: 1;
  overflow-y: auto;
  max-width: 960px;
  width: 100%;
  margin: 0 auto;
  padding: 16px;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.cart-item {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--mall-surface, #fff);
  border-radius: 8px;
  padding: 12px;
}

.pic {
  width: 80px;
  height: 80px;
  border-radius: 6px;
  cursor: pointer;
  flex-shrink: 0;
}

.pic-fb {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--mall-surface-2, #f5f7fa);
  color: var(--el-text-color-placeholder, #c0c4cc);
  font-size: 28px;
  font-weight: 700;
}

.info {
  flex: 1;
  min-width: 0;
}

.name {
  font-weight: 600;
  cursor: pointer;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;  overflow: hidden;
}

.sku-tag {
  display: inline-block;
  margin-top: 4px;
  padding: 1px 8px;
  border-radius: 4px;
  background: var(--el-fill-color);
  color: var(--el-text-color-secondary);
  font-size: 12px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.discount-note {
  margin-left: 10px;
  font-size: 12px;
  color: var(--el-color-danger);
}

.price {
  color: var(--el-color-danger);
  margin-top: 6px;
}

.ops {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.subtotal {
  font-weight: 700;
  color: var(--el-color-danger);
  font-size: 15px;
}

.checkout-bar {
  flex-wrap: wrap;
  display: flex;
  align-items: center;
  gap: 16px;
  background: var(--mall-surface, #fff);
  border-top: 1px solid var(--el-border-color-lighter, #ebeef5);
  padding: 10px 20px;
  padding-bottom: calc(10px + env(safe-area-inset-bottom));
}

.checkout-bar .total {
  margin-left: auto;
  font-size: 15px;
}

.checkout-bar .total b {
  color: var(--el-color-danger);
  font-size: 20px;
}

.amount {
  color: var(--el-color-danger);
}

.addr-form-item :deep(.el-form-item__content) {
  width: 100%;
}

@media (max-width: 768px) {
  .checkout-bar {
    padding: 8px 12px;
    gap: 8px;
  }
  .cart-body {
    padding: 10px;
  }

  .cart-item {
    padding: 8px;
    gap: 8px;
  }

  .pic {
    width: 64px;
    height: 64px;
  }

  .ops {
    gap: 4px;
  }
}

@media (max-width: 480px) {
  .cart-item {
    flex-wrap: wrap;
  }

  .info {
    flex-basis: calc(100% - 110px);
  }

  .ops {
    width: 100%;
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    justify-content: flex-end;
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

