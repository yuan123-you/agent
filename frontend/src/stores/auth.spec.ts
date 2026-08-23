import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from './auth'
import type { UserInfo } from '@/types/api'

const { apiRegisterCustomer, apiRegisterMerchant } = vi.hoisted(() => ({
  apiRegisterCustomer: vi.fn(),
  apiRegisterMerchant: vi.fn(),
}))

vi.mock('@/api', () => ({
  apiLogin: vi.fn(),
  apiLogout: vi.fn(),
  apiMe: vi.fn(),
  apiRegister: vi.fn(),
  apiRegisterCustomer,
  apiRegisterMerchant,
}))

describe('auth home route', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it.each([
    ['CUSTOMER', '/'],
    ['MERCHANT', '/merchant/products'],
    ['AGENT', '/workbench'],
    ['ADMIN', '/admin/products'],
  ])('routes a %s login to an existing role home page', (role, expectedRoute) => {
    const auth = useAuthStore()
    auth.user = { role } as UserInfo

    expect(auth.homeRoute()).toBe(expectedRoute)
  })
})

describe('registration actions', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('sends customer registrations to the customer endpoint', async () => {
    const payload = { username: 'buyer01', password: '123456', nickname: '买家' }
    const auth = useAuthStore()

    await auth.registerCustomer(payload)

    expect(apiRegisterCustomer).toHaveBeenCalledWith(payload)
  })

  it('sends merchant registrations to the merchant endpoint', async () => {
    const payload = { username: 'seller01', password: '123456', nickname: '卖家', shopName: '源选店' }
    const auth = useAuthStore()

    await auth.registerMerchant(payload)

    expect(apiRegisterMerchant).toHaveBeenCalledWith(payload)
  })
})
