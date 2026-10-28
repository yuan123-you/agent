<template>
  <div class="order-confirm-container">
    <!-- 顶部极简导航栏 (对标拼多多/京东/淘宝订单页顶部) -->
    <header class="confirm-topbar">
      <div class="topbar-inner">
        <button class="topbar-back-btn" title="返回" @click="goBack">
          <el-icon :size="18"><ArrowLeft /></el-icon>
        </button>
        <h1 class="topbar-title">确认订单</h1>
        <div class="topbar-safe-tag">
          <el-icon :size="14"><CircleCheckFilled /></el-icon>
          <span>官方保障</span>
        </div>
      </div>
    </header>

    <!-- 加载中骨架 -->
    <LoadingState v-if="loading" variant="detail" label="正在加载订单详情" />

    <!-- 订单主体内容 -->
    <main v-else-if="items.length > 0" class="confirm-main">
      <!-- 1. 收货地址卡片 (淘宝/京东经典彩条信封条设计) -->
      <section class="confirm-card address-card" @click="openAddressModal">
        <div class="envelope-stripe"></div>
        <div class="address-card-body">
          <div class="addr-icon-box">
            <el-icon :size="20"><Location /></el-icon>
          </div>

          <div v-if="selectedAddress" class="addr-content">
            <div class="addr-user-line">
              <span class="addr-user-name">{{ selectedAddress.receiverName }}</span>
              <span class="addr-user-phone">{{ selectedAddress.receiverPhone }}</span>
              <span v-if="selectedAddress.isDefault" class="addr-badge-default">默认</span>
            </div>
            <div class="addr-full-text">
              {{ selectedAddress.receiverAddress || selectedAddress.detailAddress }}
            </div>
          </div>

          <div v-else class="addr-empty-content">
            <div class="addr-empty-title">点击添加收货地址</div>
            <div class="addr-empty-sub">暂无收货地址，请先添加以完成订单配送</div>
          </div>

          <div class="addr-arrow">
            <span class="addr-action-text">{{ selectedAddress ? '修改' : '添加' }}</span>
            <el-icon :size="14"><Right /></el-icon>
          </div>
        </div>
      </section>

      <!-- 2. 店铺与商品卡片 (自营店铺规范) -->
      <section class="confirm-card store-card">
        <!-- 店铺标头 -->
        <div class="store-header">
          <div class="sh-left">
            <el-icon :size="18" class="store-icon"><Shop /></el-icon>
            <span class="store-name">AI Mall 官方自营旗舰店</span>
            <span class="store-tag-self">自营</span>
          </div>
          <span class="store-shipping-badge">顺丰速运 · 极速履约</span>
        </div>

        <!-- 商品列表 -->
        <div class="goods-list">
          <div v-for="item in items" :key="item.id" class="goods-row">
            <el-image :src="item.imageUrl" fit="cover" class="goods-img" lazy decoding="async">
              <template #error>
                <div class="goods-img-fallback">🛍️</div>
              </template>
            </el-image>

            <div class="goods-info">
              <div class="goods-title">{{ item.name }}</div>
              <div class="goods-spec-badge">
                <span>{{ item.skuSp ? spText(item.skuSp) : '官方标配' }}</span>
              </div>
              <div class="goods-price-row">
                <div class="goods-price">
                  <span class="currency">￥</span>
                  <span class="price-val">{{ Number(item.price).toFixed(2) }}</span>
                </div>

                <!-- 立即购买单品支持数量步进器微调；购物车多选展示固定件数 -->
                <div v-if="isBuyNow" class="goods-stepper">
                  <button
                    class="step-btn"
                    :disabled="item.quantity <= 1 || submitting"
                    @click="updateBuyNowQty(item.quantity - 1)"
                  >
                    -
                  </button>
                  <span class="step-num">{{ item.quantity }}</span>
                  <button
                    class="step-btn"
                    :disabled="item.quantity >= (item.stock || 99) || submitting"
                    @click="updateBuyNowQty(item.quantity + 1)"
                  >
                    +
                  </button>
                </div>
                <div v-else class="goods-qty">
                  × {{ item.quantity }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 履约承诺说明条 (对标确认订单专业规范) -->
        <div class="fulfillment-pledge">
          <span class="fp-badge">服务声明</span>
          <span class="fp-text">配送信息以订单登记为准 · 退换货与运费安排以审核及协商结果为准</span>
        </div>

        <!-- 增值服务标签 -->
        <div class="service-guarantees">
          <div class="sg-item"><el-icon><CircleCheckFilled /></el-icon> 正品保障</div>
          <div class="sg-item"><el-icon><CircleCheckFilled /></el-icon> 七天无理由退换</div>
          <div class="sg-item"><el-icon><CircleCheckFilled /></el-icon> 商家赠送运费险</div>
          <div class="sg-item"><el-icon><CircleCheckFilled /></el-icon> 极速退款</div>
        </div>

        <!-- 配送与留言配置行 -->
        <div class="order-ext-rows">
          <div class="ext-row">
            <span class="ext-label">配送服务</span>
            <span class="ext-value highlight">普通快递 免运费 (预计1-3日送达)</span>
          </div>
          <div class="ext-row">
            <span class="ext-label">退运保险</span>
            <span class="ext-value">商家赠送 · 最高赔付￥15</span>
          </div>
          <div class="ext-row">
            <span class="ext-label">发票服务</span>
            <span class="ext-value">电子普通发票 · 个人 (商品明细)</span>
          </div>
          <div class="ext-row remark-row">
            <span class="ext-label">买家留言</span>
            <input
              v-model="orderRemarks"
              type="text"
              class="remark-input"
              placeholder="选填，给商家留言（如送货时间要求等）"
              maxlength="100"
            />
          </div>
        </div>
      </section>

      <!-- 3. 优惠券抵扣卡片 (对标拼多多/淘宝优惠券模块) -->
      <section class="confirm-card coupon-card">
        <div class="card-title-row">
          <div class="ctr-left">
            <span class="card-icon">🎫</span>
            <span class="card-title">优惠券抵扣</span>
          </div>
          <span v-if="couponDiscountValue > 0" class="coupon-saved-tag">
            已优惠 ￥{{ couponDiscountValue.toFixed(2) }}
          </span>
        </div>

        <CouponPicker
          v-model="selectedCouponId"
          :amount="totalAmount"
          @discount="onCouponDiscountChange"
        />
      </section>

      <!-- 4. 支付方式卡片 (对标京东收银台) -->
      <section class="confirm-card payment-card">
        <div class="card-title-row">
          <div class="ctr-left">
            <span class="card-icon">💳</span>
            <span class="card-title">支付方式</span>
          </div>
          <span class="payment-badge">演示免充值 · 一键支付</span>
        </div>
        <div class="payment-desc">
          当前处于演示商城环境，点击提交订单即可完成模拟全流程支付，无需输入银行卡密码，不会扣除真实资金。
        </div>
      </section>

      <!-- 5. 费用明细卡片 (对标拼多多/京东金额账单) -->
      <section class="confirm-card bill-card">
        <div class="bill-row">
          <span class="bill-label">商品总额</span>
          <span class="bill-val">￥{{ totalAmount.toFixed(2) }}</span>
        </div>
        <div class="bill-row">
          <span class="bill-label">配送运费</span>
          <span class="bill-val free-text">免运费</span>
        </div>
        <div class="bill-row">
          <span class="bill-label">运费险</span>
          <span class="bill-val free-text">商家赠送</span>
        </div>
        <div v-if="couponDiscountValue > 0" class="bill-row discount-row">
          <span class="bill-label">优惠券立减</span>
          <span class="bill-val">-￥{{ couponDiscountValue.toFixed(2) }}</span>
        </div>
        <div class="bill-divider"></div>
        <div class="bill-row total-row">
          <span class="total-label">实付款</span>
          <span class="total-price">
            <i class="currency">￥</i>{{ payableAmount }}
          </span>
        </div>
      </section>

      <!-- 安全与免责保障卡片 -->
      <div class="safe-note-card">
        <span class="sn-icon">🛡️</span>
        <span class="sn-text">
          演示商城承诺：正品货源直发 · 订单可随时查询履约进度 · 售后无忧快速响应
        </span>
      </div>
    </main>

    <!-- 空状态（无商品可结算） -->
    <div v-else class="empty-state-card">
      <el-empty description="暂无可结算的商品" :image-size="80">
        <el-button type="primary" round @click="goShopping">前往商城选购商品</el-button>
      </el-empty>
    </div>

    <!-- 底部固定吸底提交栏 (拼多多/京东/淘宝经典设计) -->
    <footer v-if="items.length > 0" class="confirm-bottom-bar">
      <div class="bottom-bar-inner">
        <div class="bbar-left">
          <div class="bbar-summary">
            <span class="bbar-count">共 {{ totalQuantity }} 件，</span>
            <span class="bbar-label">实付款：</span>
            <span class="bbar-price">
              <i class="bbar-currency">￥</i>{{ payableAmount }}
            </span>
          </div>
          <div v-if="couponDiscountValue > 0" class="bbar-savings">
            已为您节省 ￥{{ couponDiscountValue.toFixed(2) }}
          </div>
        </div>

        <div class="bbar-right">
          <button
            class="submit-order-btn"
            :disabled="!selectedAddressId || submitting"
            @click="submitOrder"
          >
            <span v-if="submitting" class="submitting-spinner"></span>
            <span>{{ submitting ? '正在创建订单...' : `模拟支付 ￥${payableAmount}` }}</span>
          </button>
        </div>
      </div>
    </footer>

    <!-- 地址切换 / 新增弹窗 -->
    <el-dialog
      v-model="showAddressModal"
      title="选择或新增收货地址"
      width="min(560px, 94vw)"
      align-center
      destroy-on-close
      class="address-picker-dialog"
    >
      <div class="address-modal-content">
        <CheckoutAddressPicker
          v-model="selectedAddressId"
          @update:model-value="onAddressSelect"
        />
      </div>
      <template #footer>
        <el-button @click="showAddressModal = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft, CircleCheckFilled, Location, Right, Shop,
} from '@element-plus/icons-vue'
import LoadingState from '@/components/common/LoadingState.vue'
import CheckoutAddressPicker from '@/components/address/CheckoutAddressPicker.vue'
import CouponPicker from '@/components/mall/CouponPicker.vue'
import { preferredAddress } from '@/components/address/checkoutAddress'
import {
  apiAddresses,
  apiCartCheckout,
  apiCartList,
  apiCatalogProductSkus,
  apiCreateOrder,
  apiPayOrder,
  apiProductDetail,
} from '@/api'
import type { AddressVO, SkuVO } from '@/types/api'
import { useCartStore } from '@/stores/cart'

