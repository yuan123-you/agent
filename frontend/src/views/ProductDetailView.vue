<template>
  <div v-if="product" class="page detail">
    <div class="main">
      <el-image :src="product.imageUrl" fit="cover" class="pic" :preview-src-list="[product.imageUrl]">
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
        <div class="price">￥{{ product.price }}</div>
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
          <el-input-number v-model="quantity" :min="1" :max="Math.min(99, product.stock)" />
          <span class="stock">库存 {{ product.stock }} {{ product.stock === 0 ? '（暂时缺货）' : '' }}</span>
        </div>
        <div class="btn-row">
          <el-button size="large" class="act-btn" :disabled="product.stock === 0" @click="addToCart">
            加入购物车
          </el-button>
          <el-button type="danger" size="large" class="act-btn" :disabled="product.stock === 0"
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
      <template #header>规格参数</template>
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
      <div
        v-infinite-scroll="loadReviews"
        :infinite-scroll-disabled="reviewLoading || reviewFinished"
        :infinite-scroll-distance="30"
      >
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

    <!-- 收货信息 + 下单弹窗 -->
    <el-dialog v-model="showBuy" title="确认订单（模拟支付）" width="440px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="商品">
          <span>{{ product.name }} × {{ quantity }}</span>
        </el-form-item>
        <el-form-item label="合计">
          <span class="total">￥{{ totalAmount }}</span>
        </el-form-item>
        <el-form-item label="收货人">
          <el-input v-model="form.receiverName" placeholder="收货人姓名" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.receiverPhone" placeholder="手机号" />
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="form.receiverAddress" type="textarea" :rows="2" placeholder="收货地址" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBuy = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitOrder">提交订单</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Star } from '@element-plus/icons-vue'
import {
  apiCartAdd, apiCreateOrder, apiFavoriteStatus, apiFavoriteToggle, apiHistoryRecord,
  apiProductDetail, apiReviewCreate, apiReviews, type ReviewVO,
} from '@/api'
import { renderMarkdown } from '@/components/mall/link'
import { categoryName } from '@/constants/categories'
import type { ProductVO } from '@/types/api'

const route = useRoute()
const router = useRouter()

const product = ref<ProductVO | null>(null)
const quantity = ref(1)
const favorited = ref(false)
const showBuy = ref(false)
const submitting = ref(false)
const form = reactive({
  receiverName: '', receiverPhone: '', receiverAddress: '',
})

// 评论
const reviews = ref<ReviewVO[]>([])
const reviewLoading = ref(false)
const reviewFinished = ref(false)
const reviewPage = ref(1)
const reviewTotal = ref(0)
const avgRating = ref(5)
const myRating = ref(5)
const myContent = ref('')

const isMobile = ref(window.innerWidth <= 768)
const points = computed(() => (product.value?.sellingPoints || '').split(/\s+/).filter(Boolean))
const specs = computed(() => {
  try {
    const obj = JSON.parse(product.value?.specs || '{}')
    return Object.entries(obj).map(([k, v]) => ({ k, v: String(v) }))
  } catch {
    return []
  }
})
const totalAmount = computed(() => ((product.value?.price || 0) * quantity.value).toFixed(2))
const descHtml = computed(() => renderMarkdown(product.value?.description || '暂无介绍'))

onMounted(async () => {
  const id = Number(route.params.id)
  try {
    product.value = await apiProductDetail(id)
  } catch {
    router.replace('/404')
    return
  }
  // 收藏状态 + 浏览历史上报（失败不影响页面）
  apiFavoriteStatus(id).then((s) => (favorited.value = s.favorited)).catch(() => {})
  apiHistoryRecord(id).catch(() => {})
  loadReviews()
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
  await apiCartAdd(product.value!.id, quantity.value)
  ElMessage.success('已加入购物车')
}

async function toggleFavorite() {
  const res = await apiFavoriteToggle(product.value!.id)
  favorited.value = res.favorited
  ElMessage.success(res.favorited ? '已收藏' : '已取消收藏')
}

function buyNow() {
  showBuy.value = true
}

async function submitOrder() {
  if (!form.receiverName || !form.receiverPhone || !form.receiverAddress) {
    ElMessage.warning('请完整填写收货信息')
    return
  }
  submitting.value = true
  try {
    const order = await apiCreateOrder({
      productId: product.value!.id,
      quantity: quantity.value,
      receiverName: form.receiverName,
      receiverPhone: form.receiverPhone,
      receiverAddress: form.receiverAddress,
    })
    ElMessage.success(`下单成功：${order.orderNo}`)
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
.detail {
  height: 100%;
  overflow-y: auto;
  box-sizing: border-box;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  padding: 16px;
}

.main {
  display: flex;
  gap: 24px;
  background: #fff;
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
  color: #c0c4cc;
  background: linear-gradient(135deg, #e8f0fe, #f5f7fa);
}

.info {
  flex: 1;
  min-width: 0;
}

.name {
  margin: 0 0 8px;
}

.sub-row {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #909399;
  font-size: 13px;
}

.price {
  color: var(--el-color-danger);
  font-size: 30px;
  font-weight: 700;
  margin: 14px 0;
}

.point-tag {
  margin: 0 8px 6px 0;
}

.service-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  padding: 10px 0;
  border-top: 1px dashed #ebeef5;
  border-bottom: 1px dashed #ebeef5;
  color: #606266;
  font-size: 13px;
}

.qty-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 16px 0;
}

.qty-label {
  color: #909399;
  font-size: 14px;
}

.stock {
  font-size: 13px;
  color: #909399;
}

.btn-row {
  display: flex;
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
  color: #c0c4cc;
}

.r-content {
  margin: 8px 0 0 36px;
  line-height: 1.6;
}

.r-spec {
  margin: 4px 0 0 36px;
  font-size: 12px;
  color: #909399;
}

.r-reply {
  margin: 8px 0 0 36px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 6px;
  font-size: 13px;
}

.review-form {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
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
  color: #909399;
  font-size: 13px;
  padding: 12px 0;
}

.total {
  color: var(--el-color-danger);
  font-size: 18px;
  font-weight: 700;
}

@media (max-width: 768px) {
  .detail {
    padding: 10px;
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
}
</style>
