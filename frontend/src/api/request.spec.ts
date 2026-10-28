import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
vi.mock('element-plus', () => ({ ElMessage: { error: vi.fn() } }))
beforeEach(() => { vi.resetModules(); localStorage.setItem('token', 'expired'); localStorage.setItem('refreshToken', 'refresh') })
afterEach(() => { vi.restoreAllMocks(); localStorage.clear() })
describe('authentication replay boundary', () => {
  it('refreshes and replays at most once if the replacement token is also rejected', async () => {
    const axios = (await import('axios')).default
    const { default: instance, get, setUnauthorizedHandler } = await import('./request')
    const unauthorized = vi.fn(); setUnauthorizedHandler(unauthorized)
    const refresh = vi.spyOn(axios, 'post').mockResolvedValue({ data: { code: 0, data: { accessToken: 'still-invalid' } } })
    let calls = 0
    instance.defaults.adapter = async config => {
      calls++
      // Break the old infinite replay loop deterministically rather than hanging the test.
      const status = calls > 3 ? 503 : 401
      throw new axios.AxiosError('Rejected', 'ERR_BAD_RESPONSE', config, undefined, { status, statusText: 'Rejected', data: { code: status === 401 ? 1003 : 5002 }, config, headers: {} })
    }
    await expect(get('/orders/my')).rejects.toBeDefined()
    expect(calls).toBe(2)
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(unauthorized).toHaveBeenCalledTimes(1)
    expect(localStorage.getItem('token')).toBeNull()
  })
})

const jwt = (expiresAt: number) => `header.${btoa(JSON.stringify({ exp: expiresAt }))}.signature`

