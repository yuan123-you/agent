import { describe, expect, it } from 'vitest'
import type { AdminDashboardVO } from '@/types/api'
import dashboardSource from './DashboardView.vue?raw'
import { formatMoney, normalizeDashboard, orderStatusText } from './dashboard'

describe('admin dashboard helpers', () => {
  it('formats missing monetary amounts as zero yuan', () => {
    expect(formatMoney(undefined)).toBe('¥0.00')
  })

  it('localizes paid order status', () => {
    expect(orderStatusText('PAID')).toBe('已支付')
  })

  it('normalizes a partial response to zero-safe empty dashboard data', () => {
    const result = normalizeDashboard({ summary: { userCount: 4 } } as Partial<AdminDashboardVO>)

    expect(result.summary).toEqual({
      userCount: 4, merchantCount: 0, onSaleProductCount: 0,
      todayOrderCount: 0, todayGmv: 0, todayConversationCount: 0,
    })
    expect(result.operations.waitingHumanConversationCount).toBe(0)
    expect(result.aiQuality).toEqual({ replySuccessRate: 0, toolCallRatio: 0, avgLatencyMs: 0, totalTokens: 0 })
    expect([result.orderTrend, result.orderStatusDistribution, result.topQuestions, result.toolCalls]).toEqual([[], [], [], []])
  })

  it('moves the trend bar onto its own row on narrow screens', () => {
    expect(dashboardSource).toMatch(/@media \(max-width:760px\)[\s\S]*?\.bar-track\s*\{[^}]*grid-column:\s*1\s*\/\s*-1/)
  })
})
