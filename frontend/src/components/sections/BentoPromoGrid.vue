<template>
  <section class="bento-section container">
    <div class="section-header">
      <div class="title-wrap">
        <span class="accent-dot"></span>
        <h3 class="section-title">甄选企划 · 探索灵感</h3>
      </div>
      <span class="sub-label">精选主题专区与限时特惠</span>
    </div>
    <div class="bento-grid">
      <div
        v-for="card in cards"
        :key="card.id"
        class="bento-card"
        :class="`span-${card.span}`"
        :style="{ background: card.bg }"
        @click="$router.push(card.link)"
      >
        <div class="card-inner">
          <div class="card-top">
            <span class="card-badge">{{ card.badge }}</span>
            <span class="card-icon">{{ card.icon }}</span>
          </div>
          <div class="card-content">
            <h4 class="card-title">{{ card.title }}</h4>
            <p class="card-desc">{{ card.desc }}</p>
            <span class="card-cta">{{ card.ctaText }} →</span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useMallConfig } from '@/composables/useMallConfig'

const { config } = useMallConfig()
const cards = computed(() => config.value.bentoCards || [])
</script>

<style scoped>
.bento-section {
  margin: 28px auto;
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
  background: var(--el-color-primary, #2563eb);
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

.bento-grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 14px;
}

.bento-card {
  border-radius: var(--mall-radius-lg, 14px);
  padding: 24px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  box-shadow: var(--mall-shadow-card);
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.bento-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--mall-shadow-hover);
}

.span-large {
  grid-column: span 7;
  min-height: 200px;
}

.span-small {
  grid-column: span 5;
  min-height: 200px;
}

.card-inner {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-badge {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  padding: 3px 10px;
  border-radius: 9999px;
  background: rgba(255, 255, 255, 0.16);
  color: #ffffff;
  backdrop-filter: blur(8px);
}

.card-icon {
  font-size: 28px;
}

.card-content {
  margin-top: 24px;
}

.card-title {
  font-size: 20px;
  font-weight: 700;
  color: #ffffff;
  margin: 0 0 6px;
  letter-spacing: -0.01em;
}

.card-desc {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.8);
  margin: 0 0 14px;
  line-height: 1.5;
}

.card-cta {
  font-size: 13px;
  font-weight: 600;
  color: #ffffff;
  display: inline-flex;
  align-items: center;
  transition: transform 0.2s ease;
}

.bento-card:hover .card-cta {
  transform: translateX(4px);
}

@media (max-width: 992px) {
  .span-large,
  .span-small {
    grid-column: span 6;
  }
}

@media (max-width: 640px) {
  .span-large,
  .span-small {
    grid-column: span 12;
    min-height: 160px;
    padding: 18px;
  }
  .card-title {
    font-size: 17px;
  }
}
</style>
