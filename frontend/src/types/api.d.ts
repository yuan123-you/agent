/** 后端契约类型定义（与《API接口设计文档》对齐） */

export interface UserInfo {
  userId: number
  username: string
  nickname: string
  role: 'ADMIN' | 'AGENT' | 'CUSTOMER'
  phone?: string
  email?: string
}

export interface LoginResp {
  accessToken: string
  refreshToken?: string
  expiresIn?: number
  user?: UserInfo
}

export interface PageResult<T> {
  records: T[]
  total: number
  page: number
  size: number
}

export interface ProductVO {
  id: number
  name: string
  category: string
  brand: string
  price: number
  stock: number
  imageUrl?: string
  description?: string
  sellingPoints?: string
  specs?: string
  status?: string
  createdAt?: string
}

export interface OrderItemVO {
  productId: number
  productName: string
  productImage?: string
  price: number
  quantity: number
  subtotal: number
}

export interface OrderVO {
  orderId: number
  orderNo: string
  status: string
  statusText?: string
  totalAmount: number
  source?: string
  logisticsNo?: string
  receiverName?: string
  receiverPhone?: string
  receiverAddress?: string
  createdAt?: string
  paidAt?: string
  shippedAt?: string
  deliveredAt?: string
  items: OrderItemVO[]
  userNickname?: string
}

export interface ConversationVO {
  conversationId: number
  convNo?: string
  title?: string
  status: 'ACTIVE' | 'PENDING_HUMAN' | 'SERVICING' | 'CLOSED'
  summary?: string
  satisfaction?: number
  messageCount?: number
  createdAt?: string
  updatedAt?: string
  userNickname?: string
}

/** 工具调用卡片（流式与历史共用） */
export interface ToolCard {
  callId: string
  tool: string
  args?: Record<string, unknown>
  result?: { preview?: string }
  elapsedMs?: number
  status: 'running' | 'done'
}

export interface OrderAction {
  type: 'ORDER_CREATE'
  actionId: string
  productName: string
  quantity: number
  unitPrice: number
  amount: number
  receiverName: string
  receiverPhone: string
  receiverAddress: string
  expiresAt: string
  status?: 'PENDING' | 'CONFIRMING' | 'CONFIRMED' | 'CANCELLED' | 'EXPIRED' | 'FAILED'
  orderId?: number
  orderNo?: string
  orderStatus?: string
}

export interface ChatMessage {
  messageId?: number
  id?: number
  role: 'USER' | 'AI' | 'AGENT' | 'SYSTEM'
  content: string
  toolCalls?: ToolCard[]
  actions?: OrderAction[]
  status?: string
  createdAt?: string
  latencyMs?: number
}

export interface KbDocVO {
  docId: number
  productId?: number
  title: string
  docType: string
  fileFormat: string
  status: 'PENDING' | 'PROCESSING' | 'ACTIVE' | 'DISABLED' | 'FAILED'
  chunkCount: number
  failReason?: string
  version: number
  createdAt?: string
}

export interface StatsVO {
  todayConversationCount: number
  todayAiMessageCount: number
  topQuestions: { keyword: string; count: number }[]
  aiToolCalls: Record<string, number>
}

export interface AddressVO {
  addressId: number
  receiverName: string
  receiverPhone: string
  receiverAddress: string
  isDefault: boolean
}

export interface WorkbenchSla {
  pendingCount: number
  servicingCount: number
  todayNewCount: number
  todayHandledCount: number
  avgFirstResponseSeconds: number
}


