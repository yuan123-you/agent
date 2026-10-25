export interface SubCategoryItem {
  name: string
  icon: string
  keyword: string
}

export interface SubGroup {
  title: string
  items: SubCategoryItem[]
}

export interface MainCategoryDetail {
  code: string
  name: string
  icon: string
  tagline: string
  subGroups: SubGroup[]
}

export const DETAILED_CATEGORIES: MainCategoryDetail[] = [
  {
    code: 'PHONE',
    name: '手机数码',
    icon: '📱',
    tagline: '前沿算力 · 移动影像终端',
    subGroups: [
      {
        title: '手机通讯',
        items: [
          { name: '智能手机', icon: '📱', keyword: '手机' },
          { name: '折叠屏旗舰', icon: '📲', keyword: '折叠屏' },
          { name: '游戏手机', icon: '🎮', keyword: '游戏手机' },
          { name: '5G全网通', icon: '📶', keyword: '5G' },
        ],
      },
      {
        title: '影音娱乐',
        items: [
          { name: '降噪耳机', icon: '🎧', keyword: '降噪耳机' },
          { name: '真无线蓝牙', icon: '🎵', keyword: '蓝牙耳机' },
          { name: '智能手表', icon: '⌚', keyword: '手表' },
          { name: '航拍无人机', icon: '🛸', keyword: '无人机' },
        ],
      },
      {
        title: '数码外设',
        items: [
          { name: '桌面超能充', icon: '🔌', keyword: '充电' },
          { name: '磁吸充电宝', icon: '🔋', keyword: '充电宝' },
          { name: '云台稳定器', icon: '📹', keyword: '云台' },
          { name: '数码保护套', icon: '💼', keyword: '保护套' },
        ],
      },
    ],
  },
  {
    code: 'LAPTOP',
    name: '电脑办公',
    icon: '💻',
    tagline: '生产力工具 · 客制化外设',
    subGroups: [
      {
        title: '电脑主机',
        items: [
          { name: '轻薄笔记本', icon: '💻', keyword: '笔记本' },
          { name: '游戏笔记本', icon: '🕹️', keyword: '游戏本' },
          { name: '迷你主机', icon: '🖥️', keyword: '主机' },
          { name: '视网膜显示器', icon: '📺', keyword: '显示器' },
        ],
      },
      {
        title: '外设键盘',
        items: [
          { name: '机械键盘', icon: '⌨️', keyword: '键盘' },
          { name: '双模无线鼠标', icon: '🖱️', keyword: '鼠标' },
          { name: '客制化轴体', icon: '⚙️', keyword: '轴体' },
          { name: '多功能拓展坞', icon: '🔌', keyword: '拓展坞' },
        ],
      },
    ],
  },
  {
    code: 'APPLIANCE',
    name: '家用电器',
    icon: '🧺',
    tagline: '生活美学 · 智能居家电器',
    subGroups: [
      {
        title: '环境生活',
        items: [
          { name: '空气净化风扇', icon: '🌀', keyword: '净化器' },
          { name: '扫拖一体机', icon: '🤖', keyword: '扫地机' },
          { name: '除螨吸尘器', icon: '🧹', keyword: '吸尘器' },
          { name: '变频除湿机', icon: '💧', keyword: '除湿机' },
        ],
      },
      {
        title: '品质厨房',
        items: [
          { name: '意式咖啡机', icon: '☕', keyword: '咖啡机' },
          { name: '低速慢汁机', icon: '🍹', keyword: '榨汁机' },
          { name: '微蒸烤一体机', icon: '🍳', keyword: '烤箱' },
          { name: '智能电水壶', icon: '🫖', keyword: '水壶' },
        ],
      },
    ],
  },
  {
    code: 'CLOTHING',
    name: '潮流服饰',
    icon: '👕',
    tagline: '轻奢极简 · 高质感穿着',
    subGroups: [
      {
        title: '当季精选',
        items: [
          { name: '重磅纯棉卫衣', icon: '🧥', keyword: '卫衣' },
          { name: '专业户外冲锋衣', icon: '🧗', keyword: '冲锋衣' },
          { name: '休闲弹力长裤', icon: '👖', keyword: '休闲裤' },
          { name: '法式针织羊绒', icon: '🧶', keyword: '羊绒' },
        ],
      },
      {
        title: '品质贴身',
        items: [
          { name: '新疆长绒棉T恤', icon: '👕', keyword: 'T恤' },
          { name: '速干运动内着', icon: '🎽', keyword: '速干' },
          { name: '无痕内衣家居', icon: '🩳', keyword: '内衣' },
          { name: '天然羊毛保暖袜', icon: '🧦', keyword: '袜子' },
        ],
      },
    ],
  },
  {
    code: 'BEAUTY',
    name: '美妆个护',
    icon: '💄',
    tagline: '精准修护 · 沙龙香氛与护理',
    subGroups: [
      {
        title: '面部护理',
        items: [
          { name: '修护精华露', icon: '🧪', keyword: '精华' },
          { name: '高倍防晒乳', icon: '☀️', keyword: '防晒' },
          { name: '紧致抗皱眼霜', icon: '👁️', keyword: '眼霜' },
          { name: '温和氨基酸洁面', icon: '🫧', keyword: '洁面' },
        ],
      },
      {
        title: '香氛美发',
        items: [
          { name: '高定小众香水', icon: '💐', keyword: '香水' },
          { name: '温控负离子吹风', icon: '💨', keyword: '吹风机' },
          { name: '声波电动牙刷', icon: '🪥', keyword: '牙刷' },
          { name: '精油头皮养护', icon: '🧴', keyword: '洗发' },
        ],
      },
    ],
  },
  {
    code: 'FOOD',
    name: '食品生鲜',
    icon: '🍎',
    tagline: '原产地冷链 · 新鲜直达',
    subGroups: [
      {
        title: '新鲜原产',
        items: [
          { name: '原箱进口车厘子', icon: '🍒', keyword: '车厘子' },
          { name: '原切眼肉牛排', icon: '🥩', keyword: '牛排' },
          { name: '深海大虾海鲜', icon: '🦐', keyword: '大虾' },
          { name: '云南挂耳黑咖啡', icon: '☕', keyword: '咖啡' },
        ],
      },
      {
        title: '美味零食',
        items: [
          { name: '每日坚果大礼包', icon: '🥜', keyword: '坚果' },
          { name: '纯黑生巧克力', icon: '🍫', keyword: '巧克力' },
          { name: '精品精酿原浆啤酒', icon: '🍺', keyword: '啤酒' },
          { name: '低温烘焙燕麦片', icon: '🥣', keyword: '麦片' },
        ],
      },
    ],
  },
  {
    code: 'HOME',
    name: '居家生活',
    icon: '🛋️',
    tagline: '极简空间 · 人体工学与居室美学',
    subGroups: [
      {
        title: '办公家具',
        items: [
          { name: '人体工学办公椅', icon: '🪑', keyword: '人体工学' },
          { name: '电动升降实木桌', icon: '🪵', keyword: '升降桌' },
          { name: '桌面实木置物架', icon: '📐', keyword: '置物架' },
          { name: '护眼屏幕挂灯', icon: '💡', keyword: '挂灯' },
        ],
      },
      {
        title: '居室香氛布艺',
        items: [
          { name: '天然大豆香薰蜡烛', icon: '🕯️', keyword: '香薰' },
          { name: '埃及长绒棉四件套', icon: '🛏️', keyword: '四件套' },
          { name: '超细纤维吸水浴巾', icon: '🧖', keyword: '浴巾' },
          { name: '超声波静音加湿器', icon: '🌫️', keyword: '加湿器' },
        ],
      },
    ],
  },
  {
    code: 'SPORTS',
    name: '运动户外',
    icon: '⚽',
    tagline: '山系野趣 · 轻量专业户外',
    subGroups: [
      {
        title: '户外露营',
        items: [
          { name: '轻量山系越野鞋', icon: '👟', keyword: '越野鞋' },
          { name: '超轻纯钛露营杯', icon: '🏕️', keyword: '纯钛' },
          { name: '铝合金蛋卷折叠桌', icon: '⛺', keyword: '露营' },
          { name: '鹅绒超轻木乃伊睡袋', icon: '🪶', keyword: '睡袋' },
        ],
      },
    ],
  },
  {
    code: 'BAGS',
    name: '鞋靴箱包',
    icon: '🎒',
    tagline: '高质感皮具 · 旅行出行',
    subGroups: [
      {
        title: '箱包配饰',
        items: [
          { name: '铝镁合金登机箱', icon: '🧳', keyword: '拉杆箱' },
          { name: '头层牛皮托特包', icon: '👜', keyword: '托特包' },
          { name: '机能防水双肩包', icon: '🎒', keyword: '双肩包' },
          { name: '德训复古休闲鞋', icon: '👟', keyword: '德训鞋' },
        ],
      },
    ],
  },
]
