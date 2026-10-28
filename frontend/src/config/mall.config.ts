export interface TrustBadgeItem {
  icon: string
  title: string
  desc: string
}

export interface HeroSlideItem {
  id: string
  badge: string
  title: string
  subtitle: string
  ctaText: string
  link: string
  bg: string
  emoji: string
  accentColor?: string
}

export interface BentoCardItem {
  id: string
  span: 'large' | 'small'
  badge: string
  title: string
  desc: string
  ctaText: string
  link: string
  bg: string
  icon: string
}

export interface BrandPartnerItem {
  name: string
  logoText: string
  category: string
}

export interface FooterColumnItem {
  title: string
  links: Array<{ label: string; link?: string }>
}

export interface MallThemeConfig {
  primaryColor: string
  primaryGradient: string
  priceColor: string
  radius: string
  containerWidth: string
}

export interface MallConfig {
  site: {
    name: string
    slogan: string
    logoBadge: string
    tagline: string
    copyright: string
    icp: string
    supportPhone: string
    workHours: string
  }
  theme: {
    activeTheme: 'minimal' | 'tech' | 'classic' | 'emerald' | 'amber'
    presets: Record<string, MallThemeConfig>
  }
  features: {
    enableTrustBar: boolean
    enableBentoPromo: boolean
    enableFlashSale: boolean
    enableCoupons: boolean
    enableAiAssistantPromo: boolean
    enableFloorGoods: boolean
    enableBrandWall: boolean
    enableNewsletter: boolean
  }
  trustBadges: TrustBadgeItem[]
  heroSlides: HeroSlideItem[]
  bentoCards: BentoCardItem[]
  brandPartners: BrandPartnerItem[]
  footerColumns: FooterColumnItem[]
}

