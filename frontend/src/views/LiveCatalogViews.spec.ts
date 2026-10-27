import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, reactive, type App } from 'vue'
import HomeView from './HomeView.vue'
import ProductListView from './ProductListView.vue'
import CartView from './CartView.vue'
const mocks=vi.hoisted(() => ({ products:vi.fn(), push:vi.fn(), cart:vi.fn() }))
let route: any
vi.mock('@/api',() => ({ apiProducts:mocks.products,apiCartList:mocks.cart,apiCartCheckAll:vi.fn(),apiCartCheckout:vi.fn(),apiCartRemove:vi.fn(),apiCartUpdate:vi.fn(),apiPayOrder:vi.fn() }))
vi.mock('@/components/address/CheckoutAddressPicker.vue',()=>({default:{template:'<div />'}}))
vi.mock('@/components/mall/CouponPicker.vue',()=>({default:{template:'<div />'}}))
vi.mock('vue-router',() => ({ useRoute:() => route,useRouter:() => ({push:mocks.push}) }))
vi.mock('element-plus',() => ({ElMessage:{warning:vi.fn(),success:vi.fn(),info:vi.fn()}}))
let app:App|undefined; let host:HTMLDivElement
const flush=async()=> { for(let i=0;i<16;i++) await nextTick() }
const product=(id=701)=>({id,name:`后端真实商品${id}`,price:12.34,category:'PHONE',brand:'真实品牌',stock:5,sales:0})
async function mount(component:any) {
 host=document.createElement('div'); document.body.appendChild(host); app=createApp(component)
 const basic=defineComponent({setup(_,{slots}){return()=>h('div',slots.default?.())}})
 for(const name of ['ElImage','ElIcon','ElDrawer','ElSwitch','ElInput','ElButton','ElScrollbar','ElDialog','ElEmpty','ElCheckbox','ElInputNumber']) app.component(name,basic)
 Object.defineProperty(app.config.globalProperties,'$router',{value:{push:mocks.push}}); app.mount(host); await flush()
}
beforeEach(()=>{vi.clearAllMocks();route=reactive({query:{}});mocks.cart.mockResolvedValue({items:[],totalAmount:0,checkedCount:0});mocks.products.mockResolvedValue({records:[product()],total:1})})
afterEach(()=>{app?.unmount();app=undefined;host?.remove()})
describe('live catalog identity',()=>{
 it('category list shows product-card skeletons while the catalog is pending',async()=>{
  let resolve!: (value:any)=>void; mocks.products.mockReturnValueOnce(new Promise(r=>{resolve=r}))
  await mount(ProductListView);expect(host.querySelector('[data-loading-variant="cards"]')).not.toBeNull();expect(host.textContent).not.toContain('商品加载中')
  resolve({records:[product()],total:1});await flush();expect(host.querySelector('[data-loading-variant]')).toBeNull()
 })
 it('keeps real catalog items visible while appending a page of skeletons',async()=>{
  let resolve!: (value:any)=>void
  mocks.products.mockResolvedValueOnce({records:[product()],total:2}).mockReturnValueOnce(new Promise(r=>{resolve=r}))
  await mount(ProductListView)
  Array.from(host.querySelectorAll<HTMLButtonElement>('button')).find(b=>b.textContent?.trim()==='加载更多商品')!.click();await flush()
  expect(host.textContent).toContain('后端真实商品701')
  expect(host.querySelectorAll('.loading-card')).toHaveLength(2)
  resolve({records:[product(702)],total:2});await flush()
  expect(host.textContent).toContain('后端真实商品702');expect(host.querySelector('[data-loading-variant]')).toBeNull()
 })
 it('cart shows item skeletons while its first request is pending',async()=>{
  mocks.cart.mockReturnValueOnce(new Promise(()=>{}));await mount(CartView)
  expect(host.querySelector('[data-loading-variant="list"]')).not.toBeNull();expect(host.querySelector('.empty-cart-card')).toBeNull()
 })

 it.each([['home',HomeView,'.pdd-card'],['list',ProductListView,'.stream-product-card'],['cart recommendations',CartView,'.rec-card']] as const)('%s uses real API names, prices and ids rather than local fixture ids',async(name,component,selector)=>{
  await mount(component); expect(mocks.products).toHaveBeenCalled(); expect(host.textContent).toContain('后端真实商品701');expect(host.textContent).toContain('12.34')
  expect(host.textContent).not.toContain('Apple iPhone 15 Pro Max')
  const card=host.querySelector<HTMLElement>(selector) || host.querySelector<HTMLElement>('.stream-card')
  expect(card).not.toBeNull();card!.click();await flush();expect(mocks.push).toHaveBeenCalledWith('/products/701')
 })
 it.each([['home',HomeView],['list',ProductListView],['cart recommendations',CartView]] as const)('%s shows an API failure without substituting invented products',async(_name,component)=>{
  mocks.products.mockRejectedValue(new Error('offline'));await mount(component);expect(host.textContent).toContain('加载失败');expect(host.textContent).not.toContain('Apple iPhone 15 Pro Max')
 })
 it('home appends real backend pages on scroll',async()=>{
  mocks.products.mockResolvedValueOnce({records:[product(701)],total:2}).mockResolvedValueOnce({records:[product(702)],total:2})
  await mount(HomeView);window.dispatchEvent(new Event('scroll'));await flush()
  expect(mocks.products).toHaveBeenLastCalledWith(expect.objectContaining({page:2}));expect(host.textContent).toContain('后端真实商品702')
 })
 it('category list sends the native category code rather than its display label',async()=>{
  await mount(ProductListView);expect(mocks.products).toHaveBeenCalledWith(expect.objectContaining({category:'PHONE'}))
 })
 it('category location label renders its configured city instead of an undefined property',async()=>{
  await mount(ProductListView);expect(host.querySelector('.location-btn')?.textContent).toContain('北京市')
 })
 it('typing does not issue a database query for every keystroke before search is submitted',async()=>{
  await mount(ProductListView);const input=host.querySelector<HTMLInputElement>('.cs-input')!
  for(const text of ['真','真实','真实商品']) {input.value=text;input.dispatchEvent(new Event('input'));await flush()}
  expect(mocks.products).toHaveBeenCalledTimes(1)
  host.querySelector<HTMLButtonElement>('.cs-submit-btn')!.click();await flush()
  expect(mocks.products).toHaveBeenCalledTimes(2);expect(mocks.products).toHaveBeenLastCalledWith(expect.objectContaining({keyword:'真实商品'}))
 })

 it('keeps backend selling-point search matches even when the name does not contain the keyword',async()=>{
  route.query={keyword:'蓝牙'};mocks.products.mockResolvedValue({records:[{...product(),sellingPoints:'支持蓝牙连接'}],total:1})
  await mount(ProductListView);expect(host.textContent).toContain('后端真实商品701')
 })
 it('does not hide the current server result while an unsubmitted keyword is being edited',async()=>{
  await mount(ProductListView);const input=host.querySelector<HTMLInputElement>('.cs-input')!;input.value='尚未提交的不同关键词';input.dispatchEvent(new Event('input'));await flush()
  expect(mocks.products).toHaveBeenCalledTimes(1);expect(host.textContent).toContain('后端真实商品701')
 })

})
