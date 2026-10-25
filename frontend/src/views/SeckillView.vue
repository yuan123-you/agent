<template>
  <div class="seckill-page">
    <!-- 极简秒杀页头 (彻底移除突兀黑底大卡片) -->
    <div class="sk-minimal-header">
      <div class="smh-left">
        <span class="smh-icon">⚡</span>
        <div class="smh-text">
          <h2 class="smh-title">限时秒杀</h2>
          <span class="smh-sub">精选品牌尖货 · 整点定时直降</span>
        </div>
      </div>
      <div v-if="countdownText" class="smh-countdown">
        <span class="smh-cd-label">距本场结束</span>
        <span class="smh-cd-time">{{ countdownText }}</span>
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
              <button class="sk-buy">马上抢购</button>
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
            <div class="sk-foot">
              <span class="sk-left">限量 {{ s.seckillStock }} 件</span>
              <button class="sk-buy soon">即将开始</button>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 已结束 -->
    <template v-if="endedList.length">
      <div class="group-head muted"><i class="bar-accent muted" />已结束</div>
      <div class="sk-grid">
        <div v-for="s in endedList" :key="s.seckillId" class="sk-card mall-card ended">
          <el-image :src="s.imageUrl" fit="cover" class="sk-pic" decoding="async" />
          <div class="sk-body">
            <div class="sk-name">{{ s.name }}</div>
            <div class="sk-prices">
              <span class="sk-now"><i>￥</i>{{ s.seckillPrice }}</span>
              <span class="sk-old">￥{{ s.originalPrice }}</span>
            </div>
            <div class="sk-foot">
              <span class="sk-left">已抢光</span>
              <button class="sk-buy ended" disabled>已抢完</button>
            </div>
          </div>
        </div>
      </div>
    </template>

    <el-empty v-if="!loading && seckills.length === 0" description="暂无秒杀活动" />
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

const activeList = computed(() => seckills.value.filter((s) => s.started && !s.ended))
const soonList = computed(() => seckills.value.filter((s) => !s.started && !s.ended))
const endedList = computed(() => seckills.value.filter((s) => s.ended))

