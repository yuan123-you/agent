// Isolated browser fixture: never calls the backend or reads real login/cart data.
import { createApp, h } from 'vue'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import axios from 'axios'
import { MASSIVE_PRODUCTS } from '../src/data/products'
import type { CartRow } from '../src/api'
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import '../src/styles.css'

const params = new URLSearchParams(location.search)
document.documentElement.classList.toggle('dark', params.has('dark'))
const storage = new Map<string, string>()
Object.defineProperty(window, 'localStorage', { value: {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, String(value)),
  removeItem: (key: string) => storage.delete(key), clear: () => storage.clear(),
  key: (index: number) => [...storage.keys()][index] ?? null,
  get length() { return storage.size },
} })
const products = MASSIVE_PRODUCTS.slice(0, 8).map(product => ({ ...product, sellingPoints: undefined }))
let rows: CartRow[] = params.has('empty') ? [] : products.slice(0, 3).map((product, index) => ({
  cartItemId: index + 1, productId: product.id,
  name: params.has('long') ? 'LongUnbrokenProductName'.repeat(8) : product.name,
  imageUrl: product.imageUrl, price: params.has('long') ? 999999.99 : product.price,
  quantity: 1, checked: index === 2 ? 0 : 1, stock: 8, subtotal: product.price,
  skuSp: JSON.stringify([{ key: '规格', value: ['原色钛金属 / 256GB', '黑色 / 标准版', '钛金属 / 标准版'][index] }]),
}))
let failRecommendations = params.has('error')
axios.defaults.adapter = async config => {
  let data: unknown
  const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
  if (config.url === '/cart/check-all') {
    rows.forEach(row => { row.checked = body.checked ? 1 : 0 })
  } else if (config.url?.startsWith('/cart/items/')) {
    const id = Number(config.url.split('/').pop())
    if (config.method === 'delete') rows = rows.filter(row => row.cartItemId !== id)
    else {
      const row = rows.find(row => row.cartItemId === id)!
      if (body.checked !== undefined) row.checked = body.checked ? 1 : 0
      if (body.quantity !== undefined) row.quantity = body.quantity
    }
  } else if (config.url === '/cart') data = {
    items: rows.map(row => ({ ...row })),
    totalAmount: rows.filter(row => row.checked === 1).reduce((sum, row) => sum + row.price * row.quantity, 0),
    checkedCount: rows.filter(row => row.checked === 1).length,
  }
  else if (config.url === '/products') {
    if (failRecommendations) { failRecommendations = false; throw new Error('Fixture recommendation error') }
    data = { records: products, total: products.length, page: 1, size: 8 }
  } else throw new Error('Unexpected fixture request: ' + config.url)
  return { data: { code: 0, data }, status: 200, statusText: 'OK', headers: {}, config }
}
const [{ default: ClientLayout }, { default: CartView }] = await Promise.all([
  import('../src/layouts/ClientLayout.vue'), import('../src/views/CartView.vue'),
])
const target = (text: string) => ({ render: () => h('p', { style: 'padding:24px' }, text + '（隔离测试页面）') })
const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: ClientLayout, children: [
  { path: '', component: target('首页') }, { path: 'cart', component: CartView },
  { path: 'order/confirm', component: target('订单确认跳转成功') },
  { path: 'products/:id', component: target('商品详情跳转成功') },
  { path: 'coupons', component: target('领券中心跳转成功') },
] }] })
await router.replace('/cart')
createApp({ render: () => h(RouterView) }).use(createPinia()).use(router).mount('#app')