interface CheckoutItem {
  id: number | string
  productId: number
  skuId?: number
  name: string
  imageUrl: string
  price: number
  quantity: number
  skuSp?: string
  stock?: number
}

const route = useRoute()
const router = useRouter()
const cartStore = useCartStore()

const loading = ref(true)
const submitting = ref(false)
const items = ref<CheckoutItem[]>([])
const addresses = ref<AddressVO[]>([])
const selectedAddressId = ref<number>()
const selectedCouponId = ref<number>()
const couponDiscountValue = ref(0)
const orderRemarks = ref('')
const showAddressModal = ref(false)

const isBuyNow = computed(() => Boolean(route.query.productId))

const selectedAddress = computed(() =>
  addresses.value.find((a) => a.addressId === selectedAddressId.value),
)

const totalAmount = computed(() =>
  Number(
    items.value
      .reduce((sum, item) => sum + Number(item.price) * item.quantity, 0)
      .toFixed(2),
  ),
)

const totalQuantity = computed(() =>
  items.value.reduce((sum, item) => sum + item.quantity, 0),
)

const payableAmount = computed(() =>
  Math.max(0, Number((totalAmount.value - couponDiscountValue.value).toFixed(2))),
)

function goBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push(isBuyNow.value ? `/products/${route.query.productId}` : '/cart')
  }
}

