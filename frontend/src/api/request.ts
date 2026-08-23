/**
 * axios 封装：token 注入 + 401 自动刷新重放 + 统一错误提示
 * （token 直接读写 localStorage，避免与 store 循环依赖）
 */
import axios from 'axios'
import type { AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

const instance = axios.create({ baseURL: '/api/v1', timeout: 30000 })

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
      .post('/api/v1/auth/refresh', { refreshToken })
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

instance.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

instance.interceptors.response.use(
  (resp) => {
    const body = resp.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 0) {
        return body.data
      }
      ElMessage.error(body.message || '请求失败')
      return Promise.reject(body)
    }
    return body
  },
  async (error) => {
    const status = error.response?.status
    const body = error.response?.data
    const code = body?.code
    if (status === 401 || code === 1003) {
      const token = await tryRefresh()
      if (token) {
        return instance(error.config)
      }
      localStorage.removeItem('token')
      localStorage.removeItem('refreshToken')
      localStorage.removeItem('user')
      unauthorizedHandler()
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
