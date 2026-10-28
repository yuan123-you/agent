/** 认证状态（Pinia） */
import { defineStore } from 'pinia'
import { useChatStore } from './chat'
import { clearHotContentCache } from '@/api/hotContentCache'
import { apiLogin, apiLogout, apiMe, apiRegister, apiRegisterCustomer, apiRegisterMerchant } from '@/api'
import type { CustomerRegistration, LoginResp, MerchantRegistration, UserInfo } from '@/types/api'

export function homeRouteForRole(role: string): string {
  if (role === 'ADMIN') return '/admin/dashboard'
  if (role === 'AGENT') return '/workbench'
  if (role === 'MERCHANT') return '/merchant/products'
  return '/'
}

interface AuthState {
  token: string
  refreshToken: string
  user: UserInfo | null
}

/** A malformed UI cache must not crash startup or retain an unusable credential pair. */
function storedAuthState(): AuthState {
  try {
    const token = localStorage.getItem('token') || ''
    const refreshToken = localStorage.getItem('refreshToken') || ''
    const value: unknown = JSON.parse(localStorage.getItem('user') || 'null')
    if (token && value && typeof value === 'object' && !Array.isArray(value)) {
      const user = value as Record<string, unknown>
      const role = user.role
      if (Number.isSafeInteger(user.userId) && Number(user.userId) > 0 && typeof user.username === 'string'
        && (typeof user.nickname === 'string' || user.nickname == null)
        && (role === 'ADMIN' || role === 'AGENT' || role === 'CUSTOMER' || role === 'MERCHANT')) {
        return { token, refreshToken, user: {
          userId: Number(user.userId), username: user.username,
          nickname: typeof user.nickname === 'string' ? user.nickname : user.username, role,
          ...(typeof user.phone === 'string' ? { phone: user.phone } : {}),
          ...(typeof user.email === 'string' ? { email: user.email } : {}),
        } }
      }
    } else if (!token && !refreshToken && value === null) {
      return { token: '', refreshToken: '', user: null }
    }
  } catch { /* Recover corrupt or inaccessible local storage as a signed-out state. */ }
  clearHotContentCache()
  try { for (const key of ['token', 'refreshToken', 'user']) localStorage.removeItem(key) } catch { /* Storage can be unavailable. */ }
  return { token: '', refreshToken: '', user: null }
}

export const useAuthStore = defineStore('auth', {
  state: storedAuthState,
  getters: {
    isLoggedIn: (s) => !!s.token,
    role: (s) => s.user?.role || '',
    isCustomer: (s) => s.user?.role === 'CUSTOMER',
    isAdmin: (s) => s.user?.role === 'ADMIN',
    isAgent: (s) => s.user?.role === 'AGENT',
  },
  actions: {
    setAuth(data: LoginResp) {
      if (data.user && data.user.userId !== this.user?.userId) useChatStore().resetSession()
      clearHotContentCache()
      if (data.accessToken) this.token = data.accessToken
      if (data.refreshToken) this.refreshToken = data.refreshToken
      if (data.user) this.user = data.user
      localStorage.setItem('token', this.token)
      localStorage.setItem('refreshToken', this.refreshToken)
      localStorage.setItem('user', JSON.stringify(this.user))
    },
    logoutLocal() {
      useChatStore().resetSession()
      clearHotContentCache()
      this.token = ''
      this.refreshToken = ''
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('refreshToken')
      localStorage.removeItem('user')
    },
    async login(payload: { username: string; password: string }) {
      const data = await apiLogin(payload)
      this.setAuth(data)
      return data
    },
    async register(payload: CustomerRegistration) {
      return apiRegister(payload)
    },
    async registerCustomer(payload: CustomerRegistration) {
      return apiRegisterCustomer(payload)
    },
    async registerMerchant(payload: MerchantRegistration) {
      return apiRegisterMerchant(payload)
    },
    async logout() {
      const session = localStorage.getItem('refreshToken') || localStorage.getItem('token')
      try {
        await apiLogout()
      } catch {
        // 忽略登出接口异常
      } finally {
        if (session === (localStorage.getItem('refreshToken') || localStorage.getItem('token'))) this.logoutLocal()
      }
    },
    async fetchMe() {
      const user = await apiMe()
      this.user = user
      localStorage.setItem('user', JSON.stringify(user))
      return user
    },
    /** 登录后按角色跳转默认页 */
    homeRoute(): string {
      return homeRouteForRole(this.role)
    },
  },
})
