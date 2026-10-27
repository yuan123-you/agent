<template>
  <el-scrollbar class="page-scroll" :distance="60" @end-reached="direction => direction === 'bottom' && loadMore()">
    <div class="page">
    <div class="page-header-row">
        <button class="translucent-circle-back" title="返回" @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
        </button>
        <h3 class="page-title">我的收藏（{{ total }}）</h3>
      </div>
    <div class="grid">
      <div v-for="p in products" :key="p.id" class="fav-card" @click="$router.push(`/products/${p.id}`)">
        <el-image :src="p.imageUrl" fit="cover" class="pic" lazy decoding="async">
          <template #placeholder>
            <div class="pic-fb">{{ p.name.slice(0, 1) }}</div>
          </template>
          <template #error>
            <div class="pic-fb">{{ p.name.slice(0, 1) }}</div>
          </template>
        </el-image>
        <div class="name">{{ p.name }}</div>
        <div class="row">
          <span class="price">￥{{ p.price }}</span>
          <el-button text type="danger" size="small" @click.stop="unfavorite(p)">取消收藏</el-button>
        </div>
      </div>
    </div>
    <el-empty v-if="!loading && products.length === 0" :description="hasToken ? '暂无收藏商品，去逛逛吧' : '登录后查看我的收藏'">
      <el-button v-if="!hasToken" type="primary" @click="$router.push({ path: '/login', query: { redirect: '/favorites' } })">
        立即登录
      </el-button>
      <el-button v-else type="primary" @click="$router.push('/products')">
        去挑选商品
      </el-button>
    </el-empty>
    <LoadingState v-if="loading" variant="cards" :count="3" />
    <div v-else-if="finished && products.length > 0" class="load-state">— 没有更多了 —</div>
    </div>
  </el-scrollbar>
</template>

<script setup lang="ts">
import LoadingState from '@/components/common/LoadingState.vue'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { apiFavoriteToggle, apiFavorites } from '@/api'
import type { ProductVO } from '@/types/api'

type FavProduct = ProductVO & { time: string }

const router = useRouter()
function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/')
}

const products = ref<FavProduct[]>([])
const loading = ref(false)
const finished = ref(false)
const page = ref(1)
const total = ref(0)
const hasToken = ref(typeof localStorage !== 'undefined' ? !!localStorage.getItem('token') : false)

async function load() {
  if (loading.value || finished.value) return
  if (!localStorage.getItem('token')) {
    hasToken.value = false
    loading.value = false
    return
  }
  hasToken.value = true
  loading.value = true
  try {
    const result = await apiFavorites({ page: page.value, size: 20 })
    products.value.push(...(result.records as FavProduct[]))
    total.value = result.total
    if (result.records.length === 0 || products.value.length >= result.total) {
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

async function unfavorite(p: FavProduct) {
  await apiFavoriteToggle(p.id)
  ElMessage.success('已取消收藏')
  products.value = products.value.filter((x) => x.id !== p.id)
  total.value--
}

onMounted(load)
</script>

<style scoped>
.page-scroll { height: 100%; }
.page {
  min-height: 100%;
  box-sizing: border-box;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  padding: 16px;
}

.page-title {
  margin: 0 0 14px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.fav-card {
  min-width: 0;
  background: var(--mall-surface, #fff);
  border-radius: 8px;
  padding: 10px;
  cursor: pointer;
}

.pic {
  width: 100%;
  aspect-ratio: 1;
  border-radius: 6px;
}

.pic-fb {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--mall-surface-2, #f5f7fa);
  color: var(--el-text-color-placeholder, #c0c4cc);
  font-size: 36px;
  font-weight: 700;
}

.name {
  font-weight: 600;
  margin-top: 8px;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
}

.price {
  color: var(--el-color-danger);
  font-weight: 700;
  font-size: 17px;
}

.load-state {
  text-align: center;
  color: var(--el-text-color-secondary, #909399);
  font-size: 13px;
  padding: 18px 0 24px;
}

@media (max-width: 768px) {
  .page {
    padding: 10px;
  }

  .grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }
}
</style>


