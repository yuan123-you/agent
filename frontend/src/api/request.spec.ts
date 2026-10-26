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