function goShopping() {
  router.push('/products')
}

function openAddressModal() {
  showAddressModal.value = true
}

function onAddressSelect(newId: number | undefined) {
  selectedAddressId.value = newId
  void reloadAddresses(newId)
  showAddressModal.value = false
}

function onCouponDiscountChange(discount: number) {
  couponDiscountValue.value = Number(discount) || 0
}

function updateBuyNowQty(newQty: number) {
  if (items.value.length === 0) return
  const item = items.value[0]
  const maxStock = item.stock || 99
  const clamped = Math.max(1, Math.min(newQty, maxStock))
  item.quantity = clamped
  // 保持 query 联动
  router.replace({
    query: {
      ...route.query,
      quantity: String(clamped),
    },
  })
}

function spText(spData?: string): string {
  try {
    const arr = JSON.parse(spData || '[]') as { key: string; value: string }[]
    return arr.map((x) => x.value).join(' / ') || '官方标配'
  } catch {
    return spData || '官方标配'
  }
}

async function reloadAddresses(targetId?: number) {
  try {
    const list = await apiAddresses()
    addresses.value = list || []
    if (targetId) {
      selectedAddressId.value = targetId
    } else if (!selectedAddressId.value && list && list.length > 0) {
      selectedAddressId.value = preferredAddress(list)?.addressId
    }
  } catch (err) {
    console.error('加载地址列表失败', err)
  }
}

