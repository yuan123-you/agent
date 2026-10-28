import { describe, expect, it } from 'vitest'
import { afterSaleStatusText, afterSaleTypeText, afterSaleBase, canApplyAfterSale } from './afterSale'

describe('after-sale presentation and eligibility', () => {
  it('never labels a simulated refund as a real bank settlement', () => {
    expect(afterSaleStatusText('REFUNDED','SIMULATED')).toContain('模拟')
    expect(afterSaleStatusText('WAITING_REFUND')).toBe('待退款')
  })
  it('distinguishes returns from exchanges and buyer from management links', () => {
    expect(afterSaleTypeText('RETURN_REFUND')).toBe('退货退款')
    expect(afterSaleTypeText('EXCHANGE')).toBe('换货')
    expect(afterSaleBase('/merchant/after-sales/1')).toBe('/merchant/after-sales')
    expect(afterSaleBase('/orders/1')).toBe('/after-sales')
  })
  it('offers applications only from server eligibility, never from guessed fulfillment state', () => {
    expect(canApplyAfterSale({ status:'PAID' } as any)).toBe(false)
    expect(canApplyAfterSale({ afterSaleItems:[{orderItemId:1,availableQuantity:1,serviceTypes:['REFUND_ONLY']}] } as any,1)).toBe(true)
    expect(canApplyAfterSale({ afterSaleItems:[{orderItemId:1,availableQuantity:1,serviceTypes:[],activeAfterSaleId:5}] } as any,1)).toBe(false)
  })
})
