import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from './auth'
import type { UserInfo } from '@/types/api'

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
