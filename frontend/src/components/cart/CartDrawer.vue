<template>
  <el-drawer
    v-model="cart.isDrawerOpen"
    :size="drawerSize"
    :with-header="false"
    class="cart-drawer-custom"
    direction="rtl"
    append-to-body
  >
    <div class="cart-drawer-inner">
      <!-- 头部 -->
      <div class="drawer-header">
        <div class="header-title">
          <el-icon :size="20"><ShoppingCart /></el-icon>
          <span>我的购物车 ({{ cart.cartCount }})</span>
        </div>
        <button class="close-btn" @click="cart.closeDrawer">
          <el-icon :size="18"><Close /></el-icon>
        </button>
      </div>

      <!-- 包邮进度提示 -->
      <div class="shipping-banner">
        <div class="banner-top">
          <span class="shipping-tag">{{ freeShippingDiff <= 0 ? '已包邮' : '免运费福利' }}</span>
          <span class="shipping-text">
            {{ freeShippingDiff <= 0 ? '✨ 恭喜！订单已享全场免运费服务' : `还差 ￥${freeShippingDiff.toFixed(2)} 即可享受免运费` }}
          </span>
        </div>
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: shippingProgress + '%' }" />
        </div>
      </div>

      <!-- 商品列表 -->
      <div class="drawer-body">
        <div v-if="cart.items.length > 0" class="cart-items-list">
          <div v-for="item in cart.items" :key="item.cartItemId" class="drawer-cart-item">
            <el-image :src="item.imageUrl" fit="cover" class="item-img" @click="goProduct(item.productId)">
              <template #error>
                <div class="img-fallback">{{ item.name.slice(0, 1) }}</div>
              </template>
            </el-image>

            <div class="item-details">
              <div class="item-name" :title="item.name" @click="goProduct(item.productId)">
                {{ item.name }}
              </div>
              <div v-if="item.skuSp" class="item-sku">{{ item.skuSp }}</div>

              <div class="item-price-row">
                <span class="item-price"><i>￥</i>{{ item.price }}</span>

                <div class="qty-stepper">
                  <button
                    class="stepper-btn"
                    :disabled="item.quantity <= 1"
                    @click="cart.updateQuantity(item, item.quantity - 1)"
                  >
                    -
                  </button>
                  <span class="stepper-val">{{ item.quantity }}</span>
                  <button
                    class="stepper-btn"
                    :disabled="item.quantity >= (item.stock || 99)"
                    @click="cart.updateQuantity(item, item.quantity + 1)"
                  >
                    +
                  </button>
                </div>

                <button class="remove-btn" title="删除" @click="cart.removeItem(item.cartItemId)">
                  <el-icon><Delete /></el-icon>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 空态 -->
        <div v-else class="drawer-empty">
          <div class="empty-emoji">🛍️</div>
          <div class="empty-title">购物车空空如也</div>
          <p class="empty-sub">精选新品与限时特惠正在火热开抢</p>
          <el-button type="primary" round class="explore-btn" @click="goShopping">
            立即去逛逛
          </el-button>
        </div>
      </div>

      <!-- 底部结账区 -->
      <div v-if="cart.items.length > 0" class="drawer-footer">
        <div class="summary-row">
          <span class="summary-label">小计金额</span>
          <span class="summary-val">￥{{ cart.totalAmount }}</span>
        </div>
        <div class="summary-row sub-row">
          <span class="summary-label">预估运费</span>
          <span class="summary-val">{{ freeShippingDiff <= 0 ? '免费' : '￥10.00' }}</span>
        </div>

        <div class="footer-btns">
          <button class="view-cart-btn" @click="goFullCart">
            查看购物车
          </button>
          <button class="checkout-btn" @click="goCheckout">
            <span>立即结算</span>
            <el-icon><ArrowRight /></el-icon>
          </button>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ShoppingCart, Close, Delete, ArrowRight } from '@element-plus/icons-vue'
import { useCartStore } from '@/stores/cart'

const router = useRouter()
const cart = useCartStore()

const windowWidth = ref(window.innerWidth)
const onResize = () => (windowWidth.value = window.innerWidth)
onMounted(() => window.addEventListener('resize', onResize))

const drawerSize = computed(() => (windowWidth.value <= 768 ? '100%' : '420px'))

const FREE_SHIPPING_THRESHOLD = 99
const freeShippingDiff = computed(() => Math.max(0, FREE_SHIPPING_THRESHOLD - cart.totalAmount))
const shippingProgress = computed(() => {
  return Math.min(100, Math.round((cart.totalAmount / FREE_SHIPPING_THRESHOLD) * 100))
})

function goProduct(id: number) {
  cart.closeDrawer()
  router.push(`/products/${id}`)
}

