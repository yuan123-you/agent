/** 商品分类常量（首页宫格 / 列表筛选 / 导航共用） */
export interface CategoryDef {
  code: string
  name: string
  icon: string
}

export const CATEGORIES: CategoryDef[] = [
  { code: 'PHONE', name: '手机数码', icon: '📱' },
  { code: 'LAPTOP', name: '电脑办公', icon: '💻' },
  { code: 'APPLIANCE', name: '家用电器', icon: '🧺' },
  { code: 'CLOTHING', name: '服饰内衣', icon: '👕' },
  { code: 'BEAUTY', name: '美妆个护', icon: '💄' },
  { code: 'FOOD', name: '食品生鲜', icon: '🍎' },
  { code: 'MATERNAL', name: '母婴玩具', icon: '🧸' },
  { code: 'SPORTS', name: '运动户外', icon: '⚽' },
  { code: 'BOOK', name: '图书文娱', icon: '📚' },
  { code: 'HOME', name: '家具家居', icon: '🛋️' },
  { code: 'JEWELRY', name: '珠宝饰品', icon: '💎' },
  { code: 'BAGS', name: '箱包', icon: '🎒' },
  { code: 'SHOES', name: '鞋靴', icon: '👟' },
  { code: 'PET', name: '宠物生活', icon: '🐾' },
  { code: 'HEALTH', name: '医疗保健', icon: '🩺' },
  { code: 'CAR', name: '汽车用品', icon: '🚗' },
]

/** 分类编码 → 中文名 */
export function categoryName(code: string): string {
  return CATEGORIES.find((c) => c.code === code)?.name || code
}
