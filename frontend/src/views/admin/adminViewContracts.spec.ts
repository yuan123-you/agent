import { describe, expect, it } from 'vitest'
import productManageSource from './ProductManageView.vue?raw'
import profileSource from '../ProfileView.vue?raw'
import loginSource from '../LoginView.vue?raw'

describe('admin view source contracts', () => {
  it('removes admin product editing', () => {
    expect(productManageSource).not.toContain('openEdit')
    expect(productManageSource).not.toContain('apiAdminProductUpdate')
    expect(productManageSource).not.toContain('编辑商品')
  })

  it('uses seller for visible merchant roles', () => {
    expect(profileSource).not.toMatch(/MERCHANT.*['\"]商家['\"]/)
    expect(loginSource).not.toContain('merchant01 商家')
  })
})