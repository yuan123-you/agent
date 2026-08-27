import { describe, expect, it } from 'vitest'
import type { RegionOption } from '@/components/address/addressForm'
import {
  MAX_CUSTOM_PRODUCT_INFO,
  isCompleteProductLocation,
  locationCodesForValue,
  locationValueForCodes,
  parseCustomProductInfo,
  serializeCustomProductInfo,
  validateCustomProductInfo,
} from './productForm'

describe('custom product information', () => {
  it('serializes completed entries after trimming user input', () => {
    expect(serializeCustomProductInfo([
      { name: ' 屏幕 ', content: ' 6.7英寸 ' },
      { name: '', content: '' },
    ])).toBe('{"屏幕":"6.7英寸"}')
  })

  it('parses existing product information for editing', () => {
    expect(parseCustomProductInfo('{"屏幕":"6.7英寸","电池":"5000mAh"}')).toEqual([
      { name: '屏幕', content: '6.7英寸' },
      { name: '电池', content: '5000mAh' },
    ])
  })

  it('keeps numeric legacy content editable', () => {
    expect(parseCustomProductInfo('{"重量":180}')).toEqual([{ name: '重量', content: '180' }])
  })

  it('ignores malformed legacy content instead of breaking the edit dialog', () => {
    expect(parseCustomProductInfo('not valid')).toEqual([])
  })

  it('limits legacy content to the five editable entries', () => {
    const legacy = Object.fromEntries(Array.from({ length: 7 }, (_, index) => [`名称${index}`, `内容${index}`]))
    expect(parseCustomProductInfo(JSON.stringify(legacy))).toHaveLength(MAX_CUSTOM_PRODUCT_INFO)
  })

  it('requires both fields when either side is entered', () => {
    expect(validateCustomProductInfo([{ name: '屏幕', content: '' }])).toBe('请完整填写选项名称和选项内容')
  })

  it('rejects repeated names', () => {
    expect(validateCustomProductInfo([
      { name: '屏幕', content: '6.7英寸' },
      { name: ' 屏幕 ', content: 'OLED' },
    ])).toBe('选项名称不能重复')
  })

  it('rejects more than five entries', () => {
    const entries = Array.from({ length: 6 }, (_, index) => ({ name: `名称${index}`, content: `内容${index}` }))
    expect(validateCustomProductInfo(entries)).toBe('最多只能添加5项商品信息')
  })
})


describe('product location selection', () => {
  const options: RegionOption[] = [{
    value: '44', label: '广东省', children: [{
      value: '4401', label: '广州市', children: [{ value: '440106', label: '天河区' }],
    }],
  }]

  it('requires all three location levels', () => {
    expect(isCompleteProductLocation(['44', '4401'])).toBe(false)
    expect(isCompleteProductLocation(['44', '4401', '440106'])).toBe(true)
  })

  it('stores the selected location as readable text', () => {
    expect(locationValueForCodes(options, ['44', '4401', '440106'])).toBe('广东省 / 广州市 / 天河区')
  })

  it('restores both current and legacy location text', () => {
    expect(locationCodesForValue(options, '广东省 / 广州市 / 天河区')).toEqual(['44', '4401', '440106'])
    expect(locationCodesForValue(options, '广东省广州市天河区')).toEqual(['44', '4401', '440106'])
  })
})
