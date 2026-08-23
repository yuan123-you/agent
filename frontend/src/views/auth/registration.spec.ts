import { describe, expect, it } from 'vitest'
import { buildRegistrationPayload, validateRegistration } from './registration'

const baseForm = () => ({ username: 'buyer01', password: '123456', nickname: '买家' })

describe('registration helpers', () => {
  it('accepts a complete customer registration', () => {
    expect(validateRegistration('CUSTOMER', baseForm())).toEqual([])
  })

  it('requires a shop name for merchant registration', () => {
    expect(validateRegistration('MERCHANT', baseForm())).toContain('请输入店铺名称')
  })

  it('trims the merchant shop name in the submitted payload', () => {
    expect(buildRegistrationPayload('MERCHANT', { ...baseForm(), shopName: ' 源选店 ' }))
      .toMatchObject({ shopName: '源选店' })
  })
})