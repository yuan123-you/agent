<template>
  <el-scrollbar class="page-scroll" :distance="60" @end-reached="direction => direction === 'bottom' && loadMore()">
    <div class="page">
    <h3 class="page-title">商品评论（{{ total }}）</h3>

    <div class="list">
      <el-card v-for="r in reviews" :key="r.id" shadow="never" class="review-card">
        <div class="r-head">
          <el-rate :model-value="r.rating" disabled size="small" />
          <span class="r-time">{{ shortTime(r.createdAt) }}</span>
          <el-button size="small" text type="primary" @click="$router.push(`/products/${r.productId}`)">
            查看商品
          </el-button>
        </div>
        <div class="r-content">{{ r.content }}</div>
        <div v-if="r.specInfo" class="r-spec">规格：{{ r.specInfo }}</div>
        <div v-if="r.merchantReply" class="r-reply">
          <b>我的回复：</b>{{ r.merchantReply }}
        </div>
        <div v-else class="r-actions">
          <el-input v-model="replyDrafts[r.id]" placeholder="回复买家..." size="small" style="flex: 1" />
          <el-button size="small" type="primary" :disabled="!replyDrafts[r.id]?.trim()"
            @click="reply(r)">回复</el-button>
        </div>
      </el-card>
      <el-empty v-if="!loading && reviews.length === 0" description="暂无评论" />
    </div>

    <div v-if="loading" class="load-state">加载中...</div>
    <div v-else-if="finished && reviews.length > 0" class="load-state">— 没有更多了 —</div>
    </div>
  </el-scrollbar>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiMerchantReply, apiMerchantReviews } from '@/api'

interface MerchantReview {
  id: number; productId: number; rating: number; content: string
  specInfo?: string; merchantReply?: string; createdAt: string
}

const reviews = ref<MerchantReview[]>([])
const loading = ref(false)
const finished = ref(false)
const page = ref(1)
const total = ref(0)
const replyDrafts = reactive<Record<number, string>>({})

async function load() {
  if (loading.value || finished.value) return
  loading.value = true
  try {
    const result = await apiMerchantReviews({ page: page.value, size: 20 })
    reviews.value.push(...(result.records as MerchantReview[]))
    total.value = result.total
    if (result.records.length === 0 || reviews.value.length >= result.total) {
      finished.value = true
    } else {
      page.value++
    }
  } finally {
    loading.value = false
  }
}

function loadMore() {
  load()
}

async function reply(r: MerchantReview) {
  const content = (replyDrafts[r.id] || '').trim()
  if (!content) return
  await apiMerchantReply(r.id, content)
  r.merchantReply = content
  delete replyDrafts[r.id]
  ElMessage.success('回复成功')
}

function shortTime(t?: string): string {
  return (t || '').replace('T', ' ').slice(0, 16)
}

onMounted(load)
</script>

<style scoped>
.page-scroll { height: 100%; }
.page {
  min-height: 100%;
  box-sizing: border-box;
  max-width: 860px;
}

.page-title {
  margin: 0 0 14px;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.r-head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.r-time {
  font-size: 12px;
  color: #c0c4cc;
  margin-left: auto;
}

.r-content {
  margin-top: 8px;
  line-height: 1.6;
}

.r-spec {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.r-reply {
  margin-top: 10px;
  padding: 8px 12px;
  background: #f0f9eb;
  border-radius: 6px;
  font-size: 13px;
}

.r-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.load-state {
  text-align: center;
  color: #909399;
  font-size: 13px;
  padding: 18px 0 24px;
}
</style>
