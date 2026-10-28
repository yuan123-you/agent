// Isolated visual regression fixture. Never contacts the backend or changes real orders.
import { createApp, h } from 'vue'
import { createRouter, createMemoryHistory } from 'vue-router'
import axios from 'axios'
import type { OrderVO } from '../src/types/api'
import { MASSIVE_PRODUCTS } from '../src/data/products'
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import '../src/styles.css'

const params = new URLSearchParams(location.search)
document.documentElement.classList.toggle('dark', params.has('dark'))
const products = MASSIVE_PRODUCTS.slice(0, 3)
const statuses = ['PENDING_PAYMENT', 'SHIPPED', 'PAID', 'DELIVERED', 'CANCELLED']
const orders: OrderVO[] = statuses.map((status, index) => {
  const product = products[index % products.length]
  return {
    orderId: index + 1, orderNo: `202610281020${String(index + 1).padStart(6, '0')}`,
    status, totalAmount: product.price, createdAt: '2026-10-28T10:20:00',
    source: index === 0 ? 'AI' : 'WEB',
    ...(status === 'SHIPPED' ? { deliveryCompany: '测试物流', logisticsNo: 'TEST202610280002' } : {}),
    items: [{ orderItemId: index + 10, productId: product.id,
      productName: params.has('long') ? 'LongUnbrokenProductName'.repeat(8) : product.name,
      productImage: product.imageUrl, price: product.price, quantity: 1, subtotal: product.price,
      canReview: status === 'DELIVERED', reviewed: false }],
  }
})
let failNext = params.has('error')
axios.defaults.adapter = async config => {
  if (config.url === '/orders/my' && failNext) { failNext = false; throw new Error('Fixture network failure') }
  let data: unknown
  if (config.url === '/orders/my') {
    const records = params.has('empty') ? [] : orders.filter(order => !config.params.status || config.params.status === order.status)
    data = { records, total: records.length, page: 1, size: 10 }
  } else if (config.url?.startsWith('/orders/')) {
    const id = Number(config.url.split('/')[2])
    const order = orders.find(order => order.orderId === id)
    if (order && config.method === 'post') {
      if (config.url.endsWith('/pay')) order.status = 'PAID'
      if (config.url.endsWith('/cancel')) order.status = 'CANCELLED'
      if (config.url.endsWith('/confirm')) order.status = 'DELIVERED'
    }
    data = order
  } else if (config.url?.includes('/reviews')) data = null
  else throw new Error(`Unexpected fixture request: ${config.url}`)
  return { data: { code: 0, data }, status: 200, statusText: 'OK', headers: {}, config }
}
window.fetch = async () => new Response('', { headers: { 'Content-Type': 'text/event-stream' } })
const { default: MyOrdersView } = await import('../src/views/MyOrdersView.vue')
const router = createRouter({ history: createMemoryHistory(), routes: [
  { path: '/orders', component: MyOrdersView },
  { path: '/orders/:id', component: { render: () => h('p', '订单详情跳转成功（测试页面）') } },
  { path: '/assistant', component: { render: () => h('p', '客服页面跳转成功（测试页面）') } },
  { path: '/products/:id?', component: { render: () => h('p', '商品页面跳转成功（测试页面）') } },
] })
const { RouterView } = await import('vue-router')
await router.replace('/orders')
const app = createApp({ render: () => h(RouterView) }).use(router)
app.mount('#app')
