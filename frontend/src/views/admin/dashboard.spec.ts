import { describe, expect, it } from 'vitest'
import type { AdminDashboardVO } from '@/types/api'
import { formatMoney, normalizeDashboard, orderStatusText } from './dashboard'

describe('admin dashboard helpers', () => {
  it('formats missing monetary amounts as zero yuan', () => {
    expect(formatMoney(undefined)).toBe('¥0.00')
  })

  it('localizes paid order status', () => {
    expect(orderStatusText('PAID')).toBe('已支付')
  })

  it('normalizes a partial response to safe empty collections', () => {
    expect(normalizeDashboard({ summary: {} } as Partial<AdminDashboardVO>).orderTrend).toEqual([])
  })
})
