<template>
  <div class="product-card mall-card" @click="$router.push(`/products/${product.id}`)">
    <div class="pic-wrap">
      <el-image :src="product.imageUrl" fit="cover" class="pic" lazy decoding="async">
        <template #placeholder>
          <div class="pic-fallback">{{ product.name.slice(0, 1) }}</div>
        </template>
        <template #error>
          <div class="pic-fallback">{{ product.name.slice(0, 1) }}</div>
        </template>
      </el-image>
      <span v-if="hot" class="hot-tag">🔥 热卖</span>
    </div>
    <div class="name">{{ product.name }}</div>
    <div class="points">{{ product.sellingPoints }}</div>
    <div class="row">
      <span class="price"><i>￥</i>{{ product.price }}</span>
      <span class="meta">已售 {{ product.sales || 0 }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ProductVO } from '@/types/api'

const props = defineProps<{ product: ProductVO }>()

/** 销量门槛热卖标签 */
const hot = computed(() => (props.product.sales || 0) >= 5000)
</script>

<style scoped>
.product-card {
  min-width: 0;
  padding: 10px;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.product-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--mall-shadow-hover);
}

.pic-wrap {
  position: relative;
  border-radius: 10px;
  overflow: hidden;
}

.pic {
  width: 100%;
  aspect-ratio: 1;
  background: var(--mall-surface-2, #f5f7fa);
  transition: transform 0.3s ease;
}

.product-card:hover .pic :deep(img) {
  transform: scale(1.04);
}

.hot-tag {
  position: absolute;
  top: 8px;
  left: 8px;
  background: var(--mall-gradient);
  color: #fff;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

.pic-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  font-weight: 700;
  color: var(--el-text-color-placeholder, #c0c4cc);
  background: linear-gradient(135deg, #e8f0fe, #f5f7fa);
}

.name {
  font-weight: 600;
  margin-top: 8px;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.points {
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
  height: 32px;
  margin-top: 4px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.row {
  flex-wrap: wrap;
  gap: 4px;
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-top: 6px;
}

.price {
  color: var(--el-color-danger);
  font-weight: 700;
  font-size: 20px;
  line-height: 1;
}

.price i {
  font-style: normal;
  font-size: 13px;
  margin-right: 1px;
}

.meta {
  font-size: 12px;
  color: var(--el-text-color-placeholder, #c0c4cc);
}

/* 手机端紧凑卡片 */
@media (max-width: 768px) {
  .product-card {
    padding: 7px;
  }

  .name {
    font-size: 13px;
  }

  .points {
    display: none; /* 手机端收起卖点，卡片更聚焦价格 */
  }

  .price {
    font-size: 17px;
  }
}
</style>
