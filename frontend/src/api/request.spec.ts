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


describe('transport response and account isolation', () => {
  it('preserves a private evidence Blob instead of recursively converting it to an empty record', async () => {
    const { default: instance, get } = await import('./request')
    const proof = new Blob(['PNG-test'], { type: 'image/png' })
    instance.defaults.adapter = async config => ({status:200,statusText:'OK',data:proof,config,headers:{}})
    expect(await get('/after-sales/1/evidence/test.png', { responseType:'blob', cache:false })).toBe(proof)
  })
  it('preserves ArrayBuffer response identity', async () => {
    const { default: instance, get } = await import('./request')
    const bytes = new Uint8Array([1,2,3]).buffer
    instance.defaults.adapter = async config => ({status:200,statusText:'OK',data:bytes,config,headers:{}})
    expect(await get('/download', { responseType:'arraybuffer', cache:false })).toBe(bytes)
  })
  it('keeps the Axios response contract internally while the facade returns business data', async () => {
    const { default: instance, get } = await import('./request')
    instance.defaults.adapter = async config => ({status:200,statusText:'OK',data:{code:0,data:{id:1}},config,headers:{}})
    const raw = await instance.get('/raw')
    expect(raw.status).toBe(200); expect(raw.data).toEqual({id:1})
    await expect(get('/raw')).resolves.toEqual({id:1})
  })
  it.each(['post','put','del','upload'] as const)('preserves the unwrapped %s facade contract', async method => {
    const request = await import('./request')
    request.default.defaults.adapter = async config => ({status:200,statusText:'OK',data:{code:0,data:{id:2}},config,headers:{}})
    const result = method==='upload' ? request.upload('/write',new FormData()) : request[method]('/write')
    await expect(result).resolves.toEqual({id:2})
  })
  it('does not overwrite a newer login when an older refresh finishes late', async () => {
    const axios = (await import('axios')).default
    const { default: instance, get } = await import('./request')
    localStorage.setItem('token',jwt(Math.floor(Date.now()/1000)-1)); localStorage.setItem('refreshToken','old-refresh')
    let resolveRefresh!: (value:any)=>void, signalRefresh!:()=>void
    const started = new Promise<void>(resolve=>signalRefresh=resolve)
    vi.spyOn(axios,'post').mockImplementation(()=>{signalRefresh();return new Promise(resolve=>resolveRefresh=resolve)})
    const adapter=vi.fn(async config=>({status:200,statusText:'OK',data:{code:0,data:{}},config,headers:{}})); instance.defaults.adapter=adapter
    const pending=get('/addresses'); const rejected=expect(pending).rejects.toMatchObject({name:'CanceledError'})
    await started
    localStorage.setItem('token','new-account-access');localStorage.setItem('refreshToken','new-account-refresh')
    resolveRefresh({data:{code:0,data:{accessToken:'old-account-renewed'}}})
    await rejected
    expect(localStorage.getItem('token')).toBe('new-account-access');expect(adapter).not.toHaveBeenCalled()
  })
  it('does not refresh or replay an old-account mutation under a newly signed-in account', async () => {
    const axios = (await import('axios')).default
    const { default: instance, post, setUnauthorizedHandler } = await import('./request')
    localStorage.setItem('token','old-access');localStorage.setItem('refreshToken','old-refresh')
    let release!:()=>void, signal!:()=>void
    const started=new Promise<void>(resolve=>signal=resolve), gate=new Promise<void>(resolve=>release=resolve)
    const refresh=vi.spyOn(axios,'post').mockResolvedValue({data:{code:0,data:{accessToken:'unexpected-renewal'}}})
    const unauthorized=vi.fn();setUnauthorizedHandler(unauthorized)
    const adapter=vi.fn(async config=>{signal();await gate;throw new axios.AxiosError('Rejected','ERR_BAD_RESPONSE',config,undefined,{status:401,statusText:'Unauthorized',data:{code:1003},config,headers:{}})})
    instance.defaults.adapter=adapter
    const pending=post('/addresses',{receiverName:'old-account draft'});const rejected=expect(pending).rejects.toMatchObject({name:'CanceledError'})
    await started
    localStorage.setItem('token','new-access');localStorage.setItem('refreshToken','new-refresh');release()
    await rejected
    expect(adapter).toHaveBeenCalledTimes(1);expect(refresh).not.toHaveBeenCalled();expect(unauthorized).not.toHaveBeenCalled();expect(localStorage.getItem('token')).toBe('new-access')
  })
  it('discards a successful private response from an account that has since logged out', async () => {
    const { default: instance, get } = await import('./request')
    let finish!:(value:any)=>void, signal!:()=>void
    const started=new Promise<void>(resolve=>signal=resolve)
    instance.defaults.adapter=config=>{signal();return new Promise(resolve=>finish=value=>resolve({status:200,statusText:'OK',data:{code:0,data:value},config,headers:{}}))}
    const pending=get('/orders/my',{cache:false});const rejected=expect(pending).rejects.toMatchObject({name:'CanceledError'})
    await started;localStorage.clear();finish({records:[{privateData:'old account'}]});await rejected
  })
})


