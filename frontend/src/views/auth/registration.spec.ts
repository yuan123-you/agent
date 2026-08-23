import { describe, expect, it } from 'vitest'
import loginSource from '../LoginView.vue?raw'
import { buildRegistrationPayload, validateRegistration } from './registration'

const baseForm = () => ({ username: 'buyer01', password: '123456', nickname: '买家' })

describe('registration helpers', () => {
  it('accepts a complete customer registration', () => {
    expect(validateRegistration('CUSTOMER', baseForm())).toEqual([])
  })

  it('requires a shop name for merchant registration', () => {
    expect(validateRegistration('MERCHANT', baseForm())).toContain('请输入店铺名称')
  })

  it('renders an optional phone field and initializes it in the registration form', () => {
    expect(loginSource).toContain('v-model="regForm.phone"')
    expect(loginSource).toMatch(/regForm = reactive\(\{[^}]*phone: ''/s)
  })

  it.each(['CUSTOMER', 'MERCHANT'] as const)('includes a trimmed optional phone in the %s payload', kind => {
    const form = { ...baseForm(), phone: ' 13800000000 ', shopName: '源选店' }
    expect(buildRegistrationPayload(kind, form)).toMatchObject({ phone: '13800000000' })
  })

  it('trims the merchant shop name in the submitted payload', () => {
    expect(buildRegistrationPayload('MERCHANT', { ...baseForm(), shopName: ' 源选店 ' }))
      .toMatchObject({ shopName: '源选店' })
  })
})