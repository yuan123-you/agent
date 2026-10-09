import { API_BASE } from '@/api/base'
/** 全量 API 函数（按模块分组） */
import { del, get, post, put, upload } from './request'
import type {
  AddressVO, AdminDashboardVO, ConversationVO, CustomerRegistration, KbDocVO, LoginResp, MerchantRegistration, OrderAction, OrderApprovalForm, OrderVO, PageResult, ProductVO, StatsVO, UserInfo, WorkbenchSla,
} from '@/types/api'

// ---------- 认证 ----------
export const apiLogin = (data: { username: string; password: string }) =>
  post<LoginResp>('/auth/login', data)
export const apiRegister = (data: CustomerRegistration) =>
  post<LoginResp>('/auth/register', data)
export const apiRegisterCustomer = (data: CustomerRegistration) =>
  post<LoginResp>('/auth/register/customer', data)
export const apiRegisterMerchant = (data: MerchantRegistration) =>
  post<LoginResp>('/auth/register/merchant', data)
export const apiLogout = () => post<void>('/auth/logout')
export const apiMe = () => get<UserInfo>('/auth/me')

// ---------- 商品 ----------
export const apiProducts = (params: Record<string, unknown>) =>
  get<PageResult<ProductVO>>('/products', { params })
export const apiProductDetail = (id: number) => get<ProductVO>(`/products/${id}`)
export const apiCategories = () => get<string[]>('/products/categories')

// ---------- 购物车 ----------
export const apiCartAdd = (productId: number, quantity: number) =>
  post<void>('/cart/items', { productId, quantity })
export interface CartRow {
  cartItemId: number; productId: number; name: string; imageUrl: string
  price: number; quantity: number; checked: number; stock: number; subtotal: number
}
export const apiCartList = () =>
  get<{ items: CartRow[]; totalAmount: number; checkedCount: number }>('/cart')
export const apiCartUpdate = (id: number, body: { quantity?: number; checked?: boolean }) =>
  put<void>(`/cart/items/${id}`, body)
export const apiCartCheckAll = (checked: boolean) => put<void>('/cart/check-all', { checked })
export const apiCartRemove = (id: number) => del<void>(`/cart/items/${id}`)
export interface CheckoutDeliveryPayload {
  addressId?: number
  receiverName?: string
  receiverPhone?: string
  receiverAddress?: string
}
export const apiCartCheckout = (body: CheckoutDeliveryPayload) =>
  post<{ orderId: number; orderNo: string; totalAmount: number }>('/cart/checkout', body)

// ---------- 收藏 / 浏览历史 ----------
export const apiFavoriteToggle = (productId: number) =>
  post<{ favorited: boolean }>(`/favorites/${productId}/toggle`)
export const apiFavoriteStatus = (productId: number) =>
  get<{ favorited: boolean }>(`/favorites/${productId}/status`)
export const apiFavorites = (params: Record<string, unknown>) =>
  get<PageResult<ProductVO & { time: string }>>('/favorites', { params })
export const apiHistoryRecord = (productId: number) => post<void>(`/history/${productId}`)
export const apiHistory = (params: Record<string, unknown>) =>
  get<PageResult<ProductVO & { time: string }>>('/history', { params })
export const apiHistoryClear = () => del<void>('/history')

// ---------- 商品评论 ----------
export interface ReviewVO {
  reviewId: number; nickname: string; rating: number; content: string
  specInfo?: string; merchantReply?: string; createdAt: string
}
export const apiReviews = (productId: number, params: Record<string, unknown>) =>
  get<PageResult<ReviewVO> & { avgRating: number; ratingDistribution: Record<string, number> }>(
    `/products/${productId}/reviews`, { params })
export const apiReviewCreate = (productId: number, body: { rating: number; content: string; specInfo?: string }) =>
  post<void>(`/products/${productId}/reviews`, body)

// ---------- 商家端 ----------
export const apiMerchantProfile = () =>
  get<{ merchantId: number; shopName: string; description?: string; address?: string; onSaleCount: number; totalProducts: number }>('/merchant/profile')
export const apiMerchantProducts = (params: Record<string, unknown>) =>
  get<PageResult<ProductVO>>('/merchant/products', { params })
export const apiMerchantProductImage = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return upload<{ url: string }>('/merchant/product-images', form)
}
export const apiMerchantCreate = (data: Record<string, unknown>) =>
  post<number>('/merchant/products', data)
