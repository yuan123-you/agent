<template>
  <div class="product-card" @click="$router.push(`/products/${product.id}`)">
    <el-image :src="product.imageUrl" fit="cover" class="pic">
      <template #error>
        <div class="pic-fallback">{{ product.name.slice(0, 1) }}</div>
      </template>
    </el-image>
    <div class="name">{{ product.name }}</div>
    <div class="points">{{ product.sellingPoints }}</div>
    <div class="row">
      <span class="price">￥{{ product.price }}</span>
      <span class="stock">库存 {{ product.stock }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ProductVO } from '@/types/api'

defineProps<{ product: ProductVO }>()
</script>

<style scoped>
.product-card {
  background: #fff;
  border-radius: 8px;
  padding: 10px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}

.product-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
}

.pic {
  width: 100%;
  aspect-ratio: 1;
  border-radius: 6px;
  background: #f5f7fa;
}

.pic-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  font-weight: 700;
  color: #c0c4cc;
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
  color: #909399;
  height: 32px;
  margin-top: 4px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 6px;
}

.price {
  color: var(--el-color-danger);
  font-size: 18px;
  font-weight: 700;
}

.stock {
  font-size: 12px;
  color: #c0c4cc;
}
</style>
