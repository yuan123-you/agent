import { describe, expect, it } from 'vitest'
import { codesForLabels, composeAddress, normalizeGeocode, type RegionOption } from './addressForm'

describe('address form helpers', () => {
  it('composes province city district and a trimmed detail address', () => {
    expect(composeAddress(['浙江省', '杭州市', '西湖区'], ' 文三路 90 号 '))
      .toBe('浙江省杭州市西湖区文三路 90 号')
  })

  it('normalizes reverse geocode data without duplicating city as district', () => {
    expect(normalizeGeocode({
      principalSubdivision: '浙江省', city: '杭州市', locality: '西湖区',
    })).toEqual({ province: '浙江省', city: '杭州市', district: '西湖区', detailAddress: '' })
  })

  it('uses administrative hierarchy for a municipality and extracts usable detail text', () => {
    expect(normalizeGeocode({
      principalSubdivision: '北京市',
      city: '北京市',
      locality: '中关村街道',
      localityInfo: {
        administrative: [
          { name: '中国', description: 'country' },
          { name: '北京市', description: 'province' },
          { name: '北京市', description: 'city' },
          { name: '海淀区', description: 'district' },
          { name: '中关村街道', description: 'locality' },
        ],
        informative: [{ name: '知春路', description: 'road' }],
      },
    })).toEqual({
      province: '北京市', city: '北京市', district: '海淀区', detailAddress: '中关村街道知春路',
    })
  })

  it('matches common autonomous-region and municipality label variants', () => {
    const options: RegionOption[] = [{
      value: '11', label: '北京市', children: [{
        value: '1101', label: '市辖区', children: [{ value: '110108', label: '海淀区' }],
      }],
    }]
    expect(codesForLabels(options, ['北京', '北京市', '海淀区'])).toEqual(['11', '1101', '110108'])
  })
})