export const apiMerchantUpdate = (id: number, data: Record<string, unknown>) =>
  put<void>(`/merchant/products/${id}`, data)
export const apiMerchantStatus = (id: number, status: string) =>
  post<void>(`/merchant/products/${id}/status`, { status })
export const apiMerchantDelete = (id: number) => del<void>(`/merchant/products/${id}`)
export const apiMerchantReviews = (params: Record<string, unknown>) =>
  get<PageResult<{ id: number; productId: number; rating: number; content: string; specInfo?: string; merchantReply?: string; createdAt: string }>>('/merchant/reviews', { params })
export const apiMerchantReply = (id: number, content: string) =>
  post<void>(`/merchant/reviews/${id}/reply`, { content })
export const apiAdminProducts = (params: Record<string, unknown>) =>
  get<PageResult<ProductVO>>('/admin/products', { params })
export const apiAdminProductCreate = (data: Partial<ProductVO>) =>
  post<number>('/admin/products', data)
export const apiAdminProductStatus = (id: number, status: string) =>
  post<void>(`/admin/products/${id}/status`, { status })

// ---------- 订单 ----------
export interface CreateOrderPayload extends CheckoutDeliveryPayload {
  productId: number
  quantity: number
}
export const apiCreateOrder = (data: CreateOrderPayload) => post<{ orderId: number; orderNo: string }>('/orders', data)
export const apiPayOrder = (id: number) => post<void>(`/orders/${id}/pay`)
export const apiCancelOrder = (id: number) => post<void>(`/orders/${id}/cancel`)
export const apiMyOrders = (params: Record<string, unknown>) =>
  get<PageResult<OrderVO>>('/orders/my', { params })
export const apiOrderDetail = (id: number) => get<OrderVO>(`/orders/${id}`)
export const apiAdminOrders = (params: Record<string, unknown>) =>
  get<PageResult<OrderVO>>('/admin/orders', { params })
export const apiAdminShip = (id: number, logisticsNo: string) =>
  post<void>(`/admin/orders/${id}/ship`, { logisticsNo })
export const apiAdminDeliver = (id: number) => post<void>(`/admin/orders/${id}/deliver`)

// ---------- AI 下单动作 ----------
export interface AgentActionConfirmResult {
  type: OrderAction['type']; actionStatus: string; orderId?: number; orderNo?: string
  status?: string; totalAmount?: number; afterSaleId?: number; afterSaleNo?: string
}
export const apiConfirmOrderAction = (actionId: string, approval?: OrderApprovalForm) =>
  post<AgentActionConfirmResult>(`/order-actions/${actionId}/confirm`, approval)
export const apiCancelOrderAction = (actionId: string) =>
  post<void>(`/order-actions/${actionId}/cancel`)
export const apiOrderActionStatus = (actionId: string) =>
  get<Pick<OrderAction, 'status' | 'orderId' | 'orderNo'>>(`/order-actions/${actionId}`)

// ---------- 收货地址簿 ----------
export interface AddressPayload {
  name: string
  phone: string
  province: string
  city: string
  district: string
  detailAddress: string
  address: string
  isDefault?: boolean
}
export const apiAddresses = () => get<AddressVO[]>('/addresses')
export const apiAddressAdd = (data: AddressPayload) => post<AddressVO>('/addresses', data)
export const apiAddressUpdate = (id: number, data: AddressPayload) => put<void>(`/addresses/${id}`, data)
export const apiAddressDefault = (id: number) => post<void>(`/addresses/${id}/default`)
export const apiAddressDelete = (id: number) => del<void>(`/addresses/${id}`)

/** 订单状态 SSE 订阅（fetch + ReadableStream，Authorization header） */
export function subscribeOrderStatus(onEvent: (o: { orderId: number; orderNo: string; status: string }) => void): { stop: () => void } {
  const controller = new AbortController()
  const token = localStorage.getItem('token') || ''
  const run = async () => {
    try {
      const resp = await fetch(`${API_BASE}/orders/subscribe`, {
        headers: { Accept: 'text/event-stream', Authorization: `Bearer ${token}` },
        signal: controller.signal,
      })
      const reader = resp.body?.getReader()
      if (!reader) return
      const decoder = new TextDecoder()
      let buffer = ''
      let event = ''
      let data = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let idx: number
        while ((idx = buffer.indexOf('\n')) >= 0) {
          const line = buffer.slice(0, idx).replace(/\r$/, '')
          buffer = buffer.slice(idx + 1)
          if (line === '') {
            if (event === 'order_status' && data) {
              try { onEvent(JSON.parse(data)) } catch { /* ignore */ }
            }
            event = ''
            data = ''
          } else if (line.startsWith('event:')) {
            event = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            data += line.slice(5).trimStart()
          } else if (line.startsWith(':')) {
            // 心跳注释，忽略
          }
        }
      }
    } catch { /* aborted */ }
  }
  run()
  return { stop: () => controller.abort() }
}

