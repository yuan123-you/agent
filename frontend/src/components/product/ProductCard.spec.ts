import { afterEach, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, reactive, type App } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import ProductCard from './ProductCard.vue'

// Match the image-component boundary with either global or on-demand registration.
vi.mock('element-plus/es/components/base/style/css', () => ({}))
vi.mock('element-plus/es/components/image/style/css', () => ({}))
vi.mock('element-plus/es', async () => {
  const { defineComponent, h } = await import('vue')
  return { ElImage: defineComponent({ props: ['src'], setup: props => () => h('img', { src: props.src }) }) }
})

let app: App | undefined
let host: HTMLDivElement | undefined
afterEach(() => { app?.unmount(); host?.remove() })

it('passes the original product image URL to the image component and updates when the product changes', async () => {
  const product = reactive({ id: 7, name: '商品', category: 'PHONE', brand: '品牌', price: 99, imageUrl: '/api/v1/product-images/catalog/original.webp' })
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { template: '<div />' } }] })
  host = document.createElement('div')
  document.body.appendChild(host)
  app = createApp({ render: () => h(ProductCard, { product }) }).use(router)
  app.component('ElImage', defineComponent({ props: ['src'], setup: props => () => h('img', { src: props.src }) }))
  app.mount(host)
  expect(host.querySelector('img')?.getAttribute('src')).toBe('/api/v1/product-images/catalog/original.webp')
  product.imageUrl = 'data:image/svg+xml,%3Csvg%20xmlns="http://www.w3.org/2000/svg"/%3E'
  await nextTick()
  expect(host.querySelector('img')?.getAttribute('src')).toBe(product.imageUrl)
})
