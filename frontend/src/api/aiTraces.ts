import { get } from './request'
import type { PageResult } from '@/types/api'
import type { AiTraceSummary, AiTraceDetail, AiTraceFilters } from '@/types/aiTrace'

// Sensitive operator data must never use the storefront hot-content cache.
export const apiAiTraces = (params: AiTraceFilters) =>
  get<PageResult<AiTraceSummary>>('/admin/ai-traces', { params, cache: false })
export const apiAiTrace = (traceId: string) =>
  get<AiTraceDetail>(`/admin/ai-traces/${encodeURIComponent(traceId)}`, { cache: false })

export const apiAiBenchmark = () =>
  get<Record<string, any>>('/admin/ai-traces/benchmark', { cache: false })
