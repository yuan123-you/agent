import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import ElementPlus, { ElMessage } from 'element-plus'
import ProductDetailView from './ProductDetailView.vue'

const api = vi.hoisted(() => ({
  apiProductDetail: vi.fn(), apiCatalogProductSkus: vi.fn(), apiReviews: vi.fn(),
  apiFavoriteStatus: vi.fn(), apiFavoriteToggle: vi.fn(), apiHistoryRecord: vi.fn(), apiSeckills: vi.fn(),
  apiCartAdd: vi.fn(), apiCartList: vi.fn(), apiCartRemove: vi.fn(), apiCartUpdate: vi.fn(),
}))
vi.mock('@/api', () => api)
const auth = vi.hoisted(() => ({ isCustomer: false }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))

let app: App
let host: HTMLDivElement
let router: Router
const flush = async () => {
  for (let i = 0; i < 16; i++) await nextTick()
  await new Promise(resolve => setTimeout(resolve, 0))
  await nextTick()
}
const product = (id: number) => ({
  id, name: `真实商品${id}`, price: id * 10, stock: 8, category: 'PHONE', brand: '真实品牌',
  imageUrl: `/product-${id}.png`, description: `商品${id}的真实描述`,
})
const review = (id: number) => ({
  reviewId: id, nickname: `买家${id}`, rating: 3, content: `商品${id}的真实评价`,
  specInfo: '真实规格', createdAt: '2026-10-20T10:00:00', merchantReply: `商品${id}的真实回复`,
})
const page = (id?: number) => ({
  records: id == null ? [] : [review(id)], total: id == null ? 0 : 1, page: 1, size: 10,
  avgRating: id == null ? 0 : 3, ratingDistribution: {},
})
const sku = (id: number) => ({
  id: id * 100, productId: id, price: id * 10 + 1, stock: 4, status: 'ON_SALE',
  spData: JSON.stringify([{ key: '颜色', value: `商品${id}专用色` }]),
})
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}
async function mountPage(id = 41) {
  router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/products/:id', component: ProductDetailView },
    { path: '/cart', component: { template: '<div class="test-cart-page">购物车</div>' } },
    { path: '/login', component: { template: '<div>登录</div>' } },
    { path: '/coupons', component: { template: '<div>真实领券中心</div>' } },
  ] })
  await router.push(`/products/${id}`)
  await router.isReady()
  app = createApp(RouterView).use(createPinia()).use(router).use(ElementPlus)
  app.mount(host)
  await flush()
}
function retry(selector: string) {
  const button = host.querySelector<HTMLButtonElement>(`${selector} button`)
  expect(button, `${selector} must offer a retry button`).not.toBeNull()
  expect(button!.textContent).toContain('重试')
  button!.click()
}
function expectNoReviews() {
  expect(host.querySelectorAll('.review-item-row')).toHaveLength(0)
  expect(host.textContent).not.toContain('科技先锋买家')
  expect(host.textContent).not.toContain('数码发烧友')
}

beforeEach(() => {
  vi.resetAllMocks()
  auth.isCustomer = false
  api.apiProductDetail.mockImplementation(async (id: number) => product(id))
  api.apiCatalogProductSkus.mockResolvedValue([])
  api.apiReviews.mockResolvedValue(page())
  api.apiHistoryRecord.mockResolvedValue(undefined)
  api.apiFavoriteStatus.mockResolvedValue({ favorited: false })
  api.apiFavoriteToggle.mockResolvedValue({ favorited: true })
  api.apiCartAdd.mockResolvedValue(undefined)
  api.apiCartList.mockResolvedValue({ items: [], totalAmount: 0, checkedCount: 0 })
  host = document.createElement('div')
  document.body.appendChild(host)
})
afterEach(() => { app?.unmount(); host.remove(); ElMessage.closeAll() })

