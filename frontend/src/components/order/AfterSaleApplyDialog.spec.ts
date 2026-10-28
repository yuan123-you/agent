import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {createApp,defineComponent,h,nextTick,type App} from 'vue'
import AfterSaleApplyDialog from './AfterSaleApplyDialog.vue'
const mocks=vi.hoisted(()=>({eligibility:vi.fn(),quote:vi.fn(),apply:vi.fn(),upload:vi.fn(),created:vi.fn()}))
vi.mock('@/api',()=>({apiAfterSaleEligibility:mocks.eligibility,apiAfterSaleQuote:mocks.quote,apiAfterSaleApply:mocks.apply,apiAfterSaleUpload:mocks.upload}))
const flush=async()=>{for(let i=0;i<18;i++)await nextTick()}
let app:App,host:HTMLDivElement
async function mount(){host=document.createElement('div');document.body.append(host);app=createApp(AfterSaleApplyDialog,{modelValue:true,orderId:1,onCreated:mocks.created});app.component('ElDialog',defineComponent({setup(_,ctx){return()=>h('section',ctx.slots.default?.())}}));app.component('ElButton',defineComponent({props:['nativeType','disabled','loading'],setup(p,ctx){return()=>h('button',{type:p.nativeType||'button',disabled:!!p.disabled||!!p.loading},ctx.slots.default?.())}}));app.mount(host);await flush()}
function setReason(){const select=host.querySelectorAll<HTMLSelectElement>('select')[2];select.value='商品质量问题';select.dispatchEvent(new Event('change'))}
function submit(){host.querySelector('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))}
beforeEach(()=>{vi.clearAllMocks();mocks.eligibility.mockResolvedValue([{orderItemId:2,productName:'测试商品',purchasedQuantity:2,availableQuantity:2,serviceTypes:['REFUND_ONLY','EXCHANGE'],maxRefundAmount:80,unavailableReason:''}]);mocks.quote.mockResolvedValue({maxRefundAmount:40});mocks.apply.mockResolvedValue({id:5})})
afterEach(()=>{app?.unmount();host?.remove()})
describe('buyer application',()=>{
 it('submits actual quote, item evidence and one stable idempotency key',async()=>{await mount();setReason();submit();await flush();expect(mocks.apply).toHaveBeenCalledWith(expect.objectContaining({orderId:1,orderItemId:2,refundAmount:40,quantity:1,issueCategory:'QUALITY',evidence:[],requestId:expect.any(String)}));expect(mocks.created).toHaveBeenCalledWith({id:5})})
 it('keeps a failed draft and reuses its request key on retry',async()=>{mocks.apply.mockRejectedValueOnce(new Error('network'));await mount();setReason();submit();await flush();expect(host.querySelectorAll('select')[2].value).toBe('商品质量问题');const key=mocks.apply.mock.calls[0][0].requestId;submit();await flush();expect(mocks.apply.mock.calls[1][0].requestId).toBe(key)})
 it('blocks submission without a valid server quote',async()=>{mocks.quote.mockRejectedValue(new Error('offline'));await mount();setReason();submit();await flush();expect(mocks.apply).not.toHaveBeenCalled()})
 it('does not let a stale quote overwrite a newer quantity',async()=>{let resolve!:(v:any)=>void;mocks.quote.mockReturnValueOnce(new Promise(r=>resolve=r)).mockResolvedValue({maxRefundAmount:80});await mount();const quantity=host.querySelector<HTMLInputElement>('input[type=number]')!;quantity.value='2';quantity.dispatchEvent(new Event('input'));await flush();resolve({maxRefundAmount:40});await flush();const amount=host.querySelectorAll<HTMLInputElement>('input[type=number]')[1];expect(amount.value).toBe('80')})
})
