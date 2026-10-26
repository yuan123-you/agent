import { describe, it, expect } from 'vitest'

// Type-safe dynamic access to Node fs without requiring @types/node in tsconfig
declare const process: { cwd: () => string } | undefined
declare function require(id: string): any

const fs = typeof require === 'function' ? require('fs') : null
const path = typeof require === 'function' ? require('path') : null

describe('Mobile adaptation and performance optimizations', () => {
  const root = typeof process !== 'undefined' && process.cwd ? process.cwd() : '.'
  const read = (relPath: string) => {
    if (!fs || !path) return ''
    return fs.readFileSync(path.resolve(root, relPath), 'utf-8') as string
  }

  it('vite.config.ts splits vendor chunks to prevent large monolithic bundle', () => {
    const viteConfig = read('vite.config.ts')
    expect(viteConfig).toContain('manualChunks')
    expect(viteConfig).toContain('element-plus')
    expect(viteConfig).toContain('vue-vendor')
    expect(viteConfig).toContain('utils-vendor')
  })

  it('nginx configs enable gzip and long-lived asset caching', () => {
    const nginxConf = read('nginx.conf')
    const prodConf = read('../deploy/frontend.production.conf')
    for (const conf of [nginxConf, prodConf]) {
      expect(conf).toContain('gzip on;')
      expect(conf).toContain('gzip_types')
      expect(conf).toContain('location /assets/')
      expect(conf).toContain('max-age=31536000')
    }
  })

  it('index.html includes viewport-fit=cover for mobile display', () => {
    const indexHtml = read('index.html')
    expect(indexHtml).toContain('viewport-fit=cover')
  })

  it('ProductCard has placeholder and fallback (images are inline data URIs, lazy not needed)', () => {
    const cardVue = read('src/components/product/ProductCard.vue')
    expect(cardVue).toContain('#placeholder')
    expect(cardVue).toContain('pic-fallback')
    expect(cardVue).toContain('decoding="async"')
  })

  it('ClientLayout keeps a scrollable nav bar on mobile and hides Tabbar on ProductDetail', () => {
    const clientLayout = read('src/layouts/ClientLayout.vue')
    expect(clientLayout).toContain('isProductDetail')
    expect(clientLayout).toContain('MobileTabbar v-if="!isProductDetail"')
    // 手机端隐藏顶部通栏与全部分类下拉，导航条改为横滑频道条
    expect(clientLayout).toMatch(/@media \(max-width: 768px\)[\s\S]*?\.shop-topbar,[\s\S]*?\.all-cats,/)
    expect(clientLayout).toMatch(/\.nav-links \{[\s\S]*?overflow-x: auto/)
  })

  it('ProductDetailView provides dedicated mobile action bar and responsive layout', () => {
    const detailVue = read('src/views/ProductDetailView.vue')
    expect(detailVue).toContain('mobile-action-bar')
    expect(detailVue).toContain('m-cart-btn')
    expect(detailVue).toContain('m-buy-btn')
    expect(detailVue).toContain(':column="isMobile ? 1 : 2"')
    expect(detailVue).toContain('updateMobile')
  })

  it('ChatView provides adaptive placeholder and mobile padding', () => {
    const chatVue = read('src/views/ChatView.vue')
    expect(chatVue).toContain('inputPlaceholder')
    expect(chatVue).toContain('safe-area-inset-bottom')
  })

  it('ChatView removes the mobile composer bottom gap without duplicating the safe area', () => {
    const chatVue = read('src/views/ChatView.vue')
    const mobileStyles = chatVue.slice(chatVue.lastIndexOf('@media (max-width: 768px)'))
    expect(mobileStyles).toMatch(/\.input-bar\s*\{[^}]*padding: 8px 10px 0;/)
  })

  it('MobileTabbar matches the 56px space reserved by the chat view', () => {
    const tabbar = read('src/components/layout/MobileTabbar.vue')
    expect(tabbar).toContain('height: calc(56px + env(safe-area-inset-bottom));')
    expect(tabbar).toContain('align-items: center;')
  })

  it('ProfileView uses balanced 5-column grid for 5 entries', () => {
    const profileVue = read('src/views/ProfileView.vue')
    expect(profileVue).toContain('repeat(5, 1fr)')
  })

  it('FavoritesView and HistoryView have lazy loading and placeholder', () => {
    const favVue = read('src/views/FavoritesView.vue')
    const hisVue = read('src/views/HistoryView.vue')
    expect(favVue).toContain('lazy')
    expect(favVue).toContain('#placeholder')
    expect(hisVue).toContain('lazy')
    expect(hisVue).toContain('#placeholder')
  })

  it('styles.css prevents iOS zoom-on-focus and optimizes mobile dialogs', () => {
    const css = read('src/styles.css')
    expect(css).toContain('font-size: 16px !important')
    expect(css).toContain('touch-action: manipulation')
    expect(css).toContain('min(520px, calc(100% - 24px))')
  })
})