async function loadData() {
  loading.value = true
  try {
    await reloadAddresses()

    if (isBuyNow.value) {
      const pid = Number(route.query.productId)
      const sid = route.query.skuId ? Number(route.query.skuId) : undefined
      const qty = Math.max(1, Number(route.query.quantity) || 1)

      const product = await apiProductDetail(pid)
      let price = product.price
      let imageUrl = product.imageUrl
      let skuSp = ''
      let stock = product.stock

      if (sid) {
        try {
          const skus = (await apiCatalogProductSkus(pid)) || []
          const foundSku: SkuVO | undefined = skus.find((s) => s.id === sid)
          if (foundSku) {
            price = foundSku.price != null ? foundSku.price : price
            imageUrl = foundSku.imageUrl || imageUrl
            skuSp = foundSku.spData || ''
            stock = foundSku.stock != null ? foundSku.stock : stock
          }
        } catch {
          // ignore SKU lookup error and use product baseline
        }
      }

      items.value = [
        {
          id: `buynow-${pid}-${sid || 0}`,
          productId: pid,
          skuId: sid,
          name: product.name,
          imageUrl,
          price,
          quantity: qty,
          skuSp,
          stock,
        },
      ]
    } else {
      // 购物车多商品结算模式
      const cartData = await apiCartList()
      const checkedRows = (cartData.items || []).filter((i) => i.checked === 1)
      items.value = checkedRows.map((r) => ({
        id: r.cartItemId,
        productId: r.productId,
        skuId: r.skuId,
        name: r.name,
        imageUrl: r.imageUrl,
        price: r.price,
        quantity: r.quantity,
        skuSp: r.skuSp,
        stock: r.stock,
      }))
    }
  } catch (error: any) {
    ElMessage.error(error?.message || '加载结算商品信息失败')
  } finally {
    loading.value = false
  }
}

async function submitOrder() {
  if (!selectedAddressId.value) {
    ElMessage.warning('请先选择或新增收货地址')
    showAddressModal.value = true
    return
  }
  if (items.value.length === 0) {
    ElMessage.warning('暂无可结算的商品')
    return
  }

  submitting.value = true
  try {
    let orderId: number
    let orderNo: string

    if (isBuyNow.value) {
      const item = items.value[0]
      const res = await apiCreateOrder({
        productId: item.productId,
        skuId: item.skuId,
        quantity: item.quantity,
        addressId: selectedAddressId.value,
        couponUserId: selectedCouponId.value,
        receiverAddress: orderRemarks.value.trim() ? `[备注: ${orderRemarks.value.trim()}]` : undefined,
      })
      orderId = res.orderId
      orderNo = res.orderNo
    } else {
      const res = await apiCartCheckout({
        addressId: selectedAddressId.value,
        couponUserId: selectedCouponId.value,
        receiverAddress: orderRemarks.value.trim() ? `[备注: ${orderRemarks.value.trim()}]` : undefined,
      })
      orderId = res.orderId
      orderNo = res.orderNo
      // 同步购物车状态徽标
      void cartStore.fetchCart()
    }

    // 自动模拟支付
    await apiPayOrder(orderId)
    ElMessage.success(`下单并模拟支付成功：${orderNo}`)
    router.push(`/orders/${orderId}`)
  } catch (error: any) {
    // 错误信息已由 Axios 拦截器提示
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  void loadData()
})

