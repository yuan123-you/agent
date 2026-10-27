export {}

// Browser regression harness: open /tests/layout.html with the Vite dev server.
// Fixtures stay here, never in production code or against a live backend.
const params = new URLSearchParams(location.search)
const routes = ['/', '/products', '/products/1', '/orders', '/orders/1', '/addresses',
  '/cart', '/favorites', '/history', '/profile', '/assistant', '/assistant/1',
  '/merchant/products', '/merchant/reviews', '/admin/dashboard', '/admin/products',
  '/admin/orders', '/admin/kb', '/admin/users', '/admin/stats', '/workbench',
  '/workbench/conv/1', '/login', '/403', '/not-found',
  '/admin/products?layoutAction=新建商品', '/admin/kb?layoutAction=上传文档',
  '/merchant/products?layoutAction=按模板上架', '/addresses?layoutAction=新增地址',
  '/cart?layoutAction=结算', '/products/1?layoutAction=立即购买',
  '/login?layoutAction=注册', '/products/1?layoutAction=立即购买>确定']

if (!params.has('case')) {
  const results: unknown[] = []
  const output = document.querySelector('#results')!
  for (const width of (params.has('width') ? [Number(params.get('width'))] : [320, 375, 768, 1280])) {
    for (const path of (params.has('route') ? [params.get('route')!] : routes)) {
      const frame = document.createElement('iframe')
      frame.style.cssText = `width:${width}px;height:800px;border:0;display:block`
      const result = new Promise(resolve => {
        const timer = setTimeout(() => { window.removeEventListener('message', receive); resolve({ width, path, error: 'timeout' }) }, 20000)
        function receive(event: MessageEvent) {
          if (event.source !== frame.contentWindow) return
          clearTimeout(timer)
          window.removeEventListener('message', receive)
          resolve({ width, path, ...event.data })
        }
        window.addEventListener('message', receive)
      })
      frame.src = `/tests/layout.html?case=${encodeURIComponent(path)}`
      document.body.append(frame)
      results.push(await result)
      frame.remove()
      const failures = results.filter((r: any) => r.error || r.overflow?.length)
      output.textContent = JSON.stringify({ done: results.length, total: (params.has('route') ? 1 : routes.length) * (params.has('width') ? 1 : 4), failures }, null, 2)
    }
  }
  output.setAttribute('data-complete', 'true')
} else {
  const errors: string[] = []
  window.addEventListener('error', e => errors.push(e.message))
  window.addEventListener('unhandledrejection', e => errors.push(String(e.reason)))
  const [{ createApp }, { createPinia }, { default: axios }] = await Promise.all([
    import('vue'), import('pinia'), import('axios'),
  ])
  await import('element-plus/es/components/message/style/css')
  await import('element-plus/es/components/message-box/style/css')
  await import('element-plus/theme-chalk/dark/css-vars.css')
  await import('../src/styles.css')
  // Isolate authentication fixtures from the developer's real login state.
  const storage = new Map<string, string>()
  Object.defineProperty(window, 'localStorage', { value: {
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => storage.set(key, String(value)),
    removeItem: (key: string) => storage.delete(key),
    clear: () => storage.clear(),
    key: (index: number) => [...storage.keys()][index] ?? null,
    get length() { return storage.size },
  } })
  const path = params.get('case')!
  const user = { userId: 1, username: 'layout-test', nickname: '布局测试用户', role:
    path.startsWith('/admin') ? 'ADMIN' : path.startsWith('/merchant') ? 'MERCHANT' : path.startsWith('/workbench') ? 'AGENT' : 'CUSTOMER' }
  if (!path.startsWith('/login')) {
    localStorage.setItem('token', 'layout-test-only')
    localStorage.setItem('user', JSON.stringify(user))
  } else { localStorage.removeItem('token'); localStorage.removeItem('user') }
  const long = 'LongUnbrokenProductName'.repeat(8)
  const product = { id: 1, name: long, category: '数码', brand: '测试品牌', price: 9999.99,
    stock: 1000, sellingPoints: long, description: long, specs: '标准', status: 'ON_SALE', time: '2026-10-15T10:00:00' }
  const order = { orderId: 1, orderNo: 'ORDER2026101512345678901234567890', status: 'PENDING_PAYMENT',
    totalAmount: 9999.99, createdAt: '2026-10-15 10:00:00', receiverName: '测试收件人',
    receiverPhone: '13800000000', receiverAddress: long, items: [{ productId: 1, productName: long, price: 9999.99, quantity: 1, subtotal: 9999.99 }] }
  const conv = { conversationId: 1, title: long, userNickname: '测试买家', status: 'ACTIVE', summary: long, createdAt: '2026-10-15T10:00:00' }
  const page = (records: unknown[]) => ({ records, total: records.length, page: 1, size: 20 })
  const fixture = (url: string): unknown => {
    if (url === '/auth/me') return user
    if (url === '/history/1') return null
    if (url === '/products/categories') return ['数码', '服装', '日用']
    if (/^\/products\/\d+$/.test(url)) return product
    if (/^\/orders\/\d+$/.test(url)) return order
    if (url === '/cart') return { items: [{ ...product, cartItemId: 1, productId: 1, quantity: 1, checked: 1, subtotal: 9999.99 }], totalAmount: 9999.99, checkedCount: 1 }
    if (url === '/addresses') return [{ addressId: 1, receiverName: '测试收件人', receiverPhone: '13800000000', receiverAddress: long, isDefault: true }]
    if (url === '/merchant/profile') return { shopName: '测试店铺', onSaleCount: 1, totalProducts: 1 }
    if (url.endsWith('/status')) return { favorited: false, status: 'ACTIVE' }
    if (url.includes('/messages')) return url.endsWith('/after') ? [] : page([{ messageId: 1, role: 'USER', content: long }, { messageId: 2, role: 'AI', content: `链接 ${long}\n\n\`\`\`text\n${long}\n\`\`\`\n\n|参数|说明|\n|---|---|\n|${long}|${long}|` }])
    if (/\/conversations\/\d+$/.test(url)) return conv
    if (url.includes('pending') || url.includes('servicing')) return [conv]
    if (url.includes('sla')) return { pendingCount: 1, servicingCount: 1, todayNewCount: 1, todayHandledCount: 1, avgFirstResponseSeconds: 61 }
    if (url.includes('dashboard')) return {}
    if (url.includes('stats')) return { todayConversationCount: 1, todayAiMessageCount: 1, topQuestions: [{ keyword: long, count: 1 }], aiToolCalls: { product_search: 1 } }
    if (url.includes('conversations')) return page([conv])
    if (url.includes('reviews')) return page([{ reviewId: 1, productId: 1, productName: long, nickname: '测试买家', rating: 5, content: long, merchantReply: long, createdAt: '2026-10-15' }])
    if (url.includes('orders')) return page([order])
    if (url.includes('products') || url === '/history' || url === '/favorites') return page([product])
    if (url.includes('users')) return page([user])
    if (url.includes('/kb')) return page([{ docId: 1, title: long, docType: 'FAQ', fileFormat: 'TEXT', status: 'ACTIVE', chunkCount: 1, version: 1 }])
    errors.push(`Missing fixture: ${url}`)
    return {}
  }
  axios.defaults.adapter = async config => ({ data: { code: 0, data: fixture(config.url || '') }, status: 200, statusText: 'OK', headers: {}, config })
  // No real SSE requests from the test page.
  window.fetch = async () => new Response('', { headers: { 'Content-Type': 'text/event-stream' } })
  const { default: router } = await import('../src/router')
  const { default: App } = await import('../src/App.vue')
  document.body.innerHTML = '<div id="app"></div>'
  const app = createApp(App).use(createPinia()).use(router)
  app.config.errorHandler = error => errors.push(String(error))
  app.config.warnHandler = message => {
    if (/Failed to resolve (component|directive)/.test(message)) errors.push(message)
  }
  await router.replace(path)
  await router.isReady()
  app.mount('#app')
  await new Promise(resolve => setTimeout(resolve, 500))
  await document.fonts.ready
  const action = new URL(path, location.origin).searchParams.get('layoutAction')
  for (const step of action?.split('>') || []) {
    const button = [...document.querySelectorAll<HTMLElement>('button, [role="tab"]')]
      .find(el => el.textContent?.includes(step))
    if (!button) errors.push(`Missing action: ${step}`)
    else button.click()
    await new Promise(resolve => setTimeout(resolve, 400))
    if (step !== '注册' && !document.querySelector('.el-dialog')) errors.push(`Dialog did not open: ${step}`)
  }
  const overflow = [...document.querySelectorAll<HTMLElement>('html, body, body *')]
    .filter(el => getComputedStyle(el).visibility !== 'hidden' && el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 1 &&
      // Table/tab internals may scroll locally; carousel/step connectors extend by design.
      // Their ancestor scroll containers are still checked for page-level overflow.
      !el.closest('.el-table, .el-tabs__nav-wrap, .el-carousel, .el-step') &&
      getComputedStyle(el).overflowX !== 'hidden' && getComputedStyle(el).overflowX !== 'clip')
    .map(el => ({ element: `${el.tagName.toLowerCase()}.${String(el.className).replaceAll(' ', '.')}`, width: el.clientWidth, scrollWidth: el.scrollWidth }))
  parent.postMessage({ overflow, ...(errors.length ? { error: errors.join('; ') } : {}) }, location.origin)
}
