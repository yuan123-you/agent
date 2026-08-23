import { describe, expect, it } from 'vitest'
import { USER_TABS, canCreateAgent, roleText } from './userManagement'

describe('admin user management helpers', () => {
  it('defines isolated buyer, seller, and agent tabs', () => {
    expect(USER_TABS.map(t => t.role)).toEqual(['CUSTOMER', 'MERCHANT', 'AGENT'])
  })

  it('uses the buyer-facing seller label while retaining the MERCHANT code', () => {
    expect(roleText('MERCHANT')).toBe('卖家')
  })

  it('only permits agent creation in the agent tab', () => {
    expect(canCreateAgent('AGENT')).toBe(true)
    expect(canCreateAgent('CUSTOMER')).toBe(false)
  })
})
