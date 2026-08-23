<template>
  <div class="home" v-loading="loading">
    <!-- 轮播 Banner -->
    <section class="banner-section container">
      <el-carousel :interval="4500" trigger="click" arrow="hover" :height="bannerHeight">
        <el-carousel-item v-for="b in banners" :key="b.title">
          <div class="banner" :style="{ background: b.bg }" @click="$router.push(b.link)">
            <div class="banner-content">
              <h2>{{ b.title }}</h2>
              <p>{{ b.desc }}</p>
              <span class="banner-cta">立即查看 →</span>
            </div>
            <div class="banner-emoji">{{ b.emoji }}</div>
          </div>
        </el-carousel-item>
      </el-carousel>
    </section>

    <!-- 分类宫格 -->
    <section class="container">
      <div class="cat-grid">
        <div v-for="c in CATEGORIES" :key="c.code" class="cat-cell"
          @click="$router.push(`/products?category=${c.code}`)">
          <span class="cat-icon">{{ c.icon }}</span>
          <span class="cat-name">{{ c.name }}</span>
        </div>
      </div>
    </section>

    <!-- AI 助手入口横幅 -->
    <section class="container">
      <div class="ai-entry" @click="$router.push('/assistant')">
        <span class="ai-emoji">🤖</span>
        <div class="ai-text">
          <div class="ai-title">AI 购物助手</div>
          <div class="ai-desc">告诉我想买什么，帮你找商品、查订单、答政策</div>
        </div>
        <el-button type="primary" round>去咨询</el-button>
      </div>
    </section>

    <!-- 商品楼层（按分类） -->
    <section v-for="f in floors" :key="f.code" class="container floor">
      <div class="floor-head">
        <h3>{{ f.icon }} {{ f.name }}</h3>
        <el-button text type="primary" @click="$router.push(`/products?category=${f.code}`)">
          更多 ›
        </el-button>
      </div>
      <div class="floor-grid">
        <ProductCard v-for="p in f.products" :key="p.id" :product="p" />
      </div>
    </section>

    <!-- 猜你喜欢 -->
    <section class="container floor">
      <div class="floor-head">
        <h3>✨ 猜你喜欢</h3>
      </div>
      <div class="floor-grid like-grid">
        <ProductCard v-for="p in likes" :key="p.id" :product="p" />
      </div>
    </section>

    <footer class="home-footer">AI Mall · 智能电商平台 · 演示环境</footer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { apiProducts } from '@/api'
import { CATEGORIES } from '@/constants/categories'
import ProductCard from '@/components/product/ProductCard.vue'
import type { ProductVO } from '@/types/api'

const loading = ref(false)
const windowWidth = ref(window.innerWidth)
const onResize = () => (windowWidth.value = window.innerWidth)
window.addEventListener('resize', onResize)
onUnmounted(() => window.removeEventListener('resize', onResize))

const bannerHeight = computed(() => (windowWidth.value <= 768 ? '140px' : '240px'))

const banners = [
  { title: '数码焕新季', desc: '旗舰影像 · 折上折', emoji: '📱', bg: 'linear-gradient(120deg, #4f7cff, #8f6bff)', link: '/products?category=PHONE' },
  { title: '家电狂欢周', desc: '一级能效 · 以旧换新', emoji: '🧺', bg: 'linear-gradient(120deg, #12b7a3, #48c9b0)', link: '/products?category=APPLIANCE' },
  { title: '生鲜直达', desc: '产地直发 · 新鲜到家', emoji: '🍎', bg: 'linear-gradient(120deg, #ff7a59, #ffb347)', link: '/products?category=FOOD' },
]

// 楼层：4 个主力分类，每层 8 件
const floorCodes = ['PHONE', 'APPLIANCE', 'CLOTHING', 'SPORTS']
const floors = ref<{ code: string; name: string; icon: string; products: ProductVO[] }[]>([])
const likes = ref<ProductVO[]>([])