it('keeps a peer tab access-token refresh in the same refresh-token session without logging it out', async () => {
  const axios=(await import('axios')).default
  const {default:instance,get,setUnauthorizedHandler}=await import('./request')
  localStorage.setItem('token',jwt(Math.floor(Date.now()/1000)-1));localStorage.setItem('refreshToken','shared-refresh')
  let finish!:(v:any)=>void,signal!:()=>void
  const started=new Promise<void>(resolve=>signal=resolve)
  vi.spyOn(axios,'post').mockImplementation(()=>{signal();return new Promise(resolve=>finish=resolve)})
  const unauthorized=vi.fn();setUnauthorizedHandler(unauthorized)
  const authorizations:unknown[]=[]
  instance.defaults.adapter=async config=>{authorizations.push(config.headers.Authorization);return{status:200,statusText:'OK',data:{code:0,data:{items:[]}},config,headers:{}}}
  const request=get('/cart');await started
  localStorage.setItem('token','peer-refreshed-access')
  finish({data:{code:0,data:{accessToken:'older-refresh-result'}}})
  await expect(request).resolves.toEqual({items:[]})
  expect(authorizations).toEqual(['Bearer peer-refreshed-access']);expect(localStorage.getItem('token')).toBe('peer-refreshed-access');expect(unauthorized).not.toHaveBeenCalled()
})


it('does not copy a refresh credential into serializable request metadata',async()=>{
  const {default:instance,get}=await import('./request')
  localStorage.setItem('token','access-token');localStorage.setItem('refreshToken','private-refresh-token')
  instance.defaults.adapter=async config=>{
    const marker=(config as typeof config & {_authSession?: string})._authSession
    expect(marker).not.toBe('private-refresh-token');expect(marker).toMatch(/^session:\d+$/)
    return {status:200,statusText:'OK',data:{code:0,data:{}},config,headers:{}}
  }
  await get('/orders/my',{cache:false})
})


it('does not treat public coupon endpoints with user-specific received state as shared catalog data',async()=>{
  const {default:instance,get}=await import('./request')
  let finish!:(value:any)=>void,signal!:()=>void
  const started=new Promise<void>(resolve=>signal=resolve)
  instance.defaults.adapter=config=>{signal();return new Promise(resolve=>finish=value=>resolve({status:200,statusText:'OK',data:{code:0,data:value},config,headers:{}}))}
  const pending=get('/promotions/coupons',{cache:false});const rejected=expect(pending).rejects.toMatchObject({name:'CanceledError'})
  await started;localStorage.setItem('token','new-user-access');localStorage.setItem('refreshToken','new-user-refresh');finish([{id:1,received:true}]);await rejected
})


it('does not erase a same-session peer refresh when this tab refresh fails',async()=>{
  const axios=(await import('axios')).default
  const {default:instance,get,setUnauthorizedHandler}=await import('./request')
  localStorage.setItem('token',jwt(Math.floor(Date.now()/1000)-1));localStorage.setItem('refreshToken','shared-session')
  let fail!:(error:Error)=>void,signal!:()=>void
  const started=new Promise<void>(resolve=>signal=resolve)
  vi.spyOn(axios,'post').mockImplementation(()=>{signal();return new Promise((_,reject)=>fail=reject)})
  const unauthorized=vi.fn();setUnauthorizedHandler(unauthorized)
  instance.defaults.adapter=async config=>({status:200,statusText:'OK',data:{code:0,data:{owner:'same user'}},config,headers:{}})
  const pending=get('/cart');await started;localStorage.setItem('token','peer-current-access');fail(new Error('refresh network outage'))
  await expect(pending).resolves.toEqual({owner:'same user'});expect(localStorage.getItem('token')).toBe('peer-current-access');expect(unauthorized).not.toHaveBeenCalled()
})
