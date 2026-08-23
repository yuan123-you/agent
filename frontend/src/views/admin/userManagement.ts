export type UserRoleTab = 'CUSTOMER' | 'MERCHANT' | 'AGENT'

export const USER_TABS: ReadonlyArray<{ role: UserRoleTab; label: string }> = [
  { role: 'CUSTOMER', label: '买家' },
  { role: 'MERCHANT', label: '卖家' },
  { role: 'AGENT', label: '客服' },
]

export function roleText(role: string): string {
  return { ADMIN: '管理员', AGENT: '客服', CUSTOMER: '买家', MERCHANT: '卖家' }[role] || role
}

export function canCreateAgent(role: string): boolean {
  return role === 'AGENT'
}

export function createLatestRequestRunner<Params, Result>(
  request: (params: Params) => Promise<Result>,
  apply: (result: Result, params: Params) => void,
  setLoading: (loading: boolean) => void,
): (params: Params) => Promise<void> {
  let latestSequence = 0
  let queued: { sequence: number; params: Params } | undefined
  let running = false
  let activeRun: Promise<void> | undefined

  async function drain() {
    setLoading(true)
    try {
      while (queued) {
        const current = queued
        queued = undefined
        try {
          const result = await request(current.params)
          if (current.sequence === latestSequence) apply(result, current.params)
        } catch (error) {
          if (current.sequence === latestSequence) throw error
        }
      }
    } finally {
      setLoading(false)
      running = false
    }
  }

  return (params: Params) => {
    queued = { sequence: ++latestSequence, params }
    if (!running) {
      running = true
      activeRun = drain()
    }
    return activeRun!
  }
}