describe('真实买家评价', () => {
  it('接口失败展示失败和重试，而不是伪造五星评价', async () => {
    api.apiReviews.mockRejectedValue(new Error('offline'))
    await mountPage()
    expectNoReviews()
    expect(host.querySelector('.review-error')?.textContent).toContain('评价加载失败')
    retry('.review-error')
    await flush()
    expectNoReviews()
  })

  it('真实空列表显示暂无评价，不展示固定好评率或好评标签', async () => {
    await mountPage()
    expectNoReviews()
    expect(host.querySelector('.reviews-list')?.textContent).toContain('暂无评价')
    expect(host.querySelector('.review-error')).toBeNull()
    expect(host.textContent).not.toContain('99.4%')
    expect(host.querySelector('.review-tag-chips')?.textContent).not.toContain('音质好评')
  })

  it('只展示接口返回的评价、评分与商家回复', async () => {
    api.apiReviews.mockResolvedValue(page(41))
    await mountPage()
    expect(host.querySelectorAll('.review-item-row')).toHaveLength(1)
    expect(host.querySelector('.ri-content')?.textContent).toBe('商品41的真实评价')
    expect(host.querySelector('.ri-merchant-reply')?.textContent).toContain('商品41的真实回复')
    expect(host.querySelectorAll('.ri-rate .el-rate__item .is-active')).toHaveLength(3)
  })

  it('失败后可重试成功，并清除错误', async () => {
    api.apiReviews.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce(page(41))
    await mountPage()
    retry('.review-error')
    await flush()
    expect(host.querySelector('.review-error')).toBeNull()
    expect(host.querySelector('.ri-content')?.textContent).toBe('商品41的真实评价')
  })

  it('加载中不伪装成暂无评价', async () => {
    const pending = deferred<ReturnType<typeof page>>()
    api.apiReviews.mockReturnValue(pending.promise)
    await mountPage()
    expectNoReviews()
    expect(host.querySelector('.reviews-list')?.textContent).toContain('评价加载中')
    expect(host.querySelector('.reviews-list')?.textContent).not.toContain('暂无评价')
    pending.resolve(page())
    await flush()
    expect(host.querySelector('.reviews-list')?.textContent).toContain('暂无评价')
  })
})

describe('真实商品与规格失败', () => {
  it('未知商品详情失败不展示本地第一件商品，并允许重试', async () => {
    api.apiProductDetail.mockRejectedValueOnce(new Error('not found'))
    await mountPage(999999)
    expect(host.querySelector('.detail-container')).toBeNull()
    expect(host.querySelector('.product-error')?.textContent).toContain('商品加载失败')
    expect(host.textContent).not.toContain('Apple iPhone')
    retry('.product-error')
    await flush()
    expect(host.querySelector('.main-title')?.textContent).toBe('真实商品999999')
    expect(host.querySelector('.product-error')).toBeNull()
  })

  it('接口返回其他商品时拒绝展示', async () => {
    api.apiProductDetail.mockResolvedValue(product(42))
    await mountPage(41)
    expect(host.querySelector('.detail-container')).toBeNull()
    expect(host.querySelector('.product-error')?.textContent).toContain('商品加载失败')
  })

  it('无商品数据也显示失败而不是空白', async () => {
    api.apiProductDetail.mockResolvedValue(null)
    await mountPage()
    expect(host.querySelector('.detail-container')).toBeNull()
    expect(host.querySelector('.product-error')?.textContent).toContain('商品加载失败')
  })

  it('规格接口失败不伪造可购买的规格，并提供重试', async () => {
    api.apiCatalogProductSkus.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce([sku(41)])
    await mountPage()
    expect(host.querySelector('.selected-text')?.textContent).not.toContain('太空灰')
    expect(host.querySelector<HTMLButtonElement>('.m-buy-btn')?.disabled).toBe(true)
    retry('.sku-error')
    await flush()
    expect(host.querySelector('.sku-error')).toBeNull()
    host.querySelector<HTMLElement>('.spec-select-cell')!.click()
    await flush()
    expect(document.body.textContent).toContain('商品41专用色')
    expect(document.body.textContent).not.toContain('无线快充尊享版')
  })

  it('真实零库存不能被默认库存替代', async () => {
    api.apiProductDetail.mockResolvedValue({ ...product(41), stock: 0 })
    await mountPage()
    expect(host.querySelector<HTMLButtonElement>('.m-buy-btn')?.disabled).toBe(true)
  })

  it('规格仍在加载时，入口与弹窗确认按钮都不可购买', async () => {
    const pending = deferred<ReturnType<typeof sku>[]>()
    api.apiCatalogProductSkus.mockReturnValue(pending.promise)
    await mountPage()
    expect(host.querySelector<HTMLButtonElement>('.m-buy-btn')?.disabled).toBe(true)
    host.querySelector<HTMLElement>('.spec-select-cell')!.click()
    await flush()
    expect(document.querySelector<HTMLButtonElement>('.mf-cart-btn')?.disabled).toBe(true)
    expect(document.querySelector<HTMLButtonElement>('.mf-buy-btn')?.disabled).toBe(true)
    pending.resolve([])
    await flush()
    expect(host.querySelector<HTMLButtonElement>('.m-buy-btn')?.disabled).toBe(false)
  })

  it('真实无SKU不生成虚构规格', async () => {
    await mountPage()
    host.querySelector<HTMLElement>('.spec-select-cell')!.click()
    await flush()
    expect(document.querySelector('.smb-specs')).toBeNull()
    expect(document.body.textContent).not.toContain('太空灰')
    expect(host.querySelector('.sku-error')).toBeNull()
  })
})

