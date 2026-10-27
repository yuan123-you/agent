import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import QuickViewModal from './QuickViewModal.vue'

const cart = vi.hoisted(() => ({ addToCart: vi.fn().mockResolvedValue(true) }))
vi.mock('@/stores/cart', () => ({ useCartStore: () => cart }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
let app: App
let host: HTMLDivElement
async function open(stock?: number) {
  host = document.createElement('div'); document.body.appendChild(host)
  app = createApp(QuickViewModal)
  app.component('el-dialog', { props: ['modelValue'], template: '<div v-if="modelValue"><slot /></div>' })
  app.component('el-image', { template: '<div />' })
  app.component('el-icon', { template: '<i><slot /></i>' })
  app.config.warnHandler = () => {}
  const view = app.mount(host) as any
  view.open({ id: 1, name: '真实商品', category: 'FOOD', brand: '', price: 100, stock })
  await nextTick()
}
afterEach(() => { app?.unmount(); host?.remove(); cart.addToCart.mockClear() })

describe('商品快速预览事实与库存', () => {
  it('不虚构划线价和物流售后承诺', async () => {
    await open(2)
    expect(host.querySelector('.qv-old-price')).toBeNull()
    for (const claim of ['官方正品', '顺丰速发', '7天无理由退货']) expect(host.textContent).not.toContain(claim)
  })
  it.each([0, undefined])('库存 %s 不回落为50件或允许加入购物车', async stock => {
    await open(stock)
    const add = host.querySelector<HTMLButtonElement>('.qv-add-btn')!
    expect(add.disabled).toBe(true)
    expect(host.querySelector('.qv-stock-hint')?.textContent).not.toContain('50')
    add.click(); await nextTick()
    expect(cart.addToCart).not.toHaveBeenCalled()
  })
})
