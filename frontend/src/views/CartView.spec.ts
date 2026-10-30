import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import ElementPlus, { ElMessage, ElMessageBox } from 'element-plus'
import type { CartRow } from '@/api'
import CartView from './CartView.vue'

const api = vi.hoisted(() => ({ apiCartList: vi.fn(), apiCartUpdate: vi.fn(), apiCartCheckAll: vi.fn(), apiCartRemove: vi.fn(), apiProducts: vi.fn(), apiCartCheckout: vi.fn(), apiPayOrder: vi.fn() }))
vi.mock('@/api', () => api)
let app: App
let host: HTMLDivElement
let router: Router
let rows: CartRow[]
const flush = async () => {
  for (let i = 0; i < 12; i++) await nextTick()
  await new Promise(resolve => setTimeout(resolve, 0))
  await nextTick()
}
async function mountPage(path = '/cart') {
  router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/cart', component: CartView },
    { path: '/order/confirm', component: { template: '<div>订单确认</div>' } },
    { path: '/products/:id', component: { template: '<div>商品详情</div>' } },
    { path: '/coupons', component: { template: '<div>领券中心</div>' } },
    { path: '/', component: { template: '<div>首页</div>' } },
  ] })
  await router.push(path)
  await router.isReady()
  app = createApp(RouterView).use(router).use(ElementPlus)
  app.mount(host)
  await flush()
}
function click(selector: string) {
  const element = host.querySelector<HTMLElement>(selector)
  expect(element, selector).not.toBeNull()
  element!.click()
}
beforeEach(() => {
  vi.resetAllMocks()
  rows = [
    { cartItemId: 1, productId: 11, name: '降噪蓝牙耳机', price: 129.9, quantity: 2, checked: 1, subtotal: 259.8, stock: 5, imageUrl: '/earphones.png', skuSp: '[{"key":"颜色","value":"奶油白"}]' },
    { cartItemId: 2, productId: 22, name: '纯棉短袖', price: 39, quantity: 1, checked: 0, subtotal: 39, stock: 3, imageUrl: '/shirt.png' },
  ]
  api.apiCartList.mockImplementation(async () => ({ items: rows.map(row => ({ ...row })), totalAmount: rows.filter(row => row.checked === 1).reduce((sum, row) => sum + row.price * row.quantity, 0), checkedCount: rows.filter(row => row.checked === 1).length }))
  api.apiCartUpdate.mockImplementation(async (id, update) => {
    const row = rows.find(item => item.cartItemId === id)!
    if (update.checked !== undefined) row.checked = update.checked ? 1 : 0
    if (update.quantity !== undefined) row.quantity = update.quantity
  })
  api.apiCartCheckAll.mockImplementation(async checked => { rows.forEach(row => { row.checked = checked ? 1 : 0 }) })
  api.apiCartRemove.mockImplementation(async id => { rows = rows.filter(row => row.cartItemId !== id) })
  api.apiProducts.mockResolvedValue({ records: [{ id: 33, name: '推荐商品', price: 18.5, sales: 234, imageUrl: '/recommend.png' }] })
  host = document.createElement('div')
  document.body.appendChild(host)
})
afterEach(() => { app?.unmount(); host.remove(); ElMessage.closeAll(); vi.restoreAllMocks() })