describe('同一详情组件复用与晚到响应', () => {
  it('切换商品立即清空旧商品和评价，下一商品失败时不回显旧数据', async () => {
    api.apiReviews.mockResolvedValue(page(41))
    await mountPage()
    const pending = deferred<ReturnType<typeof product>>()
    api.apiProductDetail.mockReturnValueOnce(pending.promise)
    await router.push('/products/42')
    await flush()
    expect(host.querySelector('.detail-container')).toBeNull()
    expect(host.textContent).not.toContain('商品41')
    expect(host.querySelector('.product-loading')?.textContent).toContain('商品加载中')
    pending.reject(new Error('offline'))
    await flush()
    expect(host.querySelector('.product-error')).not.toBeNull()
    expect(host.textContent).not.toContain('商品41')
  })

  it('旧商品详情成功晚到不能覆盖当前商品', async () => {
    const old = deferred<ReturnType<typeof product>>()
    api.apiProductDetail.mockReturnValueOnce(old.promise)
    await mountPage(41)
    await router.push('/products/42')
    await flush()
    old.resolve(product(41))
    await flush()
    expect(host.querySelector('.main-title')?.textContent).toBe('真实商品42')
    expect(host.textContent).not.toContain('商品41')
  })

  it.each(['resolve', 'reject'] as const)('旧评价请求%s晚到不能覆盖当前商品的评价', async (result) => {
    const old = deferred<ReturnType<typeof page>>()
    api.apiReviews.mockReturnValueOnce(old.promise).mockResolvedValue(page(42))
    await mountPage(41)
    await router.push('/products/42')
    await flush()
    if (result === 'resolve') old.resolve(page(41))
    else old.reject(new Error('old request failed'))
    await flush()
    expect(host.querySelector('.main-title')?.textContent).toBe('真实商品42')
    expect(host.querySelector('.ri-content')?.textContent).toBe('商品42的真实评价')
    expect(host.querySelector('.review-error')).toBeNull()
    expect(host.textContent).not.toContain('商品41的真实评价')
  })

  it('旧商品SKU晚到不能覆盖当前商品规格', async () => {
    const old = deferred<ReturnType<typeof sku>[]>()
    api.apiCatalogProductSkus.mockReturnValueOnce(old.promise).mockResolvedValue([sku(42)])
    await mountPage(41)
    await router.push('/products/42')
    await flush()
    old.resolve([sku(41)])
    await flush()
    host.querySelector<HTMLElement>('.spec-select-cell')!.click()
    await flush()
    expect(document.body.textContent).toContain('商品42专用色')
    expect(document.body.textContent).not.toContain('商品41专用色')
  })

  it('A到B再回A时，最早的A评价仍不能覆盖最新A评价', async () => {
    const old = deferred<ReturnType<typeof page>>()
    api.apiReviews.mockReturnValueOnce(old.promise).mockResolvedValueOnce(page(42)).mockResolvedValueOnce(page())
    await mountPage(41)
    await router.push('/products/42')
    await flush()
    await router.push('/products/41')
    await flush()
    old.resolve(page(41))
    await flush()
    expect(host.querySelector('.main-title')?.textContent).toBe('真实商品41')
    expectNoReviews()
    expect(host.querySelector('.reviews-list')?.textContent).toContain('暂无评价')
  })
})

async function openSpecs(selectSku = false) {
  host.querySelector<HTMLElement>('.spec-select-cell')!.click()
  await flush()
  if (selectSku) {
    document.querySelector<HTMLButtonElement>('.smb-pill')!.click()
    await flush()
  }
}
function confirmButton(kind: 'cart' | 'buy') {
  return document.querySelector<HTMLButtonElement>(`.mf-${kind}-btn`)!
}
function favoriteButton() {
  return [...host.querySelectorAll<HTMLElement>('.mobile-icon-btn')]
    .find(button => button.textContent?.includes('收藏'))!
}

