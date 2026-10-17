import { describe, expect, it } from 'vitest'
import { buildRegistrationPayload, validateRegistration } from './registration'

const baseForm = () => ({ username: 'buyer01', password: '123456' })

describe('registration helpers', () => {
  it('accepts a customer with only username and password', () => {
    expect(validateRegistration('CUSTOMER', baseForm())).toEqual([])
  })

  it('still requires username and password', () => {
    expect(validateRegistration('CUSTOMER', { username: ' ', password: '' }))
      .toEqual(['请输入用户名', '请输入密码'])
  })

  it('requires a shop name for merchant registration', () => {
    expect(validateRegistration('MERCHANT', baseForm())).toEqual(['请输入店铺名称'])
  })

  it('accepts a merchant with username, password and shop name', () => {
    expect(validateRegistration('MERCHANT', { ...baseForm(), shopName: '源选店' })).toEqual([])
  })

  it('uses the trimmed username as nickname without requesting a phone', () => {
    expect(buildRegistrationPayload('CUSTOMER', { username: ' buyer01 ', password: '123456' }))
      .toEqual({ username: 'buyer01', password: '123456', nickname: 'buyer01' })
  })

  it('trims the merchant shop name and defaults nickname to username', () => {
    expect(buildRegistrationPayload('MERCHANT', { ...baseForm(), shopName: ' 源选店 ' }))
      .toEqual({ username: 'buyer01', password: '123456', nickname: 'buyer01', shopName: '源选店' })
  })
})