function goShopping() {
  cart.closeDrawer()
  router.push('/products')
}

function goFullCart() {
  cart.closeDrawer()
  router.push('/cart')
}

function goCheckout() {
  cart.closeDrawer()
  router.push('/order/confirm')
}
</script>

<style scoped>
.cart-drawer-inner {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--mall-surface, #ffffff);
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px;
  border-bottom: 1px solid var(--mall-border-light, #f1f5f9);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

html.dark .header-title {
  color: #f8fafc;
}

.close-btn {
  border: none;
  background: transparent;
  cursor: pointer;
  color: #94a3b8;
  padding: 4px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}

.close-btn:hover {
  background: var(--mall-surface-2, #f1f5f9);
  color: #0f172a;
}

/* 包邮横幅 */
.shipping-banner {
  background: var(--mall-surface-2, #f8fafc);
  border-bottom: 1px solid var(--mall-border-light, #f1f5f9);
  padding: 12px 20px;
}

.banner-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.shipping-tag {
  font-size: 10px;
  font-weight: 700;
  color: #059669;
  background: #d1fae5;
  padding: 2px 6px;
  border-radius: 4px;
}

.shipping-text {
  font-size: 12px;
  color: #475569;
}

html.dark .shipping-text {
  color: #cbd5e1;
}

.progress-track {
  height: 4px;
  background: #e2e8f0;
  border-radius: 9999px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #10b981, #059669);
  border-radius: 9999px;
  transition: width 0.3s ease;
}

/* 列表区 */
.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.cart-items-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.drawer-cart-item {
  display: flex;
  gap: 12px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--mall-border-light, #f1f5f9);
}

.item-img {
  width: 72px;
  height: 72px;
  border-radius: 8px;
  flex-shrink: 0;
  cursor: pointer;
  background: var(--mall-surface-2, #f1f5f9);
}

.img-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  color: #94a3b8;
}

.item-details {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.item-name {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
}

html.dark .item-name {
  color: #f1f5f9;
}

.item-sku {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}

.item-price-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
}

.item-price {
  font-size: 15px;
  font-weight: 700;
  color: var(--mall-price, #e11d48);
}

.item-price i {
  font-style: normal;
  font-size: 11px;
}

.qty-stepper {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--mall-border, #e2e8f0);
  border-radius: 6px;
  background: var(--mall-surface-2, #f8fafc);
  overflow: hidden;
}

.stepper-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stepper-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.stepper-val {
  width: 28px;
  text-align: center;
  font-size: 12px;
  font-weight: 600;
}

.remove-btn {
  border: none;
  background: transparent;
  cursor: pointer;
  color: #94a3b8;
  padding: 4px;
  font-size: 14px;
  transition: color 0.15s ease;
}

.remove-btn:hover {
  color: #e11d48;
}

/* 空态 */
.drawer-empty {
  text-align: center;
  padding: 60px 0;
}

.empty-emoji {
  font-size: 48px;
  margin-bottom: 12px;
}

.empty-title {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

html.dark .empty-title {
  color: #f8fafc;
}

.empty-sub {
  font-size: 12px;
  color: #94a3b8;
  margin: 6px 0 20px;
}

.explore-btn {
  padding: 8px 24px;
  font-size: 13px;
}

/* 底部结算 */
.drawer-footer {
  padding: 16px 20px;
  border-top: 1px solid var(--mall-border-light, #f1f5f9);
  background: var(--mall-surface, #ffffff);
}

.summary-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  margin-bottom: 6px;
}

.summary-label {
  color: #64748b;
}

.summary-val {
  font-weight: 700;
  font-size: 18px;
  color: var(--mall-price, #e11d48);
}

.summary-row.sub-row {
  font-size: 12px;
  margin-bottom: 16px;
}

.summary-row.sub-row .summary-val {
  font-size: 12px;
  font-weight: 500;
  color: #059669;
}

.footer-btns {
  display: grid;
  grid-template-columns: 1fr 1.3fr;
  gap: 10px;
}

.view-cart-btn {
  border: 1px solid var(--mall-border, #e2e8f0);
  background: var(--mall-surface-2, #f8fafc);
  color: #0f172a;
  border-radius: 9999px;
  padding: 10px 0;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

html.dark .view-cart-btn {
  color: #f1f5f9;
}

.view-cart-btn:hover {
  border-color: #0f172a;
}

.checkout-btn {
  border: none;
  background: var(--el-color-primary, #2563eb);
  color: #ffffff;
  border-radius: 9999px;
  padding: 10px 0;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.3);
  transition: all 0.15s ease;
}

.checkout-btn:hover {
  background: #1d4ed8;
}
</style>

