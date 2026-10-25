<template>
  <div class="mega-menu" @mouseleave="$emit('close')">
    <div class="mega-inner">
      <!-- 左侧分类纵览 -->
      <div class="mega-cats">
        <div
          v-for="c in categories"
          :key="c.code"
          class="mega-cat-item"
          :class="{ active: activeCode === c.code }"
          @mouseenter="activeCode = c.code"
          @click="goCategory(c)"
        >
          <span class="m-icon">{{ c.icon }}</span>
          <span class="m-name">{{ c.name }}</span>
          <span class="m-arrow">›</span>
        </div>
      </div>

      <!-- 右侧联动详情面板 -->
      <div class="mega-detail">
        <div class="detail-header">
          <h4 class="detail-title">{{ activeCategory?.name }} 甄选推荐</h4>
          <span class="detail-more" @click="goCategory(activeCategory)">查看全部品类 ›</span>
        </div>

        <div class="subcats-grid">
          <div v-for="sub in subItems" :key="sub.name" class="subcat-card" @click="goKeyword(sub.name)">
            <span class="subcat-icon">{{ sub.icon }}</span>
            <span class="subcat-name">{{ sub.name }}</span>
            <span class="subcat-desc">{{ sub.desc }}</span>
          </div>
        </div>

        <!-- 底部品牌与特惠微条 -->
        <div class="mega-footer-banner">
          <span class="mf-tag">限时特惠</span>
          <span class="mf-text">官方旗舰店直供 · 领券立享折上折 · 正品极速达</span>
          <button class="mf-btn" @click="goCategory(activeCategory)">立即探索 →</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { CATEGORIES, type CategoryDef } from '@/constants/categories'

const emit = defineEmits<{ (e: 'close'): void }>()
const router = useRouter()

const categories = ref<CategoryDef[]>(CATEGORIES.slice(0, 10))
const activeCode = ref(CATEGORIES[0]?.code || 'PHONE')

const activeCategory = computed(() => {
  return categories.value.find((c) => c.code === activeCode.value) || categories.value[0]
})

const SUB_MAP: Record<string, Array<{ name: string; icon: string; desc: string }>> = {
  PHONE: [
    { name: '旗舰智能机', icon: '📱', desc: '超强计算摄影与旗舰芯片' },
    { name: '真无线耳机', icon: '🎧', desc: '深度主动降噪与空间音频' },
    { name: '智能穿戴', icon: '⌚', desc: '全天候心率血氧运动监测' },
    { name: '平板电脑', icon: '📲', desc: '高效手写与视网膜全面屏' },
    { name: '数码配件', icon: '🔌', desc: '氮化镓快充与磁吸保护套' },
    { name: '无人机影像', icon: '🛸', desc: '4K超清航拍与三轴云台' },
  ],
  LAPTOP: [
    { name: '轻薄便携本', icon: '💻', desc: '全天候长续航办公首选' },
    { name: '极客游戏本', icon: '🎮', desc: '高刷电竞屏与强劲独显' },
    { name: '客制化键盘', icon: '⌨️', desc: '机械轴体与RGB光效' },
    { name: '人体工学外设', icon: '🖱️', desc: '无线双模握感舒适' },
    { name: '专业显示器', icon: '🖥️', desc: '4K高色准专业绘图' },
    { name: '生产力桌搭', icon: '💡', desc: '屏幕挂灯与实木支架' },
  ],
  APPLIANCE: [
    { name: '变频净化器', icon: '🌀', desc: '双重滤网全屋除醛' },
    { name: '负离子吹风', icon: '💨', desc: '亿级柔风快速干发' },
    { name: '扫拖一体机', icon: '🤖', desc: '激光导航全自动集尘' },
    { name: '原汁榨汁机', icon: '🍹', desc: '低速慢榨原汁原味' },
    { name: '意式咖啡机', icon: '☕', desc: '20Bar高压萃取浓缩' },
    { name: '除螨吸尘器', icon: '🧹', desc: '强劲吸力深度清洁' },
  ],
}