watch(
  () => [route.query.productId, route.query.skuId, route.query.quantity],
  () => {
    if (route.path === '/order/confirm') {
      void loadData()
    }
  },
)
</script>

<style scoped>
.order-confirm-container {
  min-height: 100vh;
  background: var(--mall-page-bg, #f4f5f7);
  padding-bottom: calc(88px + env(safe-area-inset-bottom));
}

html.dark .order-confirm-container {
  background: #09090b;
}

/* 顶部全宽吸顶导航条 */
.confirm-topbar {
  position: sticky;
  top: 0;
  z-index: 50;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--mall-border-light, #e4e4e7);
}

html.dark .confirm-topbar {
  background: rgba(18, 18, 21, 0.95);
  border-bottom-color: var(--mall-border, #27272a);
}

.topbar-inner {
  max-width: 760px;
  margin: 0 auto;
  height: 48px;
  padding: 0 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.topbar-back-btn {
  border: none;
  background: transparent;
  width: 36px;
  height: 36px;
  border-radius: 9999px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: inherit;
  transition: background-color 0.15s;
}

.topbar-back-btn:hover {
  background: var(--mall-surface-2, #f4f4f5);
}

.topbar-title {
  font-size: 16px;
  font-weight: 700;
  margin: 0;
  color: inherit;
}

.topbar-safe-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  color: #10b981;
  background: #ecfdf5;
  padding: 3px 8px;
  border-radius: 9999px;
}

html.dark .topbar-safe-tag {
  background: rgba(16, 185, 129, 0.15);
}

/* 页面内容区 */
.confirm-main {
  max-width: 760px;
  margin: 12px auto 0;
  padding: 0 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 通用卡片容器 */
.confirm-card {
  background: var(--mall-surface, #ffffff);
  border-radius: 12px;
  border: 1px solid var(--mall-border-light, #f0f0f2);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
  overflow: hidden;
}

html.dark .confirm-card {
  background: #18181b;
  border-color: #27272a;
}

/* ================= 1. 地址卡片 (淘宝/京东/拼多多经典信封彩条) ================= */
.address-card {
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}

.address-card:hover {
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.06);
}

.envelope-stripe {
  height: 4px;
  background: repeating-linear-gradient(
    -45deg,
    #ef4444 0,
    #ef4444 14px,
    transparent 14px,
    transparent 20px,
    #3b82f6 20px,
    #3b82f6 34px,
    transparent 34px,
    transparent 40px
  );
}

.address-card-body {
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.addr-icon-box {
  width: 36px;
  height: 36px;
  border-radius: 9999px;
  background: #fef2f2;
  color: #ef4444;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

html.dark .addr-icon-box {
  background: rgba(239, 68, 68, 0.18);
}

.addr-content {
  flex: 1;
  min-width: 0;
}

.addr-user-line {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.addr-user-name {
  font-size: 15px;
  font-weight: 700;
  color: inherit;
}

.addr-user-phone {
  font-size: 13px;
  color: var(--el-text-color-secondary, #71717a);
  font-weight: 500;
}

.addr-badge-default {
  font-size: 10px;
  color: #10b981;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
}

.addr-full-text {
  font-size: 13px;
  color: var(--el-text-color-regular, #52525b);
  margin-top: 5px;
  line-height: 1.5;
}

html.dark .addr-full-text {
  color: #a1a1aa;
}

.addr-empty-content {
  flex: 1;
}

.addr-empty-title {
  font-size: 15px;
  font-weight: 700;
  color: #ef4444;
}

.addr-empty-sub {
  font-size: 12px;
  color: var(--el-text-color-secondary, #71717a);
  margin-top: 3px;
}

.addr-arrow {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--el-text-color-secondary, #a1a1aa);
  font-size: 12px;
  flex-shrink: 0;
}

.addr-action-text {
  font-size: 12px;
}

/* ================= 2. 店铺与商品卡片 ================= */
.store-card {
  padding: 14px 16px;
}

.store-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--mall-border-light, #f4f4f5);
}

html.dark .store-header {
  border-bottom-color: #27272a;
}

.sh-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.store-icon {
  color: #ef4444;
}

.store-name {
  font-size: 14px;
  font-weight: 700;
  color: inherit;
}

.store-tag-self {
  font-size: 10px;
  font-weight: 700;
  background: #e11d48;
  color: #ffffff;
  padding: 1px 6px;
  border-radius: 4px;
}

.store-shipping-badge {
  font-size: 11px;
  color: #0284c7;
  background: #f0f9ff;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
}

html.dark .store-shipping-badge {
  background: rgba(2, 132, 199, 0.16);
}

.goods-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 14px 0;
}

.goods-row {
  display: flex;
  gap: 12px;
}

.goods-img {
  width: 76px;
  height: 76px;
  border-radius: 8px;
  border: 1px solid var(--mall-border-light, #f4f4f5);
  background: var(--mall-surface-2, #f4f4f5);
  flex-shrink: 0;
}

.goods-img-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.goods-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.goods-title {
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
  color: inherit;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.goods-spec-badge {
  margin-top: 4px;
}

.goods-spec-badge span {
  display: inline-block;
  font-size: 11px;
  color: #71717a;
  background: var(--mall-surface-2, #f4f4f5);
  padding: 2px 6px;
  border-radius: 4px;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

html.dark .goods-spec-badge span {
  background: #27272a;
  color: #a1a1aa;
}

.goods-price-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
}

.goods-price {
  color: var(--mall-price, #e11d48);
  font-weight: 700;
}

.goods-price .currency {
  font-size: 11px;
}

.goods-price .price-val {
  font-size: 16px;
}

.goods-qty {
  font-size: 12px;
  color: var(--el-text-color-secondary, #71717a);
  font-weight: 600;
}

.goods-stepper {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--mall-border, #e4e4e7);
  border-radius: 6px;
  overflow: hidden;
  background: var(--mall-surface, #ffffff);
}

html.dark .goods-stepper {
  border-color: #3f3f46;
  background: #18181b;
}

.step-btn {
  width: 26px;
  height: 26px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  color: inherit;
  display: flex;
  align-items: center;
  justify-content: center;
}

.step-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.step-num {
  width: 28px;
  text-align: center;
  font-size: 12px;
  font-weight: 600;
}

/* 履约提示条 (用户原图绿色文字) */
.fulfillment-pledge {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 11px;
  color: #15803d;
  margin-top: 6px;
}

html.dark .fulfillment-pledge {
  background: rgba(22, 163, 74, 0.12);
  border-color: rgba(22, 163, 74, 0.3);
  color: #86efac;
}

.fp-badge {
  font-weight: 700;
  flex-shrink: 0;
  border: 1px solid #16a34a;
  border-radius: 3px;
  padding: 0 4px;
}

.fp-text {
  flex: 1;
  line-height: 1.4;
}

/* 增值服务 */
.service-guarantees {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--mall-border-light, #f4f4f5);
  font-size: 11px;
  color: var(--el-text-color-secondary, #71717a);
}

html.dark .service-guarantees {
  border-bottom-color: #27272a;
}

.sg-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.sg-item .el-icon {
  color: #10b981;
}

/* 拓展行 */
.order-ext-rows {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 10px;
}

.ext-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
}

.ext-label {
  color: var(--el-text-color-regular, #52525b);
  min-width: 64px;
}

.ext-value {
  color: inherit;
  font-weight: 500;
}

.ext-value.highlight {
  color: #059669;
}

.remark-row {
  gap: 8px;
}

.remark-input {
  flex: 1;
  border: 1px solid var(--mall-border, #e4e4e7);
  background: var(--mall-surface-2, #f4f4f5);
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 12px;
  color: inherit;
  outline: none;
  transition: border-color 0.15s;
}

.remark-input:focus {
  border-color: #18181b;
  background: var(--mall-surface, #ffffff);
}

html.dark .remark-input:focus {
  border-color: #ffffff;
  background: #18181b;
}

/* ================= 3. 优惠券卡片 ================= */
.coupon-card,
.payment-card,
.bill-card {
  padding: 14px 16px;
}

.card-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.ctr-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.card-icon {
  font-size: 16px;
}

.card-title {
  font-size: 14px;
  font-weight: 700;
  color: inherit;
}

.coupon-saved-tag {
  font-size: 11px;
  color: #e11d48;
  background: #ffe4e6;
  padding: 2px 8px;
  border-radius: 9999px;
  font-weight: 600;
}

/* ================= 4. 支付方式卡片 ================= */
.payment-badge {
  font-size: 11px;
  color: #059669;
  background: #ecfdf5;
  padding: 2px 8px;
  border-radius: 9999px;
  font-weight: 600;
}

.payment-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary, #71717a);
  line-height: 1.5;
}

/* ================= 5. 费用账单明细 ================= */
.bill-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bill-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: var(--el-text-color-regular, #52525b);
}

html.dark .bill-row {
  color: #a1a1aa;
}

.bill-val {
  font-weight: 500;
  color: inherit;
}

.free-text {
  color: #059669;
  font-weight: 600;
}

.discount-row .bill-label,
.discount-row .bill-val {
  color: #e11d48;
  font-weight: 600;
}

.bill-divider {
  height: 1px;
  background: var(--mall-border-light, #f4f4f5);
  margin: 4px 0;
}

html.dark .bill-divider {
  background: #27272a;
}

.total-row {
  margin-top: 2px;
}

.total-label {
  font-size: 14px;
  font-weight: 700;
  color: inherit;
}

.total-price {
  font-size: 20px;
  font-weight: 800;
  color: var(--mall-price, #e11d48);
}

.total-price .currency {
  font-style: normal;
  font-size: 13px;
  font-weight: 700;
}

/* 安全免责提示卡片 */
.safe-note-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--mall-surface-2, #f4f4f5);
  border-radius: 8px;
  font-size: 11px;
  color: var(--el-text-color-secondary, #71717a);
  line-height: 1.5;
}

html.dark .safe-note-card {
  background: #18181b;
  color: #a1a1aa;
}

.sn-icon {
  font-size: 16px;
  flex-shrink: 0;
}

/* 空状态 */
.empty-state-card {
  max-width: 600px;
  margin: 60px auto;
  padding: 40px 20px;
  background: var(--mall-surface, #ffffff);
  border-radius: 12px;
  text-align: center;
}

html.dark .empty-state-card {
  background: #18181b;
}

/* ================= 6. 底部固定吸底提交栏 (拼多多/京东/淘宝经典吸底规范) ================= */
.confirm-bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 90;
  background: rgba(255, 255, 255, 0.98);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-top: 1px solid var(--mall-border-light, #f4f4f5);
  box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.05);
}

html.dark .confirm-bottom-bar {
  background: rgba(18, 18, 21, 0.98);
  border-top-color: var(--mall-border, #27272a);
}

.bottom-bar-inner {
  max-width: 760px;
  margin: 0 auto;
  padding: 8px 14px calc(8px + env(safe-area-inset-bottom));
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.bbar-left {
  display: flex;
  flex-direction: column;
}

.bbar-summary {
  display: flex;
  align-items: baseline;
}

.bbar-count {
  font-size: 12px;
  color: var(--el-text-color-secondary, #71717a);
}

.bbar-label {
  font-size: 13px;
  font-weight: 600;
  color: inherit;
}

.bbar-price {
  font-size: 24px;
  font-weight: 800;
  color: var(--mall-price, #e11d48);
  margin-left: 2px;
}

.bbar-currency {
  font-style: normal;
  font-size: 13px;
  font-weight: 700;
}

.bbar-savings {
  font-size: 11px;
  color: #e11d48;
}

.bbar-right {
  display: flex;
  align-items: center;
}

.submit-order-btn {
  height: 42px;
  padding: 0 28px;
  border-radius: 9999px;
  border: none;
  background: linear-gradient(135deg, #e11d48 0%, #f43f5e 100%);
  color: #ffffff;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(225, 29, 72, 0.35);
  transition: transform 0.15s, opacity 0.15s;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.submit-order-btn:hover:not(:disabled) {
  opacity: 0.95;
  transform: translateY(-1px);
}

.submit-order-btn:active:not(:disabled) {
  transform: scale(0.97);
}

.submit-order-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  box-shadow: none;
}

.submitting-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid #ffffff;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.address-modal-content {
  max-height: 480px;
  overflow-y: auto;
}
</style>
