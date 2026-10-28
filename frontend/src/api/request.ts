import { API_BASE } from '@/api/base'
import { clearHotContentCache, isPublicHotContentRoute, readHotContent } from './hotContentCache'
/**
 * axios 封装：token 注入 + 过期预刷新 + 401 自动刷新重放 + 统一错误提示
 * （token 直接读写 localStorage，避免与 store 循环依赖）
 */
import axios from 'axios'
import type { AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

/** Backend image routes are origin-relative; respect Vite's deployment subpath. */
function resolveProductImages(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(resolveProductImages)
  if (!value || typeof value !== 'object') return value
  const prototype = Object.getPrototypeOf(value)
  if (prototype !== Object.prototype && prototype !== null) return value
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

interface SessionRequest { _authSession?: string | null; _authRetried?: boolean }

// Keep credentials out of request metadata and error/telemetry serialization.
let sessionCredential: string | null = null
let sessionSequence = 0
let sessionMarker: string | null = null
function sessionIdentity(): string | null {
  const credential = localStorage.getItem('refreshToken') || localStorage.getItem('token')
  if (credential !== sessionCredential) {
    sessionCredential = credential
    sessionMarker = credential === null ? null : `session:${++sessionSequence}`
  }
  return sessionMarker
}

function isPublicRead(config: AxiosRequestConfig): boolean {
  const path = (config.url || '').split('?')[0]
  return config.method === 'get' && /^(?:\/(?:products|catalog)(?:\/|$)|\/promotions\/(?:seckills|coupons)$)/.test(path)
}

function assertCurrentSession(config: SessionRequest): void {
  if ('_authSession' in config && config._authSession !== sessionIdentity()) {
    throw new axios.CanceledError('登录状态已变化，请重新提交操作')
  }
}

let refreshing: Promise<string | null> | null = null
let refreshingFor: string | null = null

async function tryRefresh(): Promise<string | null> {
  const refreshToken = localStorage.getItem('refreshToken')
  if (!refreshToken) return null
  if (!refreshing || refreshingFor !== refreshToken) {
    const accessToken = localStorage.getItem('token')
    const pending = axios
      .post(`${API_BASE}/auth/refresh`, { refreshToken }, { timeout: 10000 })
      .then((resp) => {
        const body = resp.data
        const token = body?.data?.accessToken as string | undefined
        if (localStorage.getItem('refreshToken') !== refreshToken) return null
        // Another tab can refresh this same session first; retain its newer access token.
        if (localStorage.getItem('token') !== accessToken) return localStorage.getItem('token')
        if (token) {
          localStorage.setItem('token', token)
          return token
        }
        return null
      })
      .catch(() => {
        // A failed refresh in this tab must not erase a peer's newer token for the same session.
        if (localStorage.getItem('refreshToken') === refreshToken && localStorage.getItem('token') !== accessToken) {
          return localStorage.getItem('token')
        }
        return null
      })
      .finally(() => {
        setTimeout(() => {
          if (refreshing === pending) { refreshing = null; refreshingFor = null }
        }, 100)
      })
    refreshing = pending
    refreshingFor = refreshToken
  }
  return refreshing
}

function clearAuthentication(expectedSession: string | null) {
  if (expectedSession !== sessionIdentity()) return
  clearHotContentCache()
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

instance.interceptors.request.use(async (config: InternalAxiosRequestConfig & SessionRequest) => {
  if (!('_authSession' in config)) config._authSession = sessionIdentity()
  assertCurrentSession(config)
  let token = localStorage.getItem('token')
  const path = (config.url || '').split('?')[0]
  const signingIn = /^\/auth\/(login|register)(\/|$)/.test(path)
  if (token && !signingIn && !(config as AxiosRequestConfig & { _authRetried?: boolean })._authRetried && isExpired(token)) {
    token = await tryRefresh()
    assertCurrentSession(config)
    if (!token) {
      clearAuthentication(config._authSession ?? null)
      // The anonymous fallback is an intentional new transport session.
      config._authSession = sessionIdentity()
      const publicRead = isPublicRead(config)
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
    // Public catalog responses may finish after login; cache-generation guards prevent stale fills.
    if (!(resp.config.method === 'get' && isPublicHotContentRoute(resp.config.url || ''))) assertCurrentSession(resp.config as SessionRequest)
    const body = resp.data
    const envelope = body && typeof body === 'object' && 'code' in body
    if (envelope && body.code !== 0) {
      ElMessage.error(body.message || '请求失败')
      return Promise.reject(body)
    }
    if (['post', 'put', 'patch', 'delete'].includes(resp.config.method || '')
      && !/^\/auth(?:\/|$)/.test(resp.config.url || '')) {
      clearHotContentCache()
    }
    resp.data = resolveProductImages(envelope ? body.data : body)
    return resp
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
      const config = error.config as (AxiosRequestConfig & SessionRequest) | undefined
      if (config) assertCurrentSession(config)
      if (config && !config._authRetried) {
        config._authRetried = true
        const token = await tryRefresh()
        assertCurrentSession(config)
        if (token) return instance(config)
      }
      clearAuthentication(config?._authSession ?? sessionIdentity())
      return Promise.reject(body)
    }
    // silent: true 时静默失败（轮询等高频请求，不打扰用户）
    if (!(error.config as { silent?: boolean } | undefined)?.silent) {
      ElMessage.error(body?.message || '网络错误，请稍后重试')
    }
    return Promise.reject(body || error)
  },
)

export interface GetRequestConfig extends AxiosRequestConfig {
  /** Always read from the network without reading or populating the local cache. */
  cache?: false
}

/** Keep Axios responses intact internally; expose only business data at this facade. */
export async function get<T>(url: string, config?: GetRequestConfig): Promise<T> {
  const { cache, ...networkConfig } = config || {}
  const load = async () => (await instance.get<T>(url, networkConfig)).data
  // Preserve custom headers, cancellation, serialization and other axios semantics.
  if (cache === false || Object.keys(networkConfig).some(key => key !== 'params')) return load()
  const token = localStorage.getItem('token')
  // A cached response must not skip the existing expired-session refresh path.
  if (token && isExpired(token)) return load()
  return readHotContent(url, config?.params, load)
}

export async function post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return (await instance.post<T>(url, data, config)).data
}

export async function put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return (await instance.put<T>(url, data, config)).data
}

export async function del<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return (await instance.delete<T>(url, config)).data
}

export async function upload<T>(url: string, formData: FormData): Promise<T> {
  return (await instance.post<T>(url, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })).data
}

export default instance
