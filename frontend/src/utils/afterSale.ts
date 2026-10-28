import type { OrderVO } from '@/types/api'
export const afterSaleTypes: Record<string,string> = { REFUND_ONLY:'仅退款', RETURN_REFUND:'退货退款', EXCHANGE:'换货', ISSUE_REPORT:'问题反馈' }
export const afterSaleStates: Record<string,string> = { PENDING_MERCHANT:'待商家审核', PENDING_PLATFORM:'待平台处理', WAITING_RETURN:'待买家退货', RETURN_SHIPPED:'退货运输中', WAITING_REFUND:'待退款', WAITING_EXCHANGE:'待换货发出', EXCHANGE_SHIPPED:'换货运输中', REFUNDED:'退款完成', EXCHANGED:'换货完成', REJECTED:'申请被拒绝', CANCELLED:'申请已撤销', RESOLVED:'问题已处理' }
export const afterSaleActionText: Record<string,string> = { APPLY:'提交申请', APPROVE:'同意申请', REJECT:'拒绝申请', CANCEL:'撤销申请', RETURN:'填写退货物流', RECEIVE:'确认收到退货', REFUND:'执行模拟退款', SHIP_EXCHANGE:'寄出换货商品', CONFIRM_EXCHANGE:'确认收到换货', APPEAL:'申请平台介入', CONVERT_REFUND:'换货转退款', TAKEOVER:'平台接管' }
export const afterSaleTypeText=(type:string)=>afterSaleTypes[type] || type
export const afterSaleStatusText=(status:string,mode?:string)=> status==='REFUNDED' && mode==='SIMULATED' ? '退款完成（模拟）' : afterSaleStates[status] || status
export const afterSaleBase=(path:string)=>path.startsWith('/admin/')?'/admin/after-sales':path.startsWith('/merchant/')?'/merchant/after-sales':'/after-sales'
export function canApplyAfterSale(order: OrderVO, itemId?: number) { return !!order.afterSaleItems?.some(item=>(itemId===undefined || item.orderItemId===itemId) && item.availableQuantity>0 && item.serviceTypes.length>0 && !item.activeAfterSaleId) }
export const afterSaleMoney=(amount:number | undefined)=>Number(amount || 0).toFixed(2)
export const afterSaleTime=(time?:string)=>time?.replace('T',' ').slice(0,19) || '—'