describe('拼多多风格购物车', () => {
  it('展示数量、真实规格、两位小数价格，不虚构配送成交承诺', async () => {
    await mountPage()
    expect(host.querySelector('.cart-section-title')?.textContent).toContain('全部商品（2）')
    expect(host.querySelector('.goods-sku-pill')?.textContent).toContain('奶油白')
    expect(host.querySelector('.goods-price-row')?.textContent).toContain('129.90')
    expect(host.textContent).not.toContain('顺丰')
    expect(host.textContent).not.toContain('已拼')
    expect(host.querySelector('.rec-sales')?.textContent).toContain('已售 200+')
  })
  it('单品勾选更新合计且具有可访问名称', async () => {
    await mountPage()
    click('.cart-goods-row:nth-child(2) input[type="checkbox"]'); await flush()
    expect(api.apiCartUpdate).toHaveBeenCalledWith(2, { checked: true })
    expect(host.querySelector('.fcb-price')?.textContent).toBe('298.80')
    expect(host.querySelector<HTMLInputElement>('.goods-checkbox input')?.labels?.[0]?.textContent?.trim()).toBe('选择降噪蓝牙耳机')
  })
  it('底部全选和店铺勾选保持同步', async () => {
    await mountPage()
    click('.fcb-checkbox input'); await flush()
    expect(api.apiCartCheckAll).toHaveBeenLastCalledWith(true)
    expect(host.querySelector<HTMLInputElement>('.shop-checkbox input')?.checked).toBe(true)
    click('.shop-checkbox input'); await flush()
    expect(api.apiCartCheckAll).toHaveBeenLastCalledWith(false)
    expect(host.querySelector<HTMLButtonElement>('.checkout-submit-btn')?.disabled).toBe(true)
  })
  it('数量步进器沿用购物车接口并更新总价', async () => {
    await mountPage()
    const input = host.querySelector<HTMLInputElement>('.cart-goods-row .el-input-number input')!
    input.value = '3'
    input.dispatchEvent(new Event('input', { bubbles: true }))
    input.dispatchEvent(new Event('change', { bubbles: true }))
    await flush()
    expect(api.apiCartUpdate).toHaveBeenCalledWith(1, { quantity: 3, checked: true })
    expect(host.querySelector('.fcb-price')?.textContent).toBe('389.70')
  })
  it('管理模式可删除单品并返回正常模式', async () => {
    await mountPage()
    click('.manage-toggle-btn'); await flush()
    expect(host.querySelector('.checkout-submit-btn')).toBeNull()
    click('.row-delete-btn'); await flush()
    expect(api.apiCartRemove).toHaveBeenCalledWith(1)
    expect(host.querySelectorAll('.cart-goods-row')).toHaveLength(1)
    click('.manage-toggle-btn'); await flush()
    expect(host.querySelector('.checkout-submit-btn')).not.toBeNull()
  })
  it('管理模式确认后只批量删除选中商品', async () => {
    vi.spyOn(ElMessageBox, 'confirm').mockImplementation(vi.fn().mockResolvedValue('confirm'))
    await mountPage()
    click('.manage-toggle-btn'); await flush()
    click('.batch-delete-btn'); await flush()
    expect(api.apiCartRemove).toHaveBeenCalledExactlyOnceWith(1)
    expect(host.querySelector('.goods-name')?.textContent).toContain('纯棉短袖')
    expect(host.querySelector('.checkout-submit-btn')).not.toBeNull()
  })
  it('结算进入已有订单确认页，不直接创建订单或支付', async () => {
    await mountPage()
    click('.checkout-submit-btn'); await flush()
    expect(router.currentRoute.value.path).toBe('/order/confirm')
    expect(api.apiCartCheckout).not.toHaveBeenCalled()
    expect(api.apiPayOrder).not.toHaveBeenCalled()
  })
  it('兼容旧的直接结算入口', async () => {
    await mountPage('/cart?checkout=1')
    expect(router.currentRoute.value.path).toBe('/order/confirm')
  })
  it('未勾选时禁用结算，旧入口也不会进入结算', async () => {
    rows.forEach(row => { row.checked = 0 })
    await mountPage('/cart?checkout=1')
    expect(router.currentRoute.value.path).toBe('/cart')
    expect(host.querySelector<HTMLButtonElement>('.checkout-submit-btn')?.disabled).toBe(true)
  })
  it('空购物车保留去逛逛和推荐，不显示结算栏', async () => {
    rows = []
    await mountPage()
    expect(host.querySelector('.empty-cart-card')).not.toBeNull()
    expect(host.querySelector('.fixed-checkout-bar')).toBeNull()
    expect(host.querySelectorAll('.rec-card')).toHaveLength(1)
    click('.ecc-btn'); await flush()
    expect(router.currentRoute.value.path).toBe('/')
  })
  it('商品、推荐和领券入口可导航', async () => {
    await mountPage()
    click('.goods-name'); await flush()
    expect(router.currentRoute.value.path).toBe('/products/11')
    await router.push('/cart'); await flush()
    click('.rec-card'); await flush()
    expect(router.currentRoute.value.path).toBe('/products/33')
    await router.push('/cart'); await flush()
    click('.sbb-more'); await flush()
    expect(router.currentRoute.value.path).toBe('/coupons')
  })
  it('推荐失败提供重试，重试成功恢复商品', async () => {
    api.apiProducts.mockRejectedValueOnce(new Error('network'))
    await mountPage()
    expect(host.querySelector('[role="alert"]')?.textContent).toContain('推荐商品加载失败')
    click('[role="alert"] button'); await flush()
    expect(host.querySelector('[role="alert"]')).toBeNull()
    expect(host.querySelectorAll('.rec-card')).toHaveLength(1)
  })
  it('首次加载显示骨架而不是空购物车', async () => {
    let resolve!: (value: unknown) => void
    api.apiCartList.mockReturnValueOnce(new Promise(done => { resolve = done }))
    await mountPage()
    expect(host.querySelector('[data-loading-variant="list"]')).not.toBeNull()
    expect(host.querySelector('.empty-cart-card')).toBeNull()
    resolve({ items: [], totalAmount: 0, checkedCount: 0 }); await flush()
    expect(host.querySelector('.empty-cart-card')).not.toBeNull()
  })
})
