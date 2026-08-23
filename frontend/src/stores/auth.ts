/** 认证状态（Pinia） */
import { defineStore } from 'pinia'
import { apiLogin, apiLogout, apiMe, apiRegister } from '@/api'
import type { LoginResp, UserInfo } from '@/types/api'

interface AuthState {
  token: string
  refreshToken: string
  user: UserInfo | null
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    token: localStorage.getItem('token') || '',
    refreshToken: localStorage.getItem('refreshToken') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null'),
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    role: (s) => s.user?.role || '',
    isCustomer: (s) => s.user?.role === 'CUSTOMER',
    isAdmin: (s) => s.user?.role === 'ADMIN',
    isAgent: (s) => s.user?.role === 'AGENT',
  },
  actions: {
    setAuth(data: LoginResp) {
      if (data.accessToken) this.token = data.accessToken
      if (data.refreshToken) this.refreshToken = data.refreshToken
      if (data.user) this.user = data.user
      localStorage.setItem('token', this.token)
      localStorage.setItem('refreshToken', this.refreshToken)
      localStorage.setItem('user', JSON.stringify(this.user))
    },
    logoutLocal() {
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
    async register(payload: { username: string; password: string; nickname: string; phone?: string }) {
      return apiRegister(payload)
    },
    async logout() {
      try {
        await apiLogout()
      } catch {
        // 忽略登出接口异常
      } finally {
        this.logoutLocal()
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
      if (this.isAdmin) return '/admin/products'
      if (this.isAgent) return '/workbench'
      if (this.role === 'MERCHANT') return '/merchant/products'
      return '/'
    },
  },
})

