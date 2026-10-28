import {describe,it,expect} from 'vitest'
import router from './index'
describe('after-sale route ownership',()=>{
  it.each(['/admin/after-sales','/admin/after-sales/1','/merchant/after-sales','/merchant/after-sales/1'])('keeps %s in the management workflow',path=>{expect(router.resolve(path).meta.afterSaleManage).toBe(true)})
  it.each(['/after-sales','/after-sales/1'])('keeps %s in the buyer workflow',path=>{expect(router.resolve(path).meta.afterSaleManage).not.toBe(true);expect(router.resolve(path).meta.customer).toBe(true)})
})
