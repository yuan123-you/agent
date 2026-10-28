import { API_BASE } from '@/api/base'
/**
 * axios 封装：token 注入 + 过期预刷新 + 401 自动刷新重放 + 统一错误提示
 * （token 直接读写 localStorage，避免与 store 循环依赖）
 */
import axios from 'axios'
import type { AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

/** Backend image routes are origin-relative; respect Vite's deployment subpath. */
function resolveProductImages(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(resolveProductImages)
  if (!value || typeof value !== 'object') return value
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key,
    ['imageUrl', 'productImage', 'pic'].includes(key) && typeof item === 'string' && item.startsWith('/api/v1/product-images/')
      ? `${import.meta.env.BASE_URL.replace(/\/$/, '')}${item}`
      : resolveProductImages(item),
  ]))
}

const instance = axios.create({ baseURL: API_BASE, timeout: 30000 })

let unauthorizedHandler: () => void = () => {}
export function setUnauthorizedHandler(fn: () => void) {
  unauthorizedHandler = fn
}

let refreshing: Promise<string | null> | null = null

async function tryRefresh(): Promise<string | null> {
  const refreshToken = localStorage.getItem('refreshToken')
  if (!refreshToken) return null
  if (!refreshing) {
    refreshing = axios
      .post(`${API_BASE}/auth/refresh`, { refreshToken }, { timeout: 10000 })
      .then((resp) => {
        const body = resp.data
        const token = body?.data?.accessToken as string | undefined
        if (token) {
          localStorage.setItem('token', token)
          return token
        }
        return null
      })
      .catch(() => null)
      .finally(() => {
        setTimeout(() => (refreshing = null), 100)
      })
  }
  return refreshing
}

function clearAuthentication() {
  localStorage.removeItem('token')
  localStorage.removeItem('refreshToken')
  localStorage.removeItem('user')
  unauthorizedHandler()
}

function isExpired(token: string): boolean {
  try {
    // Only schedule refresh locally; signature/permission checks remain on the server.
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    const { exp } = JSON.parse(atob(payload))
    return typeof exp === 'number' && exp * 1000 <= Date.now()
  } catch {
    return false
  }
}

instance.interceptors.request.use(async (config) => {
  let token = localStorage.getItem('token')
  const path = (config.url || '').split('?')[0]
  const signingIn = /^\/auth\/(login|register)(\/|$)/.test(path)
  if (token && !signingIn && !(config as AxiosRequestConfig & { _authRetried?: boolean })._authRetried && isExpired(token)) {
    token = await tryRefresh()
    if (!token) {
      clearAuthentication()
      const publicRead = config.method === 'get' && /^(?:\/(?:products|catalog)(?:\/|$)|\/promotions\/(?:seckills|coupons)$)/.test(path)
      if (!publicRead) throw new axios.CanceledError('登录已过期，请重新登录')
      config.headers.delete('Authorization')
    }
  }
  if (token && !signingIn) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

instance.interceptors.response.use(
  (resp) => {
    const body = resp.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 0) {
        return resolveProductImages(body.data)
      }
      ElMessage.error(body.message || '请求失败')
      return Promise.reject(body)
    }
    return body
  },
  async (error) => {
    // 静默处理取消与中断请求
    if (axios.isCancel(error) || error?.name === 'CanceledError' || error?.name === 'AbortError') {
      return Promise.reject(error)
    }
    const status = error.response?.status
    const body = error.response?.data
    const code = body?.code
    if (status === 401 || code === 1003) {
      // 登录接口的 401 = 凭据错误，展示具体原因而非触发「未登录」跳转
      if (error.config?.url?.includes('/auth/login')) {
        ElMessage.error(body?.message || '用户名或密码错误')
        return Promise.reject(body)
      }
      const config = error.config as (AxiosRequestConfig & { _authRetried?: boolean }) | undefined
      if (config && !config._authRetried) {
        config._authRetried = true
        const token = await tryRefresh()
        if (token) return instance(config)
      }
      clearAuthentication()
      return Promise.reject(body)
    }
    // silent: true 时静默失败（轮询等高频请求，不打扰用户）
    if (!(error.config as { silent?: boolean } | undefined)?.silent) {
      ElMessage.error(body?.message || '网络错误，请稍后重试')
    }
    return Promise.reject(body || error)
  },
)

/** 拦截器返回的已是 data 字段，这里做类型转换 */
export async function get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return (await instance.get(url, config)) as T
}

export async function post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return (await instance.post(url, data, config)) as T
}

export async function put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return (await instance.put(url, data, config)) as T
}

export async function del<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return (await instance.delete(url, config)) as T
}

export async function upload<T>(url: string, formData: FormData): Promise<T> {
  return (await instance.post(url, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })) as T
}

export default instance
