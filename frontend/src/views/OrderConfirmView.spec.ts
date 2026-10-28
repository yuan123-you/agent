import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import ElementPlus, { ElMessage } from 'element-plus'
import OrderConfirmView from './OrderConfirmView.vue'

const api = vi.hoisted(() => ({
  apiAddresses: vi.fn(),
  apiProductDetail: vi.fn(),
  apiCatalogProductSkus: vi.fn(),
  apiCartList: vi.fn(),
  apiCreateOrder: vi.fn(),
  apiCartCheckout: vi.fn(),
  apiPayOrder: vi.fn(),
}))
vi.mock('@/api', () => api)

vi.mock('@/components/address/CheckoutAddressPicker.vue', () => ({
  default: {
    name: 'CheckoutAddressPicker',
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<div class="mock-address-picker"><button class="pick-addr-btn" @click="$emit(\'update:modelValue\', 99)">选择地址99</button></div>',
  },
}))

vi.mock('@/components/mall/CouponPicker.vue', () => ({
  default: {
    name: 'CouponPicker',
    props: ['modelValue', 'amount'],
    emits: ['update:modelValue', 'discount'],
    template: '<div class="mock-coupon-picker"><button class="apply-coupon-btn" @click="$emit(\'discount\', 10)">应用券10元</button></div>',
  },
}))

let app: App
let host: HTMLDivElement
let router: Router

const flush = async () => {
  for (let i = 0; i < 16; i++) await nextTick()
  await new Promise((resolve) => setTimeout(resolve, 0))
  await nextTick()
}

const mockAddress = (id = 1, isDefault = false) => ({
  addressId: id,
  receiverName: `收货人${id}`,
  receiverPhone: '13812345678',
  receiverAddress: `北京市海淀区中关村大街${id}号`,
  province: '北京市',
  city: '北京市',
  district: '海淀区',
  detailAddress: `中关村大街${id}号`,
  isDefault,
})

const mockProduct = (id = 10) => ({
  id,
  name: `测试自营商品${id}`,
  price: 199,
  stock: 20,
  category: 'DIGITAL',
  brand: '测试品牌',
  imageUrl: `/test-prod-${id}.png`,
  description: '商品描述',
})

const mockSku = (id = 100, productId = 10) => ({
  id,
  productId,
  price: 219,
  stock: 15,
  status: 'ON_SALE',
  imageUrl: `/test-sku-${id}.png`,
  spData: JSON.stringify([{ key: '颜色', value: '曜石黑' }]),
})

async function mountPage(fullPath = '/order/confirm') {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/order/confirm', component: OrderConfirmView },
      { path: '/orders/:id', component: { template: '<div class="test-order-detail-page">订单详情</div>' } },
      { path: '/cart', component: { template: '<div class="test-cart-page">购物车</div>' } },
      { path: '/products', component: { template: '<div class="test-products-page">商品列表</div>' } },
      { path: '/products/:id', component: { template: '<div class="test-product-detail">单品页</div>' } },
    ],
  })
  await router.push(fullPath)
  await router.isReady()
  app = createApp(RouterView).use(createPinia()).use(router).use(ElementPlus)
  app.mount(host)
  await flush()
}

beforeEach(() => {
  vi.resetAllMocks()
  api.apiAddresses.mockResolvedValue([mockAddress(1, true)])
  api.apiProductDetail.mockImplementation(async (id: number) => mockProduct(id))
  api.apiCatalogProductSkus.mockResolvedValue([mockSku(100, 10)])
  api.apiCartList.mockResolvedValue({
    items: [
      {
        cartItemId: 501,
        productId: 10,
        skuId: 100,
        name: '购物车商品A',
        imageUrl: '/cart-a.png',
        price: 219,
        quantity: 2,
        checked: 1,
        stock: 10,
        subtotal: 438,
      },
    ],
    totalAmount: 438,
    checkedCount: 1,
  })
  api.apiCreateOrder.mockResolvedValue({ orderId: 888, orderNo: 'ORD20261028001' })
  api.apiCartCheckout.mockResolvedValue({ orderId: 999, orderNo: 'ORD20261028002' })
  api.apiPayOrder.mockResolvedValue(undefined)

  host = document.createElement('div')
  document.body.appendChild(host)
})

afterEach(() => {
  app?.unmount()
  host.remove()
  ElMessage.closeAll()
})

