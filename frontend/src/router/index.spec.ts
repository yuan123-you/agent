import { beforeEach, describe, expect, it } from 'vitest'
import router from './index'

function loginAs(role: string) {
  localStorage.setItem('token', 'test-token')
  localStorage.setItem('user', JSON.stringify({ role }))
}

describe('role landing routes', () => {
  beforeEach(async () => {
    localStorage.clear()
    await router.replace('/login')
  })

  it.each([
    ['ADMIN', '/admin/dashboard'],
    ['AGENT', '/workbench'],
    ['MERCHANT', '/merchant/products'],
  ])('redirects %s away from the customer homepage', async (role, expectedRoute) => {
    loginAs(role)

    await router.push('/')

    expect(router.currentRoute.value.path).toBe(expectedRoute)
  })

  it('keeps a customer on the customer homepage', async () => {
    loginAs('CUSTOMER')

    await router.push('/')

    expect(router.currentRoute.value.path).toBe('/')
  })
})
