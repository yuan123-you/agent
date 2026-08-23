import { describe, expect, it } from 'vitest'
import type { AddressVO } from '@/types/api'
import { preferredAddress } from './checkoutAddress'

const address = (addressId: number, isDefault = false): AddressVO => ({
  addressId,
  receiverName: `买家${addressId}`,
  receiverPhone: '13800000000',
  receiverAddress: `测试地址${addressId}`,
  province: '浙江省',
  city: '杭州市',
  district: '西湖区',
  detailAddress: `文三路${addressId}号`,
  isDefault,
})

describe('checkout address selection', () => {
  it('selects the default saved address even when it is not first', () => {
    expect(preferredAddress([address(1), address(2, true)])?.addressId).toBe(2)
  })

  it('falls back to the first saved address and handles an empty book', () => {
    expect(preferredAddress([address(3), address(4)])?.addressId).toBe(3)
    expect(preferredAddress([])).toBeUndefined()
  })
})
