<template>
  <section class="brand-section container">
    <div class="section-header">
      <div class="title-wrap">
        <span class="accent-dot"></span>
        <h3 class="section-title">官方授权品牌</h3>
      </div>
      <span class="sub-label">100% 正品保障 · 品牌深度合作</span>
    </div>
    <div class="brand-grid">
      <div
        v-for="brand in brands"
        :key="brand.name"
        class="brand-tile"
        @click="$router.push(`/products?keyword=${encodeURIComponent(brand.name)}`)"
      >
        <span class="brand-name">{{ brand.logoText }}</span>
        <span class="brand-cat">{{ brand.category }}</span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useMallConfig } from '@/composables/useMallConfig'

const { config } = useMallConfig()
const brands = computed(() => config.value.brandPartners || [])
</script>

<style scoped>
.brand-section {
  margin: 32px auto;
}

.section-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 14px;
}

.title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.accent-dot {
  width: 6px;
  height: 16px;
  border-radius: 3px;
  background: #64748b;
}

.section-title {
  font-size: 19px;
  font-weight: 700;
  color: #0f172a;
  margin: 0;
  letter-spacing: -0.02em;
}

html.dark .section-title {
  color: #f8fafc;
}

.sub-label {
  font-size: 13px;
  color: #94a3b8;
}

.brand-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 12px;
}

.brand-tile {
  background: var(--mall-surface, #ffffff);
  border: 1px solid var(--mall-border-light, #f1f5f9);
  border-radius: var(--mall-radius, 10px);
  padding: 16px 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  cursor: pointer;
  box-shadow: var(--mall-shadow-xs);
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.brand-tile:hover {
  transform: translateY(-3px);
  box-shadow: var(--mall-shadow-hover);
  border-color: var(--mall-border, #cbd5e1);
}

.brand-name {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #0f172a;
}

html.dark .brand-name {
  color: #f8fafc;
}

.brand-cat {
  font-size: 11px;
  color: #94a3b8;
}

@media (max-width: 992px) {
  .brand-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}

@media (max-width: 576px) {
  .brand-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