describe('购买链路的真实SKU与成功条件', () => {
  beforeEach(() => { auth.isCustomer = true })

  it('将选中SKU的id而非不存在的skuId发送给加购API', async () => {
    api.apiCatalogProductSkus.mockResolvedValue([sku(41)])
    await mountPage()
    await openSpecs(true)
    confirmButton('cart').click()
    await flush()
    expect(api.apiCartAdd).toHaveBeenCalledWith(41, 1, 4100)
    expect(router.currentRoute.value.fullPath).toBe('/products/41')
  })

  it('立即购买等待加购成功才跳转至结算购物车', async () => {
    const pending = deferred<void>()
    api.apiCartAdd.mockReturnValue(pending.promise)
    await mountPage()
    await openSpecs()
    confirmButton('buy').click()
    await flush()
    expect(router.currentRoute.value.fullPath).toBe('/products/41')
    expect(confirmButton('buy').disabled).toBe(true)
    pending.resolve(undefined)
    await flush()
    expect(router.currentRoute.value.fullPath).toBe('/cart?checkout=1')
    expect(host.querySelector('.test-cart-page')).not.toBeNull()
  })

  it('立即购买加购失败留在本页，可再次尝试成功', async () => {
    api.apiCartAdd.mockRejectedValueOnce(new Error('库存不足'))
    await mountPage()
    await openSpecs()
    confirmButton('buy').click()
    await flush()
    expect(router.currentRoute.value.fullPath).toBe('/products/41')
    expect(document.body.textContent).toContain('库存不足')
    expect(confirmButton('buy').disabled).toBe(false)
    confirmButton('buy').click()
    await flush()
    expect(router.currentRoute.value.fullPath).toBe('/cart?checkout=1')
    expect(api.apiCartAdd).toHaveBeenCalledTimes(2)
  })

  it('加购未完成时，两种确认按钮重复点击也只提交一次', async () => {
    const pending = deferred<void>()
    api.apiCartAdd.mockReturnValue(pending.promise)
    await mountPage()
    await openSpecs()
    confirmButton('cart').click()
    confirmButton('buy').click()
    confirmButton('cart').click()
    await flush()
    expect(api.apiCartAdd).toHaveBeenCalledTimes(1)
    expect(router.currentRoute.value.fullPath).toBe('/products/41')
    expect(confirmButton('cart').disabled).toBe(true)
    expect(confirmButton('buy').disabled).toBe(true)
    pending.resolve(undefined)
    await flush()
    expect(router.currentRoute.value.fullPath).toBe('/products/41')
  })

  it('商品A立即购买成功晚到不会把商品B带走', async () => {
    const pending = deferred<void>()
    api.apiCartAdd.mockReturnValueOnce(pending.promise)
    await mountPage()
    await openSpecs()
    confirmButton('buy').click()
    await router.push('/products/42')
    await flush()
    await openSpecs()
    pending.resolve(undefined)
    await flush()
    expect(router.currentRoute.value.fullPath).toBe('/products/42')
    expect(host.querySelector('.main-title')?.textContent).toBe('真实商品42')
    expect(confirmButton('cart')).not.toBeNull()
  })

  it('旧加购完成不能解除新商品正在提交的防重复状态', async () => {
    const old = deferred<void>()
    const current = deferred<void>()
    api.apiCartAdd.mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise)
    await mountPage()
    await openSpecs()
    confirmButton('cart').click()
    await router.push('/products/42')
    await flush()
    await openSpecs()
    confirmButton('cart').click()
    await flush()
    old.resolve(undefined)
    await flush()
    expect(confirmButton('cart')?.disabled).toBe(true)
    expect(confirmButton('buy')?.disabled).toBe(true)
    current.resolve(undefined)
    await flush()
    expect(router.currentRoute.value.fullPath).toBe('/products/42')
  })
})