export const defaultMallConfig: MallConfig = {
  site: {
    name: 'AI Mall',
    slogan: '极简设计 · 现代商业模版',
    logoBadge: 'AI',
    tagline: '正品好货 · 智能甄选 · 极速履约',
    copyright: '© 2026 AI Mall Inc. 专为多种现代化商城开发而生。',
    icp: '京ICP备20260088号-1',
    supportPhone: '400-888-2026',
    workHours: '周一至周日 09:00 - 22:00',
  },
  theme: {
    activeTheme: 'minimal',
    presets: {
      minimal: {
        primaryColor: '#0f172a',
        primaryGradient: 'linear-gradient(135deg, #0f172a 0%, #334155 100%)',
        priceColor: '#e11d48',
        radius: '10px',
        containerWidth: '1240px',
      },
      tech: {
        primaryColor: '#2563eb',
        primaryGradient: 'linear-gradient(135deg, #2563eb 0%, #4f46e5 100%)',
        priceColor: '#e11d48',
        radius: '12px',
        containerWidth: '1240px',
      },
      classic: {
        primaryColor: '#e4393c',
        primaryGradient: 'linear-gradient(90deg, #e4393c, #f0433f)',
        priceColor: '#e4393c',
        radius: '8px',
        containerWidth: '1200px',
      },
      emerald: {
        primaryColor: '#059669',
        primaryGradient: 'linear-gradient(135deg, #059669 0%, #10b981 100%)',
        priceColor: '#d97706',
        radius: '12px',
        containerWidth: '1240px',
      },
      amber: {
        primaryColor: '#ea580c',
        primaryGradient: 'linear-gradient(135deg, #ea580c 0%, #f97316 100%)',
        priceColor: '#ea580c',
        radius: '10px',
        containerWidth: '1240px',
      },
    },
  },
  features: {
    enableTrustBar: true,
    enableBentoPromo: true,
    enableFlashSale: true,
    enableCoupons: true,
    enableAiAssistantPromo: true,
    enableFloorGoods: true,
    enableBrandWall: true,
    enableNewsletter: true,
  },
  trustBadges: [
    { icon: 'ShieldCheck', title: '正品溯源保障', desc: '100% 官方品牌严选直供' },
    { icon: 'Van', title: '全仓极速发货', desc: '全国智能云仓次日达服务' },
    { icon: 'RefreshRight', title: '退款退换服务', desc: '申请、审核与处理进度可查' },
    { icon: 'ChatLineRound', title: 'AI 智能专属管家', desc: '24小时智能导购与秒级解答' },
  ],
  heroSlides: [
    {
      id: 'slide-1',
      badge: '年度旗舰首发',
      title: '极智科技，灵感无界',
      subtitle: '新一代智能旗舰终端 · 带来颠覆级沉浸性能与工业美学体验',
      ctaText: '立即探索 →',
      link: '/products',
      bg: 'radial-gradient(ellipse at 80% 20%, rgba(56, 189, 248, 0.25), transparent 50%), linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
      emoji: '✨',
      accentColor: '#38bdf8',
    },
    {
      id: 'slide-2',
      badge: '极简空间甄选',
      title: '生活美学，纯粹质感',
      subtitle: '现代居室与高效桌搭方案 · 打造独属于你的松弛生活场域',
      ctaText: '查看合集 →',
      link: '/products',
      bg: 'radial-gradient(ellipse at 80% 20%, rgba(129, 140, 248, 0.25), transparent 50%), linear-gradient(135deg, #1e1b4b 0%, #312e81 100%)',
      emoji: '🛋️',
      accentColor: '#a5b4fc',
    },
    {
      id: 'slide-3',
      badge: '原产地冷链直达',
      title: '天然生鲜，四季尝鲜',
      subtitle: '严选高海拔有机生态基地 · 恒温冷链24小时锁鲜到家',
      ctaText: '抢鲜尝鲜 →',
      link: '/products',
      bg: 'radial-gradient(ellipse at 80% 20%, rgba(52, 211, 153, 0.25), transparent 50%), linear-gradient(135deg, #064e3b 0%, #065f46 100%)',
      emoji: '🍏',
      accentColor: '#34d399',
    },
  ],
  bentoCards: [
    {
      id: 'bento-1',
      span: 'large',
      badge: 'NEW ARRIVALS · 尖端首选',
      title: 'AI 智慧生活前沿馆',
      desc: '汇聚前沿智能穿戴、机器人伙伴与深度生产力神器',
      ctaText: '浏览精选专区',
      link: '/products',
      bg: 'linear-gradient(135deg, #090d16 0%, #1e293b 100%)',
      icon: '🤖',
    },
    {
      id: 'bento-2',
      span: 'small',
      badge: 'TOP 榜单',
      title: '口碑热卖巅峰榜',
      desc: '万千买家真实好评回购',
      ctaText: '查看榜单',
      link: '/products',
      bg: 'linear-gradient(135deg, #1c1917 0%, #292524 100%)',
      icon: '🔥',
    },
    {
      id: 'bento-3',
      span: 'small',
      badge: 'DESK SETUP',
      title: '极简生产力桌搭',
      desc: '无线办公与声学美学',
      ctaText: '进入选购',
      link: '/products',
      bg: 'linear-gradient(135deg, #1e1b4b 0%, #172554 100%)',
      icon: '⚡',
    },
    {
      id: 'bento-4',
      span: 'large',
      badge: 'BENEFITS · 限时礼遇',
      title: '全场会员特惠领券中心',
      desc: '新客立享满减叠加抵扣券，领券立省，下单更划算',
      ctaText: '立即一键领券',
      link: '/coupons',
      bg: 'linear-gradient(135deg, #311317 0%, #4c0519 100%)',
      icon: '🎫',
    },
  ],
  brandPartners: [
    { name: 'Apple', logoText: 'Apple', category: '数码旗舰' },
    { name: 'Sony', logoText: 'SONY', category: '影音视听' },
    { name: 'Dyson', logoText: 'dyson', category: '高端生活' },
    { name: 'Bose', logoText: 'BOSE', category: '声学大师' },
    { name: 'Muji', logoText: 'MUJI', category: '极简居家' },
    { name: 'Herman Miller', logoText: 'Herman Miller', category: '人体工学' },
    { name: 'Keychron', logoText: 'Keychron', category: '客制化外设' },
    { name: 'Anker', logoText: 'ANKER', category: '充电储能' },
  ],
  footerColumns: [
    {
      title: '购物指南',
      links: [
        { label: '购物流程' },
        { label: '会员权益' },
        { label: '优惠券使用' },
        { label: '常见问题' },
      ],
    },
    {
      title: '配送方式',
      links: [
        { label: '全国闪电仓配' },
        { label: '配送费收费标准' },
        { label: '包裹签收与验货' },
        { label: '物流追踪说明' },
      ],
    },
    {
      title: '售后保障',
      links: [
        { label: '退款与退换货说明' },
        { label: '退款 / 售后进度' },
        { label: '保修与品质承诺' },
        { label: '发票开具服务' },
      ],
    },
    {
      title: '商务与开发者',
      links: [
        { label: '卖家入驻' },
        { label: '开放平台 API' },
        { label: '模版多端定制' },
        { label: '开源项目规范' },
      ],
    },
  ],
}
