export interface TraceStage {
  id: string
  parentId?: string | null
  name: string
  kind: string
  status: string
  startMs: number
  durationMs?: number
  model?: string
  usage?: Record<string, number>
  input?: unknown
  output?: unknown
  error?: string
}
export interface AiTraceSummary {
  traceId: string
  conversationId: number
  userId: number
  messageId?: number
  status: string
  inputPreview: string
  modelCalls: number
  totalTokens: number | null
  stageCount: number
  durationMs: number | null
  createdAt: string
  finishedAt?: string
}
export interface AiTraceDetail extends AiTraceSummary {
  stages: TraceStage[]
  omittedStages: number
  error?: string
}
export interface AiTraceFilters { page: number; size: number; status?: string; conversationId?: number; query?: string }