onMounted(async () => {
  loading.value = true
  try {
    const results = await Promise.all([
      ...floorCodes.map((code) =>
        apiProducts({ category: code, size: 8, sort: 'created_desc' })
          .catch(() => ({ records: [] as ProductVO[] })),
      ),
      apiProducts({ size: 12, sort: 'price_asc' }).catch(() => ({ records: [] as ProductVO[] })),
    ])
    floors.value = floorCodes.map((code, i) => {
      const def = CATEGORIES.find((c) => c.code === code)!
      return { code, name: def.name, icon: def.icon, products: results[i].records }
    })
    likes.value = results[results.length - 1].records
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.home {
  min-height: 100%;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 16px;
  margin-bottom: 24px;
}

.banner {
  height: 100%;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 48px;
  cursor: pointer;
  color: #fff;
  overflow: hidden;
}

.banner-content h2 {
  margin: 0 0 8px;
  font-size: 30px;
}

.banner-content p {
  margin: 0 0 14px;
  opacity: 0.9;
}

.banner-cta {
  font-size: 14px;
  border: 1px solid rgba(255, 255, 255, 0.7);
  padding: 6px 16px;
  border-radius: 16px;
}

.banner-emoji {
  font-size: 88px;
  filter: drop-shadow(0 8px 16px rgba(0, 0, 0, 0.2));
}

/* 分类宫格：PC 10 列，平板 5 列，手机 5 列（两行） */
.cat-grid {
  display: grid;
  grid-template-columns: repeat(10, 1fr);
  gap: 8px;
  background: #fff;
  border-radius: 12px;
  padding: 16px 12px;
}

.cat-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 8px 4px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.cat-cell:hover {
  background: #f5f7fa;
}

.cat-icon {
  font-size: 26px;
}

.cat-name {
  font-size: 12px;
  color: #606266;
}

/* AI 助手入口 */
.ai-entry {
  display: flex;
  align-items: center;
  gap: 14px;
  background: linear-gradient(120deg, #eef3ff, #f6efff);
  border: 1px solid #dde6ff;
  border-radius: 12px;
  padding: 16px 20px;
  cursor: pointer;
}

.ai-emoji {
  font-size: 34px;
}

.ai-text {
  flex: 1;
}

.ai-title {
  font-weight: 700;
  color: var(--el-color-primary);
}

.ai-desc {
  font-size: 13px;
  color: #909399;
  margin-top: 2px;
}

/* 楼层 */
.floor-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.floor-head h3 {
  margin: 0;
  font-size: 18px;
}

.floor-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.like-grid {
  grid-template-columns: repeat(6, 1fr);
}

.home-footer {
  text-align: center;
  color: #c0c4cc;
  font-size: 12px;
  padding: 8px 0 24px;
}

/* 平板 */
@media (max-width: 1024px) {
  .cat-grid {
    grid-template-columns: repeat(5, 1fr);
  }

  .floor-grid {
    grid-template-columns: repeat(3, 1fr);
  }

  .like-grid {
    grid-template-columns: repeat(4, 1fr);
  }

  .banner {
    padding: 0 28px;
  }

  .banner-content h2 {
    font-size: 24px;
  }

  .banner-emoji {
    font-size: 64px;
  }
}

/* 手机 */
@media (max-width: 768px) {
  .container {
    padding: 0 10px;
    margin-bottom: 14px;
  }

  .cat-grid {
    grid-template-columns: repeat(5, 1fr);
    padding: 10px 6px;
  }

  .cat-icon {
    font-size: 22px;
  }

  .floor-grid,
  .like-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }

  .floor-head h3 {
    font-size: 16px;
  }

  .banner {
    padding: 0 20px;
    border-radius: 8px;
  }

  .banner-content h2 {
    font-size: 18px;
    margin-bottom: 4px;
  }

  .banner-content p {
    margin-bottom: 8px;
    font-size: 12px;
  }

  .banner-emoji {
    font-size: 44px;
  }

  .ai-entry {
    padding: 12px 14px;
  }

  .ai-desc {
    display: none;
  }
}
</style>
