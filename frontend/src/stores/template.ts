import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ProductVO } from '@/types/api'

export interface TemplateSection {
  id: string
  type: 'hero-slider' | 'trust-bar' | 'category-nav' | 'bento-grid' | 'flash-sale' | 'coupon-center' | 'ai-assistant' | 'product-grid' | 'brand-wall'
  title: string
  subtitle: string
  enabled: boolean
  badge?: string
}

export interface IndustryPreset {
  id: string
  name: string
  icon: string
  brandName: string
  slogan: string
  logoBadge: string
  primaryColor: string
  priceColor: string
  radius: string
  slides: Array<{
    id: string
    badge: string
    title: string
    subtitle: string
    ctaText: string
    link: string
    bg: string
    emoji: string
  }>
  products: ProductVO[]
  sections: TemplateSection[]
}

const PRESET_DIGITAL: IndustryPreset = {
  id: 'digital',
  name: '3C 极客数码',
  icon: '⚡',
  brandName: 'CyberMall',
  slogan: '硬核算力 · 极客旗舰终端',
  logoBadge: 'CYBER',
  primaryColor: '#2563eb',
  priceColor: '#e11d48',
  radius: '10px',
  slides: [
    {
      id: 'd1',
      badge: '年度旗舰 · 算力巅峰',
      title: '极智科技，灵感无界',
      subtitle: '新一代智能微架构终端 · 带来颠覆级沉浸性能与工业美学体验',
      ctaText: '探索新品 →',
      link: '/products',
      bg: 'linear-gradient(135deg, #090d16 0%, #1e293b 100%)',
      emoji: '✨',
    },
    {
      id: 'd2',
      badge: '客制化生产力',
      title: '机械美学，纯粹手感',
      subtitle: '全铝合金 CNC 一体成型 · 蓝牙多模与全键热插拔',
      ctaText: '查看系列 →',
      link: '/products',
      bg: 'linear-gradient(135deg, #172554 0%, #1e1b4b 100%)',
      emoji: '⌨️',
    },
  ],
  products: [
    { id: 101, name: '专业级降噪头戴式无线蓝牙耳机 Pro', price: 1599, sales: 8400, category: 'PHONE', brand: 'Sony', imageUrl: 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&auto=format&fit=crop&q=60', sellingPoints: '双芯主动降噪 · 40小时长续航' },
    { id: 102, name: '全铝合金客制化三模机械键盘 RGB', price: 499, sales: 5200, category: 'PHONE', brand: 'Keychron', imageUrl: 'https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=500&auto=format&fit=crop&q=60', sellingPoints: '热插拔轴体 · 蓝牙双模连接' },
    { id: 103, name: '超轻薄 14 英寸全面屏视网膜笔记本电脑', price: 4299, sales: 3800, category: 'PHONE', brand: 'Apple', imageUrl: 'https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=500&auto=format&fit=crop&q=60', sellingPoints: 'M芯片超长续航 · 视网膜广色域' },
    { id: 104, name: '高通量氮化镓 140W 桌面多口超级充电器', price: 299, sales: 7800, category: 'PHONE', brand: 'Anker', imageUrl: 'https://images.unsplash.com/photo-1583863788434-e58a36330cf0?w=500&auto=format&fit=crop&q=60', sellingPoints: '四口同时快充 · 智能温控防烫' },
  ],
  sections: [
    { id: 'hero-slider', type: 'hero-slider', title: '主焦点舞台', subtitle: '全屏轮播展位', enabled: true },
    { id: 'trust-bar', type: 'trust-bar', title: '品质承诺条', subtitle: '4项官方保障', enabled: true },
    { id: 'bento-grid', type: 'bento-grid', title: '甄选企划', subtitle: '探索生活与科技美学', enabled: true },
    { id: 'flash-sale', type: 'flash-sale', title: '限时秒杀', subtitle: '定时整点开抢', enabled: true },
    { id: 'coupon-center', type: 'coupon-center', title: '超值礼券', subtitle: '全场立减券', enabled: true },
    { id: 'ai-assistant', type: 'ai-assistant', title: 'AI 导购管家', subtitle: '智能自然语言解答', enabled: true },
    { id: 'product-grid', type: 'product-grid', title: '甄选数码系列', subtitle: '官方认证旗舰好物', enabled: true },
    { id: 'brand-wall', type: 'brand-wall', title: '官方授权品牌', subtitle: '合作品牌墙', enabled: true },
  ],
}

const PRESET_MINIMAL: IndustryPreset = {
  id: 'minimal',
  name: '极简轻奢 / 美学独立站',
  icon: '🏛️',
  brandName: 'Nordic Studio',
  slogan: '少即是多 · 纯粹生活美学',
  logoBadge: 'NORD',
  primaryColor: '#18181b',
  priceColor: '#18181b',
  radius: '6px',
  slides: [
    {
      id: 'm1',
      badge: 'ARCHITECTURAL LIVING',
      title: '生活美学，纯粹质感',
      subtitle: '现代居室与高效桌搭方案 · 打造独属于你的松弛生活场域',
      ctaText: '选购系列 →',
      link: '/products',
      bg: 'linear-gradient(135deg, #18181b 0%, #27272a 100%)',
      emoji: '🛋️',
    },
  ],
  products: [
    { id: 201, name: '经典极简重磅纯棉连帽卫衣 420g', price: 269, sales: 4300, category: 'CLOTHING', brand: 'Muji', imageUrl: 'https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=500&auto=format&fit=crop&q=60', sellingPoints: '420g 重磅精梳棉 · 挺括亲肤' },
    { id: 202, name: '人体工学可升降护脊办公电竞椅', price: 1899, sales: 2100, category: 'HOME', brand: 'Herman Miller', imageUrl: 'https://images.unsplash.com/photo-1580481077195-c328a37db71a?w=500&auto=format&fit=crop&q=60', sellingPoints: '动态双背支撑 · 4D可调扶手' },
    { id: 203, name: '便携式户外高压浓缩意式咖啡机', price: 399, sales: 6100, category: 'FOOD', brand: 'Barista', imageUrl: 'https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=500&auto=format&fit=crop&q=60', sellingPoints: '18Bar 黄金油脂 · 无需插电' },
    { id: 204, name: '天然大豆香薰蜡烛手工礼盒', price: 189, sales: 3200, category: 'HOME', brand: 'Nordic', imageUrl: 'https://images.unsplash.com/photo-1603006905003-be475563bc59?w=500&auto=format&fit=crop&q=60', sellingPoints: '雪松与冷杉 · 纯植物精油' },
  ],
  sections: [
    { id: 'hero-slider', type: 'hero-slider', title: '主焦点舞台', subtitle: '全屏轮播展位', enabled: true },
    { id: 'trust-bar', type: 'trust-bar', title: '品质承诺条', subtitle: '4项官方保障', enabled: true },
    { id: 'product-grid', type: 'product-grid', title: '甄选生活美学', subtitle: '精选少而优的器物', enabled: true },
    { id: 'brand-wall', type: 'brand-wall', title: '合作品牌', subtitle: '合作品牌墙', enabled: true },
  ],
}

const PRESET_FRESH: IndustryPreset = {
  id: 'fresh',
  name: '天然生鲜 / 果蔬优选',
  icon: '🍏',
  brandName: 'FreshGarden',
  slogan: '原产直供 · 恒温冷链直达',
  logoBadge: 'FRESH',
  primaryColor: '#059669',
  priceColor: '#ea580c',
  radius: '14px',
  slides: [
    {
      id: 'f1',
      badge: '原产地冷链直达',
      title: '天然生鲜，四季尝鲜',
      subtitle: '严选高海拔有机生态基地 · 恒温冷链24小时锁鲜到家',
      ctaText: '抢鲜尝鲜 →',
      link: '/products',
      bg: 'linear-gradient(135deg, #064e3b 0%, #065f46 100%)',
      emoji: '🍎',
    },
  ],
  products: [
    { id: 301, name: '有机生态农场智利车厘子 5斤礼盒装 JJJ级', price: 299, sales: 9100, category: 'FOOD', brand: '原产直供', imageUrl: 'https://images.unsplash.com/photo-1528825871115-3581a5387919?w=500&auto=format&fit=crop&q=60', sellingPoints: '冷链航空直达 · 果肉脆甜多汁' },
    { id: 302, name: '澳洲安格斯谷饲原切眼肉牛排 1kg装', price: 238, sales: 4800, category: 'FOOD', brand: '牧场直运', imageUrl: 'https://images.unsplash.com/photo-1603048588665-791ca8aea617?w=500&auto=format&fit=crop&q=60', sellingPoints: '纯谷饲育肥 · 油花丰腴细腻' },
    { id: 303, name: '日本阳光玫瑰青提葡萄 2斤装礼盒', price: 128, sales: 5600, category: 'FOOD', brand: '庄园直采', imageUrl: 'https://images.unsplash.com/photo-1596363505729-4190a9506133?w=500&auto=format&fit=crop&q=60', sellingPoints: '玫瑰浓郁清香 · 无籽爆汁纯甜' },
    { id: 304, name: '鲜活现捞冷冻舟山深海大虾 2kg', price: 168, sales: 6700, category: 'FOOD', brand: '远洋渔业', imageUrl: 'https://images.unsplash.com/photo-1565680018434-b513d5e5fd47?w=500&auto=format&fit=crop&q=60', sellingPoints: '捕捞船冻急锁 · 肉质紧实弹牙' },
  ],
  sections: [
    { id: 'hero-slider', type: 'hero-slider', title: '主焦点舞台', subtitle: '全屏轮播展位', enabled: true },
    { id: 'trust-bar', type: 'trust-bar', title: '原产地冷链保障', subtitle: '全程温控', enabled: true },
    { id: 'flash-sale', type: 'flash-sale', title: '今日生鲜特惠', subtitle: '限量鲜抢', enabled: true },
    { id: 'product-grid', type: 'product-grid', title: '原生态果蔬肉禽', subtitle: '绿色健康美味', enabled: true },
  ],
}

const PRESETS = [PRESET_DIGITAL, PRESET_MINIMAL, PRESET_FRESH]
const STORAGE_KEY = 'aimall-template-config'

export const useTemplateStore = defineStore('template', () => {
  const isStudioOpen = ref(false)
  const currentPresetId = ref<string>('digital')

  const brand = ref({
    name: 'CyberMall',
    slogan: '硬核算力 · 极客旗舰终端',
    logoBadge: 'CYBER',
    copyright: '© 2026 AI Mall Inc. 专为多行业商城开发定制。',
    icp: '京ICP备20260088号-1',
    phone: '400-888-2026',
    workHours: '周一至周日 09:00 - 22:00',
  })

  const theme = ref({
    primaryColor: '#2563eb',
    priceColor: '#e11d48',
    radius: '10px',
  })

  const slides = ref([...PRESET_DIGITAL.slides])
  const products = ref([...PRESET_DIGITAL.products])
  const sections = ref<TemplateSection[]>([...PRESET_DIGITAL.sections])

  function applyCssVars() {
    const root = document.documentElement
    if (typeof root !== 'undefined' && root.style) {
      root.style.setProperty('--mall-primary', theme.value.primaryColor)
      root.style.setProperty('--el-color-primary', theme.value.primaryColor)
      root.style.setProperty('--mall-price', theme.value.priceColor)
      root.style.setProperty('--mall-radius', theme.value.radius)
    }
  }

  function saveToStorage() {
    try {
      const data = {
        presetId: currentPresetId.value,
        brand: brand.value,
        theme: theme.value,
        slides: slides.value,
        products: products.value,
        sections: sections.value,
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
    } catch {}
  }

  function loadFromStorage() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        const parsed = JSON.parse(saved)
        if (parsed.brand) brand.value = parsed.brand
        if (parsed.theme) theme.value = parsed.theme
        if (parsed.slides) slides.value = parsed.slides
        if (parsed.products) products.value = parsed.products
        if (parsed.sections) sections.value = parsed.sections
        if (parsed.presetId) currentPresetId.value = parsed.presetId
        applyCssVars()
        return true
      }
    } catch {}
    return false
  }

  function applyPreset(presetId: string) {
    const p = PRESETS.find((x) => x.id === presetId) || PRESET_DIGITAL
    currentPresetId.value = p.id
    brand.value.name = p.brandName
    brand.value.slogan = p.slogan
    brand.value.logoBadge = p.logoBadge
    theme.value.primaryColor = p.primaryColor
    theme.value.priceColor = p.priceColor
    theme.value.radius = p.radius
    slides.value = [...p.slides]
    products.value = [...p.products]
    sections.value = JSON.parse(JSON.stringify(p.sections))
    applyCssVars()
    saveToStorage()
  }

  function toggleSection(id: string) {
    const sec = sections.value.find((s) => s.id === id)
    if (sec) {
      sec.enabled = !sec.enabled
      saveToStorage()
    }
  }

  function moveSection(index: number, direction: 'up' | 'down') {
    const targetIdx = direction === 'up' ? index - 1 : index + 1
    if (targetIdx < 0 || targetIdx >= sections.value.length) return
    const temp = sections.value[index]
    sections.value[index] = sections.value[targetIdx]
    sections.value[targetIdx] = temp
    saveToStorage()
  }

  function updateSection(id: string, partial: Partial<TemplateSection>) {
    const sec = sections.value.find((s) => s.id === id)
    if (sec) {
      Object.assign(sec, partial)
      saveToStorage()
    }
  }

  function exportConfigJson(): string {
    return JSON.stringify(
      {
        presetId: currentPresetId.value,
        brand: brand.value,
        theme: theme.value,
        sections: sections.value,
      },
      null,
      2
    )
  }

  function importConfigJson(jsonStr: string): boolean {
    try {
      const parsed = JSON.parse(jsonStr)
      if (parsed.brand) brand.value = parsed.brand
      if (parsed.theme) theme.value = parsed.theme
      if (parsed.sections) sections.value = parsed.sections
      applyCssVars()
      saveToStorage()
      return true
    } catch {
      return false
    }
  }

  function resetDefault() {
    localStorage.removeItem(STORAGE_KEY)
    applyPreset('digital')
  }

  return {
    isStudioOpen,
    presets: PRESETS,
    currentPresetId,
    brand,
    theme,
    slides,
    products,
    sections,
    applyPreset,
    toggleSection,
    moveSection,
    updateSection,
    exportConfigJson,
    importConfigJson,
    resetDefault,
    applyCssVars,
    loadFromStorage,
  }
})
