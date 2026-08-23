import { describe, expect, it } from 'vitest'
import { USER_TABS, canCreateAgent, createLatestRequestRunner, roleText } from './userManagement'

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

  it('drops an in-flight stale response and then loads the latest role', async () => {
    type Request = { role: string; resolve: (records: string[]) => void }
    const requests: Request[] = []
    const applied: Array<{ role: string; records: string[] }> = []
    const loadingStates: boolean[] = []
    const run = createLatestRequestRunner(
      (role: string) => new Promise<string[]>(resolve => requests.push({ role, resolve })),
      (records, role) => applied.push({ role, records }),
      loading => loadingStates.push(loading),
    )

    const customerRun = run('CUSTOMER')
    const merchantRun = run('MERCHANT')
    expect(requests.map(request => request.role)).toEqual(['CUSTOMER'])

    requests[0].resolve(['old customer'])
    await Promise.resolve()
    expect(applied).toEqual([])
    expect(requests.map(request => request.role)).toEqual(['CUSTOMER', 'MERCHANT'])

    requests[1].resolve(['current merchant'])
    await Promise.all([customerRun, merchantRun])
    expect(applied).toEqual([{ role: 'MERCHANT', records: ['current merchant'] }])
    expect(loadingStates).toEqual([true, false])
  })
})