const countdownText = computed(() => {
  const active = activeList.value[0]
  if (!active) return ''
  const diff = Math.max(0, new Date(active.endTime).getTime() - nowTick.value)
  const h = Math.floor(diff / 3600000)
  const m = Math.floor((diff % 3600000) / 60000)
  const s = Math.floor((diff % 60000) / 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(h)}:${pad(m)}:${pad(s)}`
})

function stockPercent(s: SeckillVO): string {
  const original = Math.max(1, s.seckillStock + 1)
  return `${Math.min(100, Math.round((s.seckillStock / original) * 100))}%`
}

const DEFAULT_SECKILLS: SeckillVO[] = [
  {
    seckillId: 1,
    productId: 1,
    name: 'Apple iPhone 15 Pro Max 钛金属旗舰手机',
    imageUrl: 'https://images.unsplash.com/photo-1695048133142-1a20484d2569?w=600&auto=format&fit=crop&q=80',
    seckillPrice: 7649,
    originalPrice: 9999,
    seckillStock: 28,
    seckillLimit: 1,
    startTime: new Date(Date.now() - 3600000).toISOString(),
    endTime: new Date(Date.now() + 7200000).toISOString(),
    started: true,
    ended: false,
  },
  {
    seckillId: 2,
    productId: 2,
    name: 'Sony WH-1000XM5 无线降噪头戴式耳机',
    imageUrl: 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&auto=format&fit=crop&q=80',
    seckillPrice: 1861,
    originalPrice: 2499,
    seckillStock: 45,
    seckillLimit: 2,
    startTime: new Date(Date.now() - 3600000).toISOString(),
    endTime: new Date(Date.now() + 7200000).toISOString(),
    started: true,
    ended: false,
  },
  {
    seckillId: 3,
    productId: 3,
    name: 'Xiaomi Watch Ultra 2 钛金属表壳智能手表',
    imageUrl: 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&auto=format&fit=crop&q=80',
    seckillPrice: 1299,
    originalPrice: 1799,
    seckillStock: 18,
    seckillLimit: 1,
    startTime: new Date(Date.now() - 3600000).toISOString(),
    endTime: new Date(Date.now() + 7200000).toISOString(),
    started: true,
    ended: false,
  },
  {
    seckillId: 4,
    productId: 4,
    name: 'Keychron Q1 Pro 全铝客制化无线机械键盘',
    imageUrl: 'https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=600&auto=format&fit=crop&q=80',
    seckillPrice: 899,
    originalPrice: 1299,
    seckillStock: 35,
    seckillLimit: 2,
    startTime: new Date(Date.now() + 10800000).toISOString(),
    endTime: new Date(Date.now() + 21600000).toISOString(),
    started: false,
    ended: false,
  },
]

onMounted(async () => {
  timer = window.setInterval(() => (nowTick.value = Date.now()), 1000)
  try {
    const list = await apiSeckills()
      if (list && list.length > 0) {
        seckills.value = list
      } else {
        seckills.value = DEFAULT_SECKILLS
      }
  } catch {
      seckills.value = DEFAULT_SECKILLS
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
  max-width: var(--mall-container, 1240px);
  margin: 0 auto;
  padding: 18px 20px 40px;
}

/* 页头横幅 */
.sk-minimal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--mall-border-light, #f4f4f5);
}

.smh-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.smh-icon {
  font-size: 20px;
}

.smh-text {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}

.smh-title {
  font-size: 18px;
  font-weight: 800;
  color: #18181b;
  margin: 0;
}

html.dark .smh-title {
  color: #f4f4f5;
}

.smh-sub {
  font-size: 12px;
  color: #71717a;
}

.smh-countdown {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--mall-price, #e11d48);
  color: #ffffff;
  padding: 4px 12px;
  border-radius: 9999px;
  font-size: 11px;
  font-weight: 700;
}

.smh-cd-time {
  font-family: monospace;
  letter-spacing: 1px;
}

.group-head {
  font-size: 18px;
  font-weight: 700;
  margin: 28px 0 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #0f172a;
}

html.dark .group-head {
  color: #f8fafc;
}

.group-head.muted {
  color: #94a3b8;
}

.bar-accent {
  width: 4px;
  height: 18px;
  border-radius: 2px;
  background: var(--mall-price, #e11d48);
}

.bar-accent.soon {
  background: #3b82f6;
}

.bar-accent.muted {
  background: #94a3b8;
}

.sk-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.sk-card {
  overflow: hidden;
  cursor: pointer;
  border-radius: var(--mall-radius, 10px);
  display: flex;
  flex-direction: column;
  transition: transform 0.22s ease, box-shadow 0.22s ease;
}

.sk-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--mall-shadow-hover);
}

.sk-pic {
  width: 100%;
  aspect-ratio: 1;
  background: var(--mall-surface-2, #f1f5f9);
}

.sk-body {
  padding: 14px;
  display: flex;
  flex-direction: column;
  flex: 1;
}

.sk-name {
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #0f172a;
}

html.dark .sk-name {
  color: #f1f5f9;
}

.sk-prices {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-top: 8px;
}

.sk-now {
  color: var(--mall-price, #e11d48);
  font-size: 20px;
  font-weight: 700;
}

.sk-now i {
  font-style: normal;
  font-size: 13px;
}

.sk-old {
  font-size: 12px;
  color: #94a3b8;
  text-decoration: line-through;
}

.sk-progress {
  height: 6px;
  border-radius: 9999px;
  background: #ffe4e6;
  overflow: hidden;
  margin: 10px 0;
}

.sk-bar {
  height: 100%;
  border-radius: 9999px;
  background: linear-gradient(90deg, #f43f5e, #e11d48);
}

.sk-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
}

.sk-left {
  font-size: 12px;
  color: #64748b;
}

.sk-buy {
  border: none;
  border-radius: 6px;
  padding: 6px 14px;
  background: var(--mall-price, #e11d48);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.sk-buy:hover {
  opacity: 0.9;
}

.sk-buy.soon {
  background: #3b82f6;
}

.sk-buy.ended {
  background: #94a3b8;
  cursor: not-allowed;
}

@media (max-width: 992px) {
  .sk-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .seckill-page {
    padding: 12px 14px 28px;
  }
  .seckill-hero {
    padding: 20px 18px;
  }
  .sh-title {
    font-size: 22px;
  }
  .sh-flash {
    font-size: 32px;
  }
  .sk-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }
  .sk-body {
    padding: 10px;
  }
  .sk-now {
    font-size: 17px;
  }
}
</style>