// ---------- 会话与消息 ----------
export const apiCreateConversation = () =>
  post<{ conversationId: number; convNo: string; status: string }>('/chat/conversations')
export const apiConversations = (params: Record<string, unknown>) =>
  get<PageResult<ConversationVO>>('/chat/conversations', { params })
export const apiConversationDetail = (id: number) => get<ConversationVO>(`/chat/conversations/${id}`)
export const apiCloseConversation = (id: number) => post<void>(`/chat/conversations/${id}/close`)
export const apiSatisfaction = (id: number, score: number) =>
  post<void>(`/chat/conversations/${id}/satisfaction`, { score })
export const apiMessages = (id: number, params: Record<string, unknown>) =>
  get<PageResult<import('@/types/api').ChatMessage>>(`/chat/conversations/${id}/messages`, { params })
export const apiMessagesAfter = (id: number, afterId: number) =>
  get<import('@/types/api').ChatMessage[]>(`/chat/conversations/${id}/messages`, { params: { afterId }, silent: true } as never)
export const apiConversationStatus = (id: number) =>
  get<{ conversationId: number; status: string; humanWaitExpiresAt?: string }>(`/chat/conversations/${id}/status`, { silent: true } as never)
export const apiCancelHuman = (id: number) => post<void>(`/chat/conversations/${id}/cancel-human`)
export const apiHumanMessage = (id: number, content: string) =>
  post<void>(`/chat/conversations/${id}/human-message`, { content })

// ---------- 知识库（ADMIN） ----------
export const apiKbDocs = (params: Record<string, unknown>) =>
  get<PageResult<KbDocVO>>('/admin/kb/docs', { params })
export const apiKbDocDetail = (id: number) => get<KbDocVO>(`/admin/kb/docs/${id}`)
export const apiKbContent = (id: number) =>
  get<Blob>(`/admin/kb/docs/${id}/content`, { responseType: 'blob' })
export const apiKbUpload = (formData: FormData) => upload<KbDocVO>('/admin/kb/docs', formData)
export const apiKbToggle = (id: number, status: string) =>
  post<void>(`/admin/kb/docs/${id}/status`, { status })
export const apiKbReindex = (id: number) => post<void>(`/admin/kb/docs/${id}/reindex`)
export const apiKbDelete = (id: number) => del<void>(`/admin/kb/docs/${id}`)

// ---------- 用户管理（ADMIN） ----------
export const apiAdminUsers = (params: Record<string, unknown>) =>
  get<PageResult<UserInfo & { status: string }>>('/admin/users', { params })
export const apiAdminAgentCreate = (payload: CustomerRegistration) =>
  post<number>('/admin/users/agents', payload)
export const apiAdminUserStatus = (id: number, status: 'ACTIVE' | 'DISABLED') =>
  put<void>(`/admin/users/${id}/status`, { status })

// ---------- 统计（ADMIN） ----------
export const apiStats = () => get<StatsVO>('/admin/stats/overview')
export const apiAdminDashboard = () => get<AdminDashboardVO>('/admin/dashboard')

// ---------- 工作台（AGENT） ----------
export const apiPending = () => get<ConversationVO[]>('/workbench/pending')
export const apiServicing = () => get<ConversationVO[]>('/workbench/servicing')
export const apiClaim = (id: number) => post<void>(`/workbench/conversations/${id}/claim`)
export const apiAgentMessage = (id: number, content: string) =>
  post<void>(`/workbench/conversations/${id}/messages`, { content })
export const apiFinish = (id: number) => post<void>(`/workbench/conversations/${id}/finish`)
export const apiWorkbenchMessages = (id: number) =>
  get<import('@/types/api').ChatMessage[]>(`/workbench/conversations/${id}/messages`)
export const apiWorkbenchStatus = (id: number) =>
  get<{ conversationId: number; status: string }>(`/workbench/conversations/${id}/status`, { silent: true } as never)
export const apiWorkbenchSla = () => get<WorkbenchSla>('/workbench/sla')
