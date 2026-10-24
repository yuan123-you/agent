<template>
  <div class="seckill-page">
    <!-- 页头横幅：全局倒计时 -->
    <div class="seckill-hero">
      <div class="sh-info">
        <span class="sh-flash">⚡</span>
        <div>
          <div class="sh-title">限时秒杀</div>
          <div class="sh-sub">品牌好物 · 低价到底 · 每日上新</div>
        </div>
      </div>
      <div v-if="countdownText" class="sh-countdown">
        <span class="sh-cd-label">距结束</span>
        <span class="sh-cd-time">{{ countdownText }}</span>
      </div>
    </div>

    <!-- 进行中 -->
    <template v-if="activeList.length">
      <div class="group-head"><i class="bar-accent" />正在疯抢</div>
      <div class="sk-grid">
        <div v-for="s in activeList" :key="s.seckillId" class="sk-card mall-card"
          @click="$router.push(`/products/${s.productId}`)">
          <el-image :src="s.imageUrl" fit="cover" class="sk-pic" decoding="async" />
          <div class="sk-body">
            <div class="sk-name">{{ s.name }}</div>
            <div class="sk-prices">
              <span class="sk-now"><i>￥</i>{{ s.seckillPrice }}</span>
              <span class="sk-old">￥{{ s.originalPrice }}</span>
            </div>
            <div class="sk-progress"><div class="sk-bar" :style="{ width: stockPercent(s) }" /></div>
            <div class="sk-foot">
              <span class="sk-left">仅剩 {{ s.seckillStock }} 件</span>
              <button class="sk-buy">马上抢</button>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 即将开始 -->
    <template v-if="soonList.length">
      <div class="group-head"><i class="bar-accent soon" />即将开始</div>
      <div class="sk-grid">
        <div v-for="s in soonList" :key="s.seckillId" class="sk-card mall-card soon"
          @click="$router.push(`/products/${s.productId}`)">
          <el-image :src="s.imageUrl" fit="cover" class="sk-pic" decoding="async" />
          <div class="sk-body">
            <div class="sk-name">{{ s.name }}</div>
            <div class="sk-prices">
              <span class="sk-now"><i>￥</i>{{ s.seckillPrice }}</span>
              <span class="sk-old">￥{{ s.originalPrice }}</span>
            </div>
            <div class="sk-start">{{ startTimeText(s) }} 开抢</div>
            <div class="sk-foot">
              <span class="sk-left">限量 {{ s.seckillStock + s.seckillLimit }} 件</span>
              <button class="sk-buy soon" disabled>未开始</button>
            </div>
          </div>
        </div>
      </div>
    </template>

    <el-empty v-if="!loading && seckills.length === 0" description="暂无秒杀活动，敬请期待" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { apiSeckills } from '@/api'
import type { SeckillVO } from '@/types/api'

const seckills = ref<SeckillVO[]>([])
const loading = ref(true)
const nowTick = ref(Date.now())
let timer: number | undefined

const activeList = computed(() => seckills.value.filter((s) => s.started))
const soonList = computed(() => seckills.value.filter((s) => !s.started))

const countdownText = computed(() => {
  const ends = activeList.value.map((s) => new Date(s.endTime).getTime())
  if (!ends.length) return ''
  const diff = Math.max(0, Math.min(...ends) - nowTick.value)
  const d = Math.floor(diff / 86400000)
  const h = Math.floor((diff % 86400000) / 3600000)
  const m = Math.floor((diff % 3600000) / 60000)
  const s = Math.floor((diff % 60000) / 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return (d > 0 ? `${d}天 ` : '') + `${pad(h)}:${pad(m)}:${pad(s)}`
})

function stockPercent(s: SeckillVO): string {
  const original = Math.max(1, s.seckillStock + 1)
  return `${Math.min(100, Math.round((s.seckillStock / original) * 100))}%`
}

function startTimeText(s: SeckillVO): string {
  return (s.startTime || '').replace('T', ' ').slice(5, 16)
}

onMounted(async () => {
  timer = window.setInterval(() => (nowTick.value = Date.now()), 1000)
  try {
    seckills.value = (await apiSeckills()) || []
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<style scoped>
.seckill-page {
  max-width: var(--mall-container, 1200px);
  margin: 0 auto;
  padding: 16px 16px 32px;
}

/* 页头横幅 */
.seckill-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  background: linear-gradient(120deg, #ee0a24, #ff6034);
  border-radius: var(--mall-radius-lg, 12px);
  color: #fff;
  padding: 26px 28px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.sh-info {
  display: flex;
  align-items: center;
  gap: 14px;
}

.sh-flash {
  font-size: 42px;
  filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.25));
}

.sh-title {
  font-size: 28px;
  font-weight: 800;
  letter-spacing: 2px;
}

.sh-sub {
  font-size: 13px;
  opacity: 0.9;
  margin-top: 2px;
}

.sh-countdown {
  background: rgba(0, 0, 0, 0.35);
  border-radius: 8px;
  padding: 10px 18px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.sh-cd-label {
  font-size: 12px;
  opacity: 0.85;
}

.sh-cd-time {
  font-size: 22px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  letter-spacing: 1px;
}

/* 分组标题 */
.group-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 800;
  margin: 0 0 12px;
}

.bar-accent {
  display: inline-block;
  width: 4px;
  height: 18px;
  border-radius: 2px;
  background: var(--mall-gradient);
}

.bar-accent.soon {
  background: linear-gradient(120deg, #b8c4ff, #8f9dff);
}

/* 网格 */
.sk-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 24px;
}

.sk-card {
  overflow: hidden;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  transition: box-shadow 0.15s;
}

.sk-card:hover {
  box-shadow: var(--mall-shadow-hover);
}

.sk-pic {
  width: 100%;
  aspect-ratio: 1;
  background: var(--mall-surface-2, #f5f7fa);
}

.sk-body {
  padding: 10px 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sk-name {
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sk-prices {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.sk-now {
  color: var(--mall-price, #e4393c);
  font-size: 22px;
  font-weight: 700;
}

.sk-now i {
  font-style: normal;
  font-size: 13px;
}

.sk-old {
  font-size: 12px;
  color: var(--el-text-color-placeholder, #c0c4cc);
  text-decoration: line-through;
}

.sk-progress {
  height: 6px;
  border-radius: 3px;
  background: #fde2e2;
  overflow: hidden;
}

.sk-bar {
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, #ff6034, var(--mall-price, #e4393c));
}

.sk-start {
  font-size: 12px;
  color: #7d8aff;
}

.sk-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sk-left {
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
}

.sk-buy {
  border: 0;
  border-radius: 14px;
  padding: 5px 16px;
  background: linear-gradient(90deg, #ff6034, var(--mall-price, #e4393c));
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.sk-buy:hover {
  filter: brightness(1.08);
}

.sk-buy.soon {
  background: linear-gradient(120deg, #b8c4ff, #8f9dff);
  cursor: not-allowed;
}

/* 平板/手机 */
@media (max-width: 1199px) {
  .sk-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .seckill-page {
    padding: 12px 12px 24px;
  }

  .seckill-hero {
    padding: 16px;
  }

  .sh-title {
    font-size: 20px;
  }

  .sh-flash {
    font-size: 30px;
  }

  .sh-cd-time {
    font-size: 16px;
  }

  .sk-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }
}
</style>
