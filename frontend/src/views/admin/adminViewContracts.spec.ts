import { describe, expect, it } from 'vitest'
import productManageSource from './ProductManageView.vue?raw'
import profileSource from '../ProfileView.vue?raw'
import loginSource from '../LoginView.vue?raw'
import merchantLayoutSource from '../../layouts/MerchantLayout.vue?raw'
import productDetailSource from '../ProductDetailView.vue?raw'
import dashboardSource from './DashboardView.vue?raw'
import apiSource from '../../api/index.ts?raw'

describe('admin view source contracts', () => {
  it('removes admin product editing', () => {
    expect(productManageSource).not.toContain('openEdit')
    expect(productManageSource).not.toContain('apiAdminProductUpdate')
    expect(productManageSource).not.toContain('编辑商品')
    expect(apiSource).not.toContain('apiAdminProductUpdate')
    expect(apiSource).toContain('apiMerchantUpdate')
    expect(apiSource).toContain('/merchant/products/${id}')
  })

  it('uses seller for visible merchant roles', () => {
    expect(profileSource).not.toMatch(/MERCHANT.*['\"]商家['\"]/)
    expect(loginSource).not.toContain('merchant01 商家')
  })

  it('calls the merchant workspace the seller center', () => {
    expect(merchantLayoutSource).toContain('卖家中心')
    expect(merchantLayoutSource).not.toContain('商家中心')
  })

  it('calls the dashboard merchant metric the seller count', () => {
    expect(dashboardSource).toContain('卖家数量')
    expect(dashboardSource).not.toContain('商家数量')
  })

  it('keeps merchant reply as an allowed business phrase', () => {
    expect(productDetailSource).toContain('商家回复')
  })
})
