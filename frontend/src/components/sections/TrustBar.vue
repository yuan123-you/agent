<template>
  <section class="trust-bar-section container">
    <div class="trust-grid">
      <div v-for="(b, i) in badges" :key="i" class="trust-item">
        <div class="icon-wrap">
          <span class="icon-emoji" v-if="i === 0">🛡️</span>
          <span class="icon-emoji" v-else-if="i === 1">⚡</span>
          <span class="icon-emoji" v-else-if="i === 2">🔄</span>
          <span class="icon-emoji" v-else>🤖</span>
        </div>
        <div class="text-wrap">
          <div class="trust-title">{{ b.title }}</div>
          <div class="trust-desc">{{ b.desc }}</div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useMallConfig } from '@/composables/useMallConfig'

const { config } = useMallConfig()
const badges = computed(() => config.value.trustBadges || [])
</script>

<style scoped>
.trust-bar-section {
  margin: 16px auto;
}

.trust-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  background: var(--mall-surface, #ffffff);
  border: 1px solid var(--mall-border-light, #f1f5f9);
  border-radius: var(--mall-radius, 10px);
  padding: 16px 24px;
  box-shadow: var(--mall-shadow-card);
}

.trust-item {
  display: flex;
  align-items: center;
  gap: 14px;
}

.icon-wrap {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: var(--mall-surface-2, #f1f5f9);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
  transition: transform 0.2s ease;
}

.trust-item:hover .icon-wrap {
  transform: scale(1.08);
}

.trust-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

html.dark .trust-title {
  color: #f1f5f9;
}

.trust-desc {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}

html.dark .trust-desc {
  color: #94a3b8;
}

@media (max-width: 992px) {
  .trust-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
    padding: 14px 16px;
  }
}

@media (max-width: 576px) {
  .trust-grid {
    grid-template-columns: 1fr;
    gap: 10px;
  }
  .icon-wrap {
    width: 36px;
    height: 36px;
    font-size: 17px;
  }
}
</style>