describe('expired session before requests', () => {
  it('refreshes an expired access token before the first cart request reaches the server', async () => {
    const axios = (await import('axios')).default
    const { default: instance, get } = await import('./request')
    localStorage.setItem('token', jwt(Math.floor(Date.now() / 1000) - 60))
    const refresh = vi.spyOn(axios, 'post').mockResolvedValue({ data: { code: 0, data: { accessToken: 'renewed' } } })
    const headers: unknown[] = []
    instance.defaults.adapter = async config => {
      headers.push(config.headers.Authorization)
      return { status: 200, statusText: 'OK', data: { code: 0, data: { items: [] } }, config, headers: {} }
    }
    await expect(get('/cart')).resolves.toEqual({ items: [] })
    expect(headers).toEqual(['Bearer renewed'])
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(localStorage.getItem('token')).toBe('renewed')
  })

  it('shares one refresh across concurrent requests with an expired token', async () => {
    const axios = (await import('axios')).default
    const { default: instance, get } = await import('./request')
    localStorage.setItem('token', jwt(Math.floor(Date.now() / 1000) - 60))
    const refresh = vi.spyOn(axios, 'post').mockResolvedValue({ data: { code: 0, data: { accessToken: 'renewed' } } })
    const headers: unknown[] = []
    instance.defaults.adapter = async config => {
      headers.push(config.headers.Authorization)
      return { status: 200, statusText: 'OK', data: { code: 0, data: [] }, config, headers: {} }
    }
    await Promise.all([get('/cart'), get('/orders/my')])
    expect(headers).toEqual(['Bearer renewed', 'Bearer renewed'])
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('clears an expired session without issuing an unauthorized cart request when no refresh token remains', async () => {
    const { default: instance, get, setUnauthorizedHandler } = await import('./request')
    localStorage.setItem('token', jwt(Math.floor(Date.now() / 1000) - 60))
    localStorage.setItem('user', JSON.stringify({ role: 'CUSTOMER' }))
    localStorage.removeItem('refreshToken')
    const unauthorized = vi.fn()
    setUnauthorizedHandler(unauthorized)
    const adapter = vi.fn()
    instance.defaults.adapter = adapter
    await expect(get('/cart')).rejects.toBeDefined()
    expect(adapter).not.toHaveBeenCalled()
    expect(localStorage.getItem('token')).toBeNull()
    expect(localStorage.getItem('user')).toBeNull()
    expect(unauthorized).toHaveBeenCalledTimes(1)
  })

  it('still loads public products anonymously after the session expires', async () => {
    const { default: instance, get } = await import('./request')
    localStorage.setItem('token', jwt(Math.floor(Date.now() / 1000) - 60))
    localStorage.removeItem('refreshToken')
    const headers: unknown[] = []
    instance.defaults.adapter = async config => {
      headers.push(config.headers.Authorization)
      return { status: 200, statusText: 'OK', data: { code: 0, data: { records: [] } }, config, headers: {} }
    }
    await expect(get('/products')).resolves.toEqual({ records: [] })
    expect(headers).toEqual([undefined])
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('does not refresh a valid token before normal requests', async () => {
    const axios = (await import('axios')).default
    const { default: instance, get } = await import('./request')
    const token = jwt(Math.floor(Date.now() / 1000) + 3600)
    localStorage.setItem('token', token)
    const refresh = vi.spyOn(axios, 'post')
    instance.defaults.adapter = async config => ({ status: 200, statusText: 'OK', data: { code: 0, data: true }, config, headers: {} })
    await expect(get('/cart')).resolves.toBe(true)
    expect(refresh).not.toHaveBeenCalled()
  })
})

describe('expired session edge cases', () => {
  it('does not refresh the old session or attach its token when signing in again', async () => {
    const axios = (await import('axios')).default
    const { default: instance, post } = await import('./request')
    localStorage.setItem('token', jwt(Math.floor(Date.now() / 1000) - 60))
    const refresh = vi.spyOn(axios, 'post')
    const headers: unknown[] = []
    instance.defaults.adapter = async config => {
      headers.push(config.headers.Authorization)
      return { status: 200, statusText: 'OK', data: { code: 0, data: { accessToken: 'new-session' } }, config, headers: {} }
    }
    await expect(post('/auth/login', { username: 'buyer', password: 'test-only' })).resolves.toEqual({ accessToken: 'new-session' })
    expect(refresh).not.toHaveBeenCalled()
    expect(headers).toEqual([undefined])
  })

  it('stops the protected request if refreshing the expired session fails', async () => {
    const axios = (await import('axios')).default
    const { default: instance, get, setUnauthorizedHandler } = await import('./request')
    localStorage.setItem('token', jwt(Math.floor(Date.now() / 1000) - 60))
    const refresh = vi.spyOn(axios, 'post').mockRejectedValue(new Error('refresh expired'))
    const unauthorized = vi.fn()
    setUnauthorizedHandler(unauthorized)
    const adapter = vi.fn()
    instance.defaults.adapter = adapter
    await expect(get('/cart')).rejects.toBeDefined()
    expect(adapter).not.toHaveBeenCalled()
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(unauthorized).toHaveBeenCalledTimes(1)
    expect(localStorage.getItem('token')).toBeNull()
    expect(localStorage.getItem('refreshToken')).toBeNull()
  })
})

describe('refresh availability boundaries', () => {
  it('keeps using a still-valid access token rather than logging out during a refresh outage', async () => {
    const axios = (await import('axios')).default
    const { default: instance, get, setUnauthorizedHandler } = await import('./request')
    const token = jwt(Math.floor(Date.now() / 1000) + 20)
    localStorage.setItem('token', token)
    const refresh = vi.spyOn(axios, 'post').mockRejectedValue(new Error('503 temporarily unavailable'))
    const unauthorized = vi.fn()
    setUnauthorizedHandler(unauthorized)
    const headers: unknown[] = []
    instance.defaults.adapter = async config => {
      headers.push(config.headers.Authorization)
      return { status: 200, statusText: 'OK', data: { code: 0, data: { items: [] } }, config, headers: {} }
    }
    await expect(get('/cart')).resolves.toEqual({ items: [] })
    expect(headers).toEqual([`Bearer ${token}`])
    expect(localStorage.getItem('token')).toBe(token)
    expect(unauthorized).not.toHaveBeenCalled()
    expect(refresh).not.toHaveBeenCalled()
  })

  it('uses a bounded refresh timeout and falls back to anonymous product browsing on timeout', async () => {
    const axios = (await import('axios')).default
    const { default: instance, get } = await import('./request')
    localStorage.setItem('token', jwt(Math.floor(Date.now() / 1000) - 60))
    const refresh = vi.spyOn(axios, 'post').mockRejectedValue(new axios.AxiosError('timeout', 'ECONNABORTED'))
    const headers: unknown[] = []
    instance.defaults.adapter = async config => {
      headers.push(config.headers.Authorization)
      return { status: 200, statusText: 'OK', data: { code: 0, data: { records: [] } }, config, headers: {} }
    }
    await expect(get('/products')).resolves.toEqual({ records: [] })
    expect(headers).toEqual([undefined])
    expect(refresh).toHaveBeenCalledWith(expect.stringContaining('/auth/refresh'), { refreshToken: 'refresh' }, { timeout: 10000 })
  })
})


describe('catalog photograph deployment paths', () => {
  afterEach(() => vi.unstubAllEnvs())
  it('resolves product, cart, SKU and order photographs under the deployed base without changing source URLs', async () => {
    vi.stubEnv('BASE_URL', '/aimall/')
    localStorage.clear()
    const { default: instance, get } = await import('./request')
    const image = '/api/v1/product-images/catalog/abc.webp'
    instance.defaults.adapter = async config => ({ status: 200, statusText: 'OK', config, headers: {},
      data: { code: 0, data: { records: [{ imageUrl: image, originalImageUrl: 'https://cdn.example/photo.jpg',
        items: [{ productImage: image, pic: image }], description: image }] } } })
    const data = await get<{ records: { imageUrl: string; originalImageUrl: string; description: string; items: { productImage: string; pic: string }[] }[] }>('/products')
    expect(data.records[0].imageUrl).toBe('/aimall' + image)
    expect(data.records[0].items[0]).toEqual({ productImage: '/aimall' + image, pic: '/aimall' + image })
    expect(data.records[0].originalImageUrl).toBe('https://cdn.example/photo.jpg')
    expect(data.records[0].description).toBe(image)
  })
  it('leaves root deployments, external URLs and already prefixed images unchanged', async () => {
    vi.stubEnv('BASE_URL', '/')
    localStorage.clear()
    const { default: instance, get } = await import('./request')
    const rows = [{ imageUrl: '/api/v1/product-images/id.jpg' }, { imageUrl: 'https://cdn.example/p.jpg' },
      { imageUrl: '/aimall/api/v1/product-images/p.png' }, { imageUrl: null }]
    instance.defaults.adapter = async config => ({ status: 200, statusText: 'OK', config, headers: {}, data: { code: 0, data: rows } })
    await expect(get('/products')).resolves.toEqual(rows)
  })
})
