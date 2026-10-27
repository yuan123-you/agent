<template>
  <el-dialog
    v-model="visible"
    :width="dialogWidth"
    :show-close="true"
    class="quickview-dialog"
    destroy-on-close
    append-to-body
  >
    <LoadingState v-if="loading" variant="detail" label="正在加载商品预览" />
    <div v-else-if="product" class="quickview-body">
      <!-- 左侧大图 -->
      <div class="qv-left">
        <el-image :src="currentImage || product.imageUrl" fit="cover" class="qv-main-img">
          <template #error>
            <div class="qv-img-fallback">{{ product.name.slice(0, 1) }}</div>
          </template>
        </el-image>
      </div>

      <!-- 右侧信息 -->
      <div class="qv-right">
        <div class="qv-header">
          <div class="qv-tags">
            <span v-if="product.brand" class="qv-brand-tag">{{ product.brand }}</span>
            <span class="qv-cat-tag">{{ categoryName(product.category) }}</span>
          </div>
          <h3 class="qv-title">{{ product.name }}</h3>
          <p v-if="product.sellingPoints" class="qv-desc">{{ product.sellingPoints }}</p>
        </div>

        <div class="qv-price-box">
          <span class="qv-price"><i>￥</i>{{ product.price }}</span>
          <span v-if="product.sales != null" class="qv-sales">已售 {{ product.sales }} 件</span>
        </div>

        <!-- 数量步进器 -->
        <div class="qv-quantity-row">
          <span class="qv-qty-label">选购数量</span>
          <div class="qty-stepper">
            <button class="step-btn" :disabled="quantity <= 1" @click="quantity--">-</button>
            <span class="step-val">{{ quantity }}</span>
            <button class="step-btn" :disabled="quantity >= stockLimit" @click="quantity++">+</button>
          </div>
          <span class="qv-stock-hint">{{ product.stock == null ? '库存待确认' : `库存 ${product.stock} 件` }}</span>
        </div>

        <!-- 操作按钮 -->
        <div class="qv-action-row">
          <button class="qv-add-btn" :disabled="adding || stockLimit < 1" :loading="adding" @click="handleAddToCart">
            <el-icon><ShoppingCart /></el-icon>
            <span>加入购物车</span>
          </button>
          <button class="qv-detail-btn" @click="goDetail">
            查看详情 ›
          </button>
        </div>

        <!-- 服务保障微条 -->
        <div class="qv-guarantee">
          <span>配送与售后请查看商品详情及适用政策</span>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import LoadingState from '@/components/common/LoadingState.vue'
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ShoppingCart } from '@element-plus/icons-vue'
import { categoryName } from '@/constants/categories'
import { useCartStore } from '@/stores/cart'
import type { ProductVO } from '@/types/api'

const router = useRouter()
const cart = useCartStore()

const visible = ref(false)
const loading = ref(false)
const adding = ref(false)
const product = ref<ProductVO | null>(null)
const currentImage = ref('')
const quantity = ref(1)

const windowWidth = ref(window.innerWidth)
const onResize = () => (windowWidth.value = window.innerWidth)
onMounted(() => window.addEventListener('resize', onResize))

const dialogWidth = computed(() => (windowWidth.value <= 768 ? '92%' : '780px'))
const stockLimit = computed(() => Math.min(99, Math.max(0, product.value?.stock ?? 0)))

function open(p: ProductVO) {
  product.value = p
  currentImage.value = p.imageUrl
  quantity.value = 1
  visible.value = true
}

async function handleAddToCart() {
  if (!product.value || adding.value || quantity.value < 1 || quantity.value > stockLimit.value) return
  adding.value = true
  try {
    const success = await cart.addToCart(product.value.id, quantity.value, 0, true)
    if (success) {
      visible.value = false
    }
  } finally {
    adding.value = false
  }
}

function goDetail() {
  if (!product.value) return
  visible.value = false
  router.push(`/products/${product.value.id}`)
}

defineExpose({
  open,
})
</script>

<style scoped>
.quickview-body {
  display: flex;
  gap: 28px;
  padding: 6px 4px;
}

.qv-left {
  width: 320px;
  flex-shrink: 0;
}

.qv-main-img {
  width: 100%;
  aspect-ratio: 1;
  border-radius: 12px;
  background: var(--mall-surface-2, #f1f5f9);
}

.qv-img-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 54px;
  font-weight: 700;
  color: #94a3b8;
}

.qv-right {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.qv-tags {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}

.qv-brand-tag {
  font-size: 11px;
  font-weight: 700;
  color: #0f172a;
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 4px;
}

html.dark .qv-brand-tag {
  color: #f1f5f9;
  background: #1e293b;
}

.qv-cat-tag {
  font-size: 11px;
  color: var(--el-color-primary, #2563eb);
  background: rgba(37, 99, 235, 0.08);
  padding: 2px 8px;
  border-radius: 4px;
}

.qv-title {
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 6px;
  line-height: 1.35;
  letter-spacing: -0.02em;
}

html.dark .qv-title {
  color: #f8fafc;
}

.qv-desc {
  font-size: 13px;
  color: #64748b;
  margin: 0 0 16px;
  line-height: 1.5;
}

.qv-price-box {
  display: flex;
  align-items: baseline;
  gap: 10px;
  background: var(--mall-surface-2, #f8fafc);
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 18px;
}

.qv-price {
  font-size: 24px;
  font-weight: 800;
  color: var(--mall-price, #e11d48);
}

.qv-price i {
  font-style: normal;
  font-size: 14px;
}

.qv-old-price {
  font-size: 13px;
  color: #94a3b8;
  text-decoration: line-through;
}

.qv-sales {
  font-size: 12px;
  color: #94a3b8;
  margin-left: auto;
}

.qv-quantity-row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 22px;
}

.qv-qty-label {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

html.dark .qv-qty-label {
  color: #cbd5e1;
}

.qty-stepper {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--mall-border, #e2e8f0);
  border-radius: 6px;
  overflow: hidden;
}

.step-btn {
  width: 30px;
  height: 30px;
  border: none;
  background: var(--mall-surface, #ffffff);
  cursor: pointer;
  font-weight: 600;
  color: #334155;
  display: flex;
  align-items: center;
  justify-content: center;
}

.step-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.step-val {
  width: 36px;
  text-align: center;
  font-size: 13px;
  font-weight: 600;
}

.qv-stock-hint {
  font-size: 12px;
  color: #94a3b8;
}

.qv-action-row {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.qv-add-btn {
  flex: 1.5;
  height: 42px;
  background: var(--el-color-primary, #2563eb);
  color: #ffffff;
  border: none;
  border-radius: 9999px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.15s ease;
}

.qv-add-btn:hover {
  background: #1d4ed8;
}

.qv-detail-btn {
  flex: 1;
  height: 42px;
  background: var(--mall-surface-2, #f1f5f9);
  color: #0f172a;
  border: 1px solid var(--mall-border, #e2e8f0);
  border-radius: 9999px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

html.dark .qv-detail-btn {
  color: #f1f5f9;
}

.qv-detail-btn:hover {
  border-color: #0f172a;
}

.qv-guarantee {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #64748b;
  padding-top: 12px;
  border-top: 1px solid var(--mall-border-light, #f1f5f9);
}

@media (max-width: 768px) {
  .quickview-body {
    flex-direction: column;
    gap: 16px;
  }
  .qv-left {
    width: 100%;
  }
}
</style>
