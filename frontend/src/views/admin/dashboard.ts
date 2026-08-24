import type { AdminDashboardVO } from '@/types/api'

export interface NormalizedDashboard {
  summary: Required<AdminDashboardVO['summary']>
  orderTrend: AdminDashboardVO['orderTrend']
  orderStatusDistribution: AdminDashboardVO['orderStatusDistribution']
  operations: Required<AdminDashboardVO['operations']>
  aiQuality: Required<AdminDashboardVO['aiQuality']>
  topQuestions: AdminDashboardVO['topQuestions']
  toolCalls: AdminDashboardVO['toolCalls']
}

const numberOrZero = (value: unknown): number => typeof value === 'number' && Number.isFinite(value) ? value : 0

export function formatMoney(value: unknown): string {
  return `¥${numberOrZero(value).toFixed(2)}`
}

export function formatPercent(value: unknown): string {
  return `${numberOrZero(value).toFixed(2)}%`
}

export function orderStatusText(status: string): string {
  return {
    PENDING_PAYMENT: '待支付', PAID: '已支付', SHIPPED: '已发货',
    DELIVERED: '已送达', CANCELLED: '已取消', COMPLETED: '已完成',
  }[status] || status || '未知状态'
}

export function normalizeDashboard(value: Partial<AdminDashboardVO> = {}): NormalizedDashboard {
  const summary: Partial<AdminDashboardVO['summary']> = value.summary ?? {}
  const operations: Partial<AdminDashboardVO['operations']> = value.operations ?? {}
  const aiQuality: Partial<AdminDashboardVO['aiQuality']> = value.aiQuality ?? {}
  return {
    summary: {
      userCount: numberOrZero(summary.userCount), merchantCount: numberOrZero(summary.merchantCount),
      onSaleProductCount: numberOrZero(summary.onSaleProductCount), todayOrderCount: numberOrZero(summary.todayOrderCount),
      todayGmv: numberOrZero(summary.todayGmv), todayConversationCount: numberOrZero(summary.todayConversationCount),
    },
    orderTrend: Array.isArray(value.orderTrend) ? value.orderTrend.map(item => ({ date: item?.date || '', orderCount: numberOrZero(item?.orderCount), gmv: numberOrZero(item?.gmv) })) : [],
    orderStatusDistribution: Array.isArray(value.orderStatusDistribution) ? value.orderStatusDistribution.map(item => ({ status: item?.status || '', count: numberOrZero(item?.count) })) : [],
    operations: { waitingHumanConversationCount: numberOrZero(operations.waitingHumanConversationCount) },
    aiQuality: {
      replySuccessRate: numberOrZero(aiQuality.replySuccessRate), toolCallRatio: numberOrZero(aiQuality.toolCallRatio),
      avgLatencyMs: numberOrZero(aiQuality.avgLatencyMs), totalTokens: numberOrZero(aiQuality.totalTokens),
    },
    topQuestions: Array.isArray(value.topQuestions) ? value.topQuestions.map(item => ({ name: item?.name || '', count: numberOrZero(item?.count) })) : [],
    toolCalls: Array.isArray(value.toolCalls) ? value.toolCalls.map(item => ({ name: item?.name || '', count: numberOrZero(item?.count) })) : [],
  }
}

export function toolText(tool: string): string {
  return {
    product_search: '检索商品', product_detail: '商品详情', order_query: '查询订单',
    order_create: '创建订单', kb_search: '检索知识库', escalate_to_human: '转人工',
  }[tool] || tool || '未知工具'
}
