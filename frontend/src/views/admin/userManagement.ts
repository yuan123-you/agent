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
