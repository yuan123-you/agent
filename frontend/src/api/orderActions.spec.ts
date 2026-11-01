import { describe, expect, it, vi } from 'vitest'
const transport = vi.hoisted(() => ({ post: vi.fn(), get: vi.fn() }))
vi.mock('./request', () => ({ ...transport, put: vi.fn(), del: vi.fn(), upload: vi.fn() }))
import * as api from './index'

describe('order workflow recovery HTTP boundary', () => {
  it('posts recovery with only the action identifier in the path and no decision body', async () => {
    transport.post.mockResolvedValue({ workflow: { workflowStatus: 'WAITING_APPROVAL' } })
    await api.apiRecoverOrderAction('act_123')
    expect(transport.post).toHaveBeenCalledExactlyOnceWith('/order-actions/act_123/recover')
  })
})
