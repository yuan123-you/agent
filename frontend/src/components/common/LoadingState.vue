<template>
  <div
    v-if="loading"
    class="loading-state"
    :class="{ 'loading-state--full-page': fullPage }"
    :data-loading-variant="variant"
    role="status"
    :aria-label="label"
    aria-busy="true"
    aria-live="polite"
  >
    <div v-if="variant === 'spinner'" class="loading-center" aria-hidden="true">
      <span class="loading-spinner" />
    </div>
    <div v-else-if="variant === 'detail'" class="loading-detail" aria-hidden="true">
      <div class="loading-shape loading-hero" />
      <div class="loading-detail-body">
        <div class="loading-shape loading-price" />
        <div class="loading-shape loading-line" />
        <div class="loading-shape loading-line loading-line--short" />
        <div v-for="n in 3" :key="n" class="loading-detail-section">
          <div class="loading-shape loading-line loading-line--short" />
          <div class="loading-shape loading-line" />
        </div>
      </div>
    </div>
    <div v-else :class="['loading-layout', `loading-layout--${variant}`]" aria-hidden="true">
      <div v-for="n in count" :key="n" :class="['loading-item', variant === 'cards' ? 'loading-card' : `loading-${variant}-item` ]">
        <div v-if="variant === 'cards' || variant === 'list'" class="loading-shape loading-picture" />
        <div v-if="variant === 'table'" class="loading-table-cells">
          <div v-for="cell in 4" :key="cell" class="loading-shape loading-line" />
        </div>
        <div v-else class="loading-copy">
          <div class="loading-shape loading-line" />
          <div class="loading-shape loading-line loading-line--short" />
          <div v-if="variant === 'cards' || variant === 'list'" class="loading-shape loading-price" />
        </div>
      </div>
    </div>
  </div>
  <slot v-else />
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  loading?: boolean
  variant?: 'detail' | 'cards' | 'list' | 'table' | 'stats' | 'text' | 'spinner'
  label?: string
  count?: number
  fullPage?: boolean
}>(), {
  loading: true,
  variant: 'list',
  label: '正在加载内容',
  count: 4,
  fullPage: false,
})
</script>

<style scoped>
.loading-state { width: 100%; min-width: 0; box-sizing: border-box; padding: 16px 0; }
.loading-shape {
  background: var(--el-fill-color, #f0f2f5);
  border-radius: 6px;
  position: relative;
  overflow: hidden;
}
.loading-shape::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, var(--el-fill-color-blank, #fff), transparent);
  opacity: .55;
  transform: translateX(-100%);
  animation: loading-shimmer 1.6s ease-in-out infinite;
}
.loading-layout { display: grid; gap: 16px; }
.loading-layout--cards { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.loading-layout--stats { grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); }
.loading-item { min-width: 0; }
.loading-card, .loading-list-item, .loading-stats-item {
  padding: 16px;
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 12px;
  background: var(--mall-surface, var(--el-bg-color, #fff));
}
.loading-card { padding: 0 0 16px; overflow: hidden; }
.loading-card .loading-copy { padding: 16px 12px 0; }
.loading-picture { width: 100%; aspect-ratio: 1; border-radius: 0; }
.loading-list-item { display: flex; align-items: center; gap: 16px; }
.loading-list-item .loading-picture { width: 88px; flex: 0 0 88px; border-radius: 8px; }
.loading-copy { flex: 1; min-width: 0; }
.loading-line { height: 14px; width: 90%; margin-bottom: 12px; }
.loading-line--short { width: 58%; }
.loading-price { height: 22px; width: 30%; min-width: 64px; }
.loading-table-item { padding: 16px 12px; border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5); }
.loading-table-cells { display: grid; grid-template-columns: 1fr 3fr 2fr 2fr; gap: 24px; }
.loading-table-cells .loading-line { margin: 0; }
.loading-text-item { padding: 8px 0; }
.loading-detail { max-width: 860px; margin: 0 auto; background: var(--mall-surface, var(--el-bg-color, #fff)); }
.loading-state[data-loading-variant="detail"] { padding: 0; }
.loading-hero { height: 340px; border-radius: 0; }
.loading-detail-body { padding: 24px; }
.loading-detail-body > .loading-price { margin-bottom: 20px; }
.loading-detail-section { padding: 24px 0 12px; border-top: 1px solid var(--el-border-color-lighter, #ebeef5); margin-top: 24px; }
.loading-center { display: grid; place-items: center; min-height: 240px; }
.loading-spinner { width: 36px; height: 36px; border: 3px solid var(--el-fill-color, #f0f2f5); border-top-color: var(--el-color-primary, #e11d48); border-radius: 50%; animation: loading-spin .8s linear infinite; }
.loading-state--full-page { position: fixed; inset: 0; z-index: 100; display: grid; place-items: center; pointer-events: none; }
@keyframes loading-shimmer { to { transform: translateX(100%); } }
@keyframes loading-spin { to { transform: rotate(360deg); } }
@media (max-width: 1024px) { .loading-layout--cards { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 640px) {
  .loading-layout--cards, .loading-layout--stats { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
  .loading-list-item { padding: 12px; gap: 12px; }
  .loading-list-item .loading-picture { width: 72px; flex-basis: 72px; }
  .loading-table-cells { gap: 12px; }
  .loading-hero { height: 320px; }
  .loading-detail-body { padding: 20px 16px; }
}
@media (prefers-reduced-motion: reduce) {
  .loading-shape::after, .loading-spinner { animation: none; }
}
</style>