describe('OrderConfirmView 确认订单独立全屏页面', () => {
  describe('立即购买 (BUY_NOW) 结算流程', () => {
    it('正确展示单品基本信息、默认收货地址与实付金额', async () => {
      await mountPage('/order/confirm?productId=10&quantity=1')
      expect(api.apiProductDetail).toHaveBeenCalledWith(10)
      expect(host.textContent).toContain('测试自营商品10')
      expect(host.textContent).toContain('收货人1')
      expect(host.textContent).toContain('13812345678')
      expect(host.textContent).toContain('199.00')
      expect(host.querySelector('.submit-order-btn')?.textContent).toContain('模拟支付 ￥199')
    })

    it('携带 skuId 时正确加载并展示规格专有价格与规格标签', async () => {
      await mountPage('/order/confirm?productId=10&skuId=100&quantity=2')
      expect(api.apiCatalogProductSkus).toHaveBeenCalledWith(10)
      expect(host.textContent).toContain('曜石黑')
      expect(host.textContent).toContain('219.00')
      // 219 * 2 = 438
      expect(host.textContent).toContain('438.00')
      expect(host.querySelector('.submit-order-btn')?.textContent).toContain('模拟支付 ￥438')
    })

    it('立即购买模式下支持数量微调，联动实付金额', async () => {
      await mountPage('/order/confirm?productId=10&quantity=1')
      expect(host.querySelector('.bbar-price')?.textContent).toContain('199')

      const stepBtns = host.querySelectorAll<HTMLButtonElement>('.goods-stepper .step-btn')
      expect(stepBtns.length).toBe(2)
      // 点击加号
      stepBtns[1].click()
      await flush()
      expect(host.querySelector('.bbar-price')?.textContent).toContain('398')
      expect(router.currentRoute.value.query.quantity).toBe('2')
    })

    it('点击模拟支付提交订单，成功调用 apiCreateOrder 和 apiPayOrder 并跳转至订单详情', async () => {
      await mountPage('/order/confirm?productId=10&skuId=100&quantity=2')
      const submitBtn = host.querySelector<HTMLButtonElement>('.submit-order-btn')!
      submitBtn.click()
      await flush()

      expect(api.apiCreateOrder).toHaveBeenCalledWith(
        expect.objectContaining({
          productId: 10,
          skuId: 100,
          quantity: 2,
          addressId: 1,
        }),
      )
      expect(api.apiPayOrder).toHaveBeenCalledWith(888)
      expect(router.currentRoute.value.fullPath).toBe('/orders/888')
    })
  })

  describe('购物车结算 (CART) 流程', () => {
    it('不传 productId 时进入购物车结算，展示勾选商品和对应总价', async () => {
      await mountPage('/order/confirm')
      expect(api.apiCartList).toHaveBeenCalled()
      expect(host.textContent).toContain('购物车商品A')
      expect(host.textContent).toContain('438.00')
      expect(host.querySelector('.submit-order-btn')?.textContent).toContain('模拟支付 ￥438')
    })

    it('购物车结算提交成功调用 apiCartCheckout 和 apiPayOrder 并跳转至订单详情', async () => {
      await mountPage('/order/confirm')
      const submitBtn = host.querySelector<HTMLButtonElement>('.submit-order-btn')!
      submitBtn.click()
      await flush()

      expect(api.apiCartCheckout).toHaveBeenCalledWith(
        expect.objectContaining({
          addressId: 1,
        }),
      )
      expect(api.apiPayOrder).toHaveBeenCalledWith(999)
      expect(router.currentRoute.value.fullPath).toBe('/orders/999')
    })

    it('购物车无勾选商品时展示空状态提示', async () => {
      api.apiCartList.mockResolvedValueOnce({ items: [], totalAmount: 0, checkedCount: 0 })
      await mountPage('/order/confirm')
      expect(host.textContent).toContain('暂无可结算的商品')
      expect(host.querySelector('.submit-order-btn')).toBeNull()
    })
  })

  describe('优惠券与费用明细', () => {
    it('优惠券抵扣生效时，费用明细与底部吸底栏同步扣减优惠金额', async () => {
      await mountPage('/order/confirm?productId=10&quantity=1')
      expect(host.querySelector('.bbar-price')?.textContent).toContain('199')

      const applyBtn = host.querySelector<HTMLButtonElement>('.apply-coupon-btn')!
      applyBtn.click()
      await flush()

      // 199 - 10 = 189
      expect(host.textContent).toContain('已优惠 ￥10.00')
      expect(host.querySelector('.bbar-price')?.textContent).toContain('189')
      expect(host.querySelector('.submit-order-btn')?.textContent).toContain('模拟支付 ￥189')
    })
  })

  describe('收货地址与安全校验', () => {
    it('无收货地址时，提交按钮处于禁用状态', async () => {
      api.apiAddresses.mockResolvedValueOnce([])
      await mountPage('/order/confirm?productId=10&quantity=1')
      const submitBtn = host.querySelector<HTMLButtonElement>('.submit-order-btn')!
      expect(submitBtn.disabled).toBe(true)
    })

    it('点击返回按钮正确后退', async () => {
      await mountPage('/order/confirm?productId=10&quantity=1')
      const backBtn = host.querySelector<HTMLButtonElement>('.topbar-back-btn')!
      expect(backBtn).not.toBeNull()
      backBtn.click()
      await flush()
    })
  })
})