describe('收藏的失败、重复点击与请求隔离', () => {
  beforeEach(() => { auth.isCustomer = true })

  it.each([false, true])('收藏失败保留原状态%s，并展示失败而非成功反馈', async (initial) => {
    api.apiFavoriteStatus.mockResolvedValue({ favorited: initial })
    api.apiFavoriteToggle.mockRejectedValue(new Error('offline'))
    await mountPage()
    favoriteButton().click()
    await flush()
    expect(favoriteButton().textContent?.trim()).toBe(initial ? '已收藏' : '收藏')
    expect(document.body.textContent).toContain('收藏操作失败')
    expect(document.body.textContent).not.toContain('已添加到收藏')
    expect(document.body.textContent).not.toContain('已取消收藏')
  })

  it('请求成功才更新收藏，失败后允许重试', async () => {
    api.apiFavoriteToggle.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ favorited: true })
    await mountPage()
    favoriteButton().click()
    await flush()
    expect(favoriteButton().textContent?.trim()).toBe('收藏')
    favoriteButton().click()
    await flush()
    expect(favoriteButton().textContent?.trim()).toBe('已收藏')
    expect(api.apiFavoriteToggle).toHaveBeenCalledTimes(2)
  })

  it('收藏请求未完成时重复点击只提交一次，完成后可取消收藏', async () => {
    const pending = deferred<{ favorited: boolean }>()
    api.apiFavoriteToggle.mockReturnValueOnce(pending.promise).mockResolvedValue({ favorited: false })
    await mountPage()
    favoriteButton().click()
    favoriteButton().click()
    await flush()
    favoriteButton().click()
    expect(api.apiFavoriteToggle).toHaveBeenCalledTimes(1)
    expect(favoriteButton().getAttribute('aria-busy')).toBe('true')
    pending.resolve({ favorited: true })
    await flush()
    expect(favoriteButton().textContent?.trim()).toBe('已收藏')
    expect(favoriteButton().getAttribute('aria-busy')).toBe('false')
    favoriteButton().click()
    await flush()
    expect(favoriteButton().textContent?.trim()).toBe('收藏')
  })

  it.each(['resolve', 'reject'] as const)('商品A收藏%s晚到不改变商品B也不显示A的反馈', async (result) => {
    const pending = deferred<{ favorited: boolean }>()
    api.apiFavoriteToggle.mockReturnValueOnce(pending.promise)
    await mountPage()
    favoriteButton().click()
    await router.push('/products/42')
    await flush()
    if (result === 'resolve') pending.resolve({ favorited: true })
    else pending.reject(new Error('old request failed'))
    await flush()
    expect(favoriteButton().textContent?.trim()).toBe('收藏')
    expect(document.body.textContent).not.toContain('已添加到收藏')
    expect(document.body.textContent).not.toContain('收藏操作失败')
    expect(host.querySelector('.main-title')?.textContent).toBe('真实商品42')
  })

  it('旧收藏完成不能解除新商品正在提交的防重复状态', async () => {
    const old = deferred<{ favorited: boolean }>()
    const current = deferred<{ favorited: boolean }>()
    api.apiFavoriteToggle.mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise)
    await mountPage()
    favoriteButton().click()
    await router.push('/products/42')
    await flush()
    favoriteButton().click()
    await flush()
    old.resolve({ favorited: true })
    await flush()
    expect(favoriteButton().getAttribute('aria-busy')).toBe('true')
    favoriteButton().click()
    expect(api.apiFavoriteToggle).toHaveBeenCalledTimes(2)
    current.resolve({ favorited: false })
    await flush()
    expect(favoriteButton().textContent?.trim()).toBe('收藏')
    expect(favoriteButton().getAttribute('aria-busy')).toBe('false')
  })

  it('初始化收藏查询晚到不能覆盖已成功的收藏操作', async () => {
    const pending = deferred<{ favorited: boolean }>()
    api.apiFavoriteStatus.mockReturnValueOnce(pending.promise)
    await mountPage()
    favoriteButton().click()
    await flush()
    expect(favoriteButton().textContent?.trim()).toBe('已收藏')
    pending.resolve({ favorited: false })
    await flush()
    expect(favoriteButton().textContent?.trim()).toBe('已收藏')
  })
  it('领券入口跳转真实领券中心而不是伪造已领取成功', async () => {
    const success = vi.spyOn(ElMessage, 'success')
    try {
      await mountPage()
      host.querySelector<HTMLElement>('.coupon-chip')!.click()
      await flush()
      expect(success).not.toHaveBeenCalled()
      expect(router.currentRoute.value.path).toBe('/coupons')
    } finally { success.mockRestore() }
  })

})
