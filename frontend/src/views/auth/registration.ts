import type { CustomerRegistration, MerchantRegistration } from '@/types/api'

export type RegistrationKind = 'CUSTOMER' | 'MERCHANT'
export type RegistrationForm = Pick<CustomerRegistration, 'username' | 'password'> & { shopName?: string }

export function validateRegistration(kind: RegistrationKind, form: RegistrationForm): string[] {
  const errors: string[] = []
  if (!form.username.trim()) errors.push('请输入用户名')
  if (!form.password) errors.push('请输入密码')
  if (kind === 'MERCHANT' && !form.shopName?.trim()) errors.push('请输入店铺名称')
  return errors
}

export function buildRegistrationPayload(kind: RegistrationKind, form: RegistrationForm): CustomerRegistration | MerchantRegistration {
  const customer = {
    username: form.username.trim(),
    password: form.password,
    nickname: form.username.trim(),
  }
  return kind === 'MERCHANT' ? { ...customer, shopName: form.shopName?.trim() || '' } : customer
}