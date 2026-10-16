import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

describe('Mobile adaptation and performance optimizations', () => {
  const root = resolve(__dirname, '..')

  it('vite.config.ts splits vendor chunks to prevent large monolithic bundle', () => {
    const viteConfig = readFileSync(resolve(root, 'vite.config.ts'), 'utf-8')
    expect(viteConfig).toContain('manualChunks')
    expect(viteConfig).toContain('element-plus')
    expect(viteConfig).toContain('vue-vendor')
    expect(viteConfig).toContain('utils-vendor')
  })

  it('nginx configs enable gzip and long-lived asset caching', () => {
    const nginxConf = readFileSync(resolve(root, 'nginx.conf'), 'utf-8')
    const prodConf = readFileSync(resolve(root, '../deploy/frontend.production.conf'), 'utf-8')
    for (const conf of [nginxConf, prodConf]) {
      expect(conf).toContain('gzip on;')
      expect(conf).toContain('gzip_types')
      expect(conf).toContain('location /assets/')
      expect(conf).toContain('max-age=31536000')
    }
  })

  it('index.html includes viewport-fit=cover for mobile display', () => {
    const indexHtml = readFileSync(resolve(root, 'index.html'), 'utf-8')
    expect(indexHtml).toContain('viewport-fit=cover')
  })

  it('ProductCard has lazy loading and placeholder to avoid blocking network', () => {
    const cardVue = readFileSync(resolve(__dirname, 'components/product/ProductCard.vue'), 'utf-8')
    expect(cardVue).toContain('lazy')
    expect(cardVue).toContain('#placeholder')
    expect(cardVue).toContain('pic-fallback')
  })

  it('ClientLayout provides horizontal scrolling category bar and hides Tabbar on ProductDetail', () => {
    const clientLayout = readFileSync(resolve(__dirname, 'layouts/ClientLayout.vue'), 'utf-8')
    expect(clientLayout).toContain('isProductDetail')
    expect(clientLayout).toContain('MobileTabbar v-if="!isProductDetail"')
    expect(clientLayout).toContain('overflow-x: auto')
    expect(clientLayout).toContain('-webkit-overflow-scrolling: touch')
  })

  it('ProductDetailView provides dedicated mobile action bar and responsive layout', () => {
    const detailVue = readFileSync(resolve(__dirname, 'views/ProductDetailView.vue'), 'utf-8')
    expect(detailVue).toContain('mobile-action-bar')
    expect(detailVue).toContain('m-cart-btn')
    expect(detailVue).toContain('m-buy-btn')
    expect(detailVue).toContain(':column="isMobile ? 1 : 2"')
    expect(detailVue).toContain('updateMobile')
  })

  it('ChatView provides adaptive placeholder and mobile padding', () => {
    const chatVue = readFileSync(resolve(__dirname, 'views/ChatView.vue'), 'utf-8')
    expect(chatVue).toContain('inputPlaceholder')
    expect(chatVue).toContain('safe-area-inset-bottom')
  })

  it('ProfileView uses balanced 5-column grid for 5 entries', () => {
    const profileVue = readFileSync(resolve(__dirname, 'views/ProfileView.vue'), 'utf-8')
    expect(profileVue).toContain('repeat(5, 1fr)')
  })
  it('FavoritesView and HistoryView have lazy loading and placeholder', () => {
    const favVue = readFileSync(resolve(__dirname, 'views/FavoritesView.vue'), 'utf-8')
    const hisVue = readFileSync(resolve(__dirname, 'views/HistoryView.vue'), 'utf-8')
    expect(favVue).toContain('lazy')
    expect(favVue).toContain('#placeholder')
    expect(hisVue).toContain('lazy')
    expect(hisVue).toContain('#placeholder')
  })

  it('styles.css prevents iOS zoom-on-focus and optimizes mobile dialogs', () => {
    const css = readFileSync(resolve(__dirname, 'styles.css'), 'utf-8')
    expect(css).toContain('font-size: 16px !important')
    expect(css).toContain('touch-action: manipulation')
    expect(css).toContain('min(520px, calc(100% - 24px))')
  })
})