const subItems = computed(() => {
  return (
    SUB_MAP[activeCode.value] || [
      { name: '精选爆款', icon: '🔥', desc: '真实高口碑买家热推' },
      { name: '重磅新品', icon: '✨', desc: '最新上市品质优选' },
      { name: '专区特惠', icon: '🏷️', desc: '限量满减立折好物' },
      { name: '官方自营', icon: '🛡️', desc: '正品溯源保障无忧' },
      { name: '品质升级', icon: '💎', desc: '打造品质生活场域' },
      { name: '会员专享', icon: '🎁', desc: '下单立享积分多倍' },
    ]
  )
})

function goCategory(c: any) {
  emit('close')
  router.push(`/products?category=${c.code}`)
}

function goKeyword(kw: string) {
  emit('close')
  router.push(`/products?keyword=${encodeURIComponent(kw)}`)
}
</script>

<style scoped>
.mega-menu {
  position: absolute;
  top: 100%;
  left: 0;
  width: 760px;
  background: var(--mall-surface, #ffffff);
  border: 1px solid var(--mall-border, #e2e8f0);
  border-radius: var(--mall-radius-lg, 14px);
  box-shadow: 0 16px 36px -4px rgba(15, 23, 42, 0.16);
  z-index: 100;
  overflow: hidden;
}

html.dark .mega-menu {
  border-color: var(--mall-border, #232734);
  box-shadow: 0 20px 40px -4px rgba(0, 0, 0, 0.7);
}

.mega-inner {
  display: flex;
  min-height: 380px;
}

.mega-cats {
  width: 190px;
  background: var(--mall-surface-2, #f8fafc);
  border-right: 1px solid var(--mall-border-light, #f1f5f9);
  padding: 10px 0;
  display: flex;
  flex-direction: column;
}

.mega-cat-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 18px;
  height: 36px;
  font-size: 13px;
  color: #334155;
  cursor: pointer;
  transition: all 0.15s ease;
}

html.dark .mega-cat-item {
  color: #cbd5e1;
}

.mega-cat-item:hover,
.mega-cat-item.active {
  background: var(--mall-surface, #ffffff);
  color: var(--el-color-primary, #2563eb);
  font-weight: 600;
}

.m-icon {
  font-size: 15px;
}

.m-name {
  flex: 1;
}

.m-arrow {
  color: #94a3b8;
  font-size: 14px;
}

/* 详情区 */
.mega-detail {
  flex: 1;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.detail-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  margin: 0;
}

html.dark .detail-title {
  color: #f8fafc;
}

.detail-more {
  font-size: 12px;
  color: var(--el-color-primary, #2563eb);
  cursor: pointer;
}

.subcats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  flex: 1;
}

.subcat-card {
  background: var(--mall-surface-2, #f8fafc);
  border: 1px solid var(--mall-border-light, #f1f5f9);
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 3px;
  transition: all 0.18s ease;
}

.subcat-card:hover {
  background: var(--mall-surface, #ffffff);
  border-color: var(--el-color-primary, #2563eb);
  transform: translateY(-2px);
  box-shadow: var(--mall-shadow-xs);
}

.subcat-icon {
  font-size: 20px;
  margin-bottom: 2px;
}

.subcat-name {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}

html.dark .subcat-name {
  color: #f1f5f9;
}

.subcat-desc {
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.35;
}

.mega-footer-banner {
  margin-top: 16px;
  padding: 10px 14px;
  background: radial-gradient(circle at 90% 50%, rgba(37, 99, 235, 0.15), transparent 70%),
              var(--mall-surface-2, #f1f5f9);
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.mf-tag {
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  background: var(--mall-price, #e11d48);
  padding: 2px 6px;
  border-radius: 4px;
}

.mf-text {
  font-size: 12px;
  color: #475569;
  flex: 1;
}

html.dark .mf-text {
  color: #cbd5e1;
}

.mf-btn {
  border: none;
  background: var(--el-color-primary, #2563eb);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 9999px;
  cursor: pointer;
}
</style>
