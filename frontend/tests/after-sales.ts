// Visual/integration fixture only. All HTTP/SSE responses stay local to this page.
import {createApp,h} from 'vue'
import {createMemoryHistory,createRouter,RouterView} from 'vue-router'
import axios from 'axios'
import type {OrderVO} from '../src/types/api'
import type {AfterSaleVO,AfterSaleType} from '../src/types/aftersale'
import {MASSIVE_PRODUCTS} from '../src/data/products'
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import '../src/styles.css'
const params=new URLSearchParams(location.search)
document.documentElement.classList.toggle('dark',params.has('dark'))
const storage=new Map<string,string>([['token','after-sale-fixture-only']])
Object.defineProperty(window,'localStorage',{value:{getItem:(key:string)=>storage.get(key)??null,setItem:(key:string,value:string)=>storage.set(key,String(value)),removeItem:(key:string)=>storage.delete(key),clear:()=>storage.clear()}})
window.fetch=async()=>new Response('',{headers:{'Content-Type':'text/event-stream'}})
let role=params.get('role') || 'CUSTOMER'
;(document.getElementById('fixture-role') as HTMLSelectElement).value=role
const now='2026-10-28T10:20:00'
const orders:OrderVO[]=Array.from({length:4},(_,i)=>({orderId:i+1,orderNo:`20261028000000${i+1}`,status:i===2?'REFUNDED':'DELIVERED',totalAmount:80,discountAmount:20,createdAt:now,paidAt:now,deliveredAt:now,source:i===3?'AI':'USER',receiverName:'测试收件人',receiverPhone:'13800000000',receiverAddress:'测试收货地址',items:[{orderItemId:101+i,productId:MASSIVE_PRODUCTS[i%3].id,productName:MASSIVE_PRODUCTS[i%3].name,productImage:MASSIVE_PRODUCTS[i%3].imageUrl,quantity:2,price:50,subtotal:100,canReview:true,reviewed:false}]}))
const caseValue=(id:number,orderId:number,type:AfterSaleType,status:string):AfterSaleVO=>({id,afterSaleNo:`AS20261028000${id}`,orderId,orderItemId:100+orderId,orderNo:orders[orderId-1].orderNo,productName:orders[orderId-1].items[0].productName,productImage:orders[orderId-1].items[0].productImage,serviceType:type,issueCategory:'QUALITY',reason:'商品存在质量问题，申请售后处理',quantity:id===3?2:1,requestedRefundAmount:type==='EXCHANGE'?0:id===3?80:40,status,currentHandler:'MERCHANT',refundMode:'SIMULATED',evidence:[],history:[{action:'APPLY',status:'PENDING_MERCHANT',actorRole:'BUYER',message:'商品存在质量问题，申请售后处理',at:now}],actions:[],createdAt:now})
const cases=[caseValue(1,1,'RETURN_REFUND',params.get('state') || 'PENDING_MERCHANT'),caseValue(2,2,'EXCHANGE','WAITING_EXCHANGE'),caseValue(3,3,'REFUND_ONLY','REFUNDED')]
Object.assign(cases[1],{returnRecipient:'售后验收人',returnPhone:'010-00000000',returnAddress:'测试商家登记的退货地址',returnCompany:'测试物流',returnTrackingNo:'RETURN0002'})
Object.assign(cases[2],{approvedRefundAmount:80,refundReference:'SIM-TEST-0003',completedAt:now})
const terminal=['CANCELLED','REJECTED','RESOLVED','REFUNDED','EXCHANGED']
function actions(c:AfterSaleVO){if(role==='CUSTOMER'){if(c.status==='WAITING_EXCHANGE')return ['CONVERT_REFUND'];if(c.status==='WAITING_RETURN')return ['RETURN','CANCEL'];if(c.status.startsWith('PENDING'))return ['CANCEL'];if(c.status==='REJECTED')return ['APPEAL'];if(c.status==='EXCHANGE_SHIPPED')return ['CONFIRM_EXCHANGE'];return []}const operator=role==='ADMIN'?c.currentHandler==='PLATFORM':c.currentHandler==='MERCHANT';if(!operator)return role==='ADMIN'&&!terminal.includes(c.status)?['TAKEOVER']:[];if(c.status.startsWith('PENDING'))return ['APPROVE','REJECT'];return ({RETURN_SHIPPED:['RECEIVE'],WAITING_REFUND:['REFUND'],WAITING_EXCHANGE:['SHIP_EXCHANGE']} as Record<string,string[]>)[c.status] || []}
const view=(c:AfterSaleVO)=>({...c,actions:actions(c),convertRefundAmount:c.status==='WAITING_EXCHANGE'?40:undefined})
function eligibility(orderId:number){const order=orders.find(o=>o.orderId===orderId)!;return order.items.map(item=>{const previous=cases.filter(c=>c.orderItemId===item.orderItemId),active=previous.find(c=>!terminal.includes(c.status)),consumed=previous.filter(c=>!['REJECTED','CANCELLED','RESOLVED'].includes(c.status)).reduce((n,c)=>n+c.quantity,0);const remaining=Math.max(0,item.quantity-consumed);return {orderItemId:item.orderItemId,productName:item.productName,productImage:item.productImage,purchasedQuantity:item.quantity,availableQuantity:remaining,maxRefundAmount:remaining*40,serviceTypes:active||!remaining||order.status==='REFUNDED'?[]:order.status==='PAID'?['REFUND_ONLY']:['REFUND_ONLY','RETURN_REFUND','EXCHANGE'],activeAfterSaleId:active?.id,unavailableReason:active?'已有进行中的售后':!remaining?'可售后数量已用完':''}})}
const orderView=(o:OrderVO)=>({...o,afterSales:cases.filter(c=>c.orderId===o.orderId).map(view),afterSaleItems:eligibility(o.orderId),refundedAmount:cases.filter(c=>c.orderId===o.orderId&&c.status==='REFUNDED').reduce((n,c)=>n+Number(c.approvedRefundAmount??c.requestedRefundAmount),0)})
axios.defaults.adapter=async config=>{let data:unknown;const url=config.url || '',body=typeof config.data==='string'?JSON.parse(config.data):config.data,p=config.params || {}
 if(url==='/orders/my'){const records=orders.filter(o=>!p.status||o.status===p.status).map(orderView);data={records,total:records.length,page:1,size:10}}
 else if(/^\/orders\/\d+$/.test(url))data=orderView(orders.find(o=>o.orderId===Number(url.split('/')[2]))!)
 else if(url==='/after-sales/eligibility')data=eligibility(Number(p.orderId))
 else if(url==='/after-sales/quote')data={maxRefundAmount:p.serviceType==='EXCHANGE'?0:Number(p.quantity)*40}
 else if(url==='/after-sales/my'||url==='/after-sales/manage'){const records=cases.filter(c=>(!p.status||c.status===p.status)&&(!p.orderId||c.orderId===Number(p.orderId))).map(view);data={records,total:records.length,page:1,size:20}}
 else if(url==='/after-sales'&&config.method==='post'){const c=caseValue(cases.length+100,body.orderId,body.serviceType,'PENDING_MERCHANT');Object.assign(c,{reason:body.reason,quantity:body.quantity,requestedRefundAmount:body.refundAmount,evidence:body.evidence});cases.unshift(c);data=view(c)}
 else if(/^\/after-sales\/\d+\/actions$/.test(url)){const c=cases.find(c=>c.id===Number(url.split('/')[2]))!;if(!actions(c).includes(body.action))throw new Error('Fixture rejected unauthorized action');const transitions:Record<string,string>={TAKEOVER:c.status.startsWith('PENDING')?'PENDING_PLATFORM':c.status,APPROVE:c.serviceType==='REFUND_ONLY'?'WAITING_REFUND':'WAITING_RETURN',REJECT:'REJECTED',APPEAL:'PENDING_PLATFORM',CANCEL:'CANCELLED',RETURN:'RETURN_SHIPPED',RECEIVE:c.serviceType==='EXCHANGE'?'WAITING_EXCHANGE':'WAITING_REFUND',REFUND:'REFUNDED',CONVERT_REFUND:'WAITING_REFUND',SHIP_EXCHANGE:'EXCHANGE_SHIPPED',CONFIRM_EXCHANGE:'EXCHANGED'};c.status=transitions[body.action];if(['APPEAL','TAKEOVER'].includes(body.action))c.currentHandler='PLATFORM';if(body.action==='CONVERT_REFUND'){c.serviceType='RETURN_REFUND';c.requestedRefundAmount=40;c.approvedRefundAmount=40}if(body.action==='APPROVE'){c.returnRecipient=body.recipient;c.returnPhone=body.phone;c.returnAddress=body.address;if(c.serviceType!=='EXCHANGE')c.approvedRefundAmount=c.requestedRefundAmount}if(body.action==='RETURN'){c.returnCompany=body.company;c.returnTrackingNo=body.trackingNo}if(body.action==='SHIP_EXCHANGE'){c.exchangeCompany=body.company;c.exchangeTrackingNo=body.trackingNo}if(body.action==='REFUND')c.refundReference='SIM-FIXTURE-'+c.id;c.history.push({action:body.action,status:c.status,actorRole:role==='CUSTOMER'?'BUYER':role==='ADMIN'?'PLATFORM':'MERCHANT',message:body.reason || '',at:now});data=view(c)}
 else if(/^\/after-sales\/\d+$/.test(url))data=view(cases.find(c=>c.id===Number(url.split('/')[2]))!)
 else throw new Error('Missing after-sale fixture: '+url)
 return {data:{code:0,data},status:200,statusText:'OK',headers:{},config}
}
const [{default:MyOrdersView},{default:OrderDetailView},{default:AfterSalesView},{default:AfterSaleDetailView}]=await Promise.all([import('../src/views/MyOrdersView.vue'),import('../src/views/OrderDetailView.vue'),import('../src/views/AfterSalesView.vue'),import('../src/views/AfterSaleDetailView.vue')])
const router=createRouter({history:createMemoryHistory(),routes:[{path:'/orders',component:MyOrdersView},{path:'/orders/:id',component:OrderDetailView},...['','/merchant','/admin'].flatMap(prefix=>[{path:prefix+'/after-sales',component:AfterSalesView,meta:{afterSaleManage:!!prefix}},{path:prefix+'/after-sales/:id',component:AfterSaleDetailView,meta:{afterSaleManage:!!prefix}}]),{path:'/assistant',component:{render:()=>h('p','客服跳转成功（测试页面）')}},{path:'/products/:id?',component:{render:()=>h('p','商品跳转成功（测试页面）')}}]})
await router.replace(params.get('case') || '/orders')
createApp({render:()=>h(RouterView)}).use(router).mount('#app')
document.getElementById('fixture-orders')!.addEventListener('click',()=>void router.push('/orders'))
document.getElementById('fixture-role')!.addEventListener('change',event=>{role=(event.target as HTMLSelectElement).value;const base=role==='CUSTOMER'?'/after-sales':role==='MERCHANT'?'/merchant/after-sales':'/admin/after-sales';void router.push(base+(router.currentRoute.value.params.id?'/'+router.currentRoute.value.params.id:''))})
