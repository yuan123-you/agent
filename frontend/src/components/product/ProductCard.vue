<template>
  <div class="product-card" @click="goDetail">
    <div class="pic-wrap">
      <el-image :src="product.imageUrl" fit="cover" class="pic" decoding="async">
        <template #placeholder>
          <div class="pic-fallback">{{ product.name.slice(0, 1) }}</div>
        </template>
        <template #error>
          <div class="pic-fallback">{{ product.name.slice(0, 1) }}</div>
        </template>
      </el-image>
    </div>

    <div class="info-wrap">
      <div class="name-text" :title="product.name">{{ product.name }}</div>
      <div class="price-text">￥{{ product.price }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import type { ProductVO } from '@/types/api'

const props = defineProps<{
  product: ProductVO
  showPoints?: boolean
}>()

const router = useRouter()

function goDetail() {
  router.push(`/products/${props.product.id}`)
}
</script>

<style scoped>
.product-card {
  min-width: 0;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  transition: opacity 0.2s ease;
}

.product-card:hover {
  opacity: 0.85;
}

.pic-wrap {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  border-radius: 8px;
  overflow: hidden;
  background: var(--mall-surface-2, #f4f4f5);
}

.pic {
  width: 100%;
  height: 100%;
  transition: transform 0.5s cubic-bezier(0.16, 1, 0.3, 1);
}

.product-card:hover .pic :deep(img) {
  transform: scale(1.03);
}

.pic-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  font-weight: 600;
  color: #a1a1aa;
}

.info-wrap {
  padding-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.name-text {
  font-size: 14px;
  font-weight: 500;
  color: #18181b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  letter-spacing: -0.01em;
}

html.dark .name-text {
  color: #f4f4f5;
}

.price-text {
  font-size: 14px;
  font-weight: 600;
  color: #71717a;
  letter-spacing: -0.01em;
}

html.dark .price-text {
  color: #a1a1aa;
}

@media (max-width: 768px) {
  .name-text {
    font-size: 13px;
  }
  .price-text {
    font-size: 13px;
  }
}
</style>
