import { describe, expect, it } from 'vitest'
import { composeAddress, normalizeGeocode } from './addressForm'

describe('address form helpers', () => {
  it('composes province city district and a trimmed detail address', () => {
    expect(composeAddress(['浙江省', '杭州市', '西湖区'], ' 文三路 90 号 '))
      .toBe('浙江省杭州市西湖区文三路 90 号')
  })

  it('normalizes reverse geocode data without duplicating city as district', () => {
    expect(normalizeGeocode({
      principalSubdivision: '浙江省', city: '杭州市', locality: '西湖区',
    })).toEqual({ province: '浙江省', city: '杭州市', district: '西湖区' })
    expect(normalizeGeocode({
      principalSubdivision: '北京市', city: '北京市', locality: '北京市',
    })).toEqual({ province: '北京市', city: '北京市', district: '' })
  })
})
