/** 路由 + 守卫（本地快速校验，真正鉴权在后端） */
import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
    {
      path: '/',
      component: () => import('@/layouts/ClientLayout.vue'),
      children: [
        { path: '', component: () => import('@/views/HomeView.vue') },
        { path: 'assistant', component: () => import('@/views/ChatView.vue'), meta: { customer: true } },
        { path: 'chat/:conversationId', redirect: (to) => `/assistant/${to.params.conversationId}` },
        { path: 'assistant/:conversationId', component: () => import('@/views/ChatView.vue'), meta: { customer: true } },
        { path: 'products', component: () => import('@/views/ProductListView.vue') },
        { path: 'products/:id', component: () => import('@/views/ProductDetailView.vue') },
        { path: 'orders', component: () => import('@/views/MyOrdersView.vue'), meta: { customer: true } },
        { path: 'orders/:id', component: () => import('@/views/OrderDetailView.vue'), meta: { customer: true } },
        { path: 'addresses', component: () => import('@/views/AddressesView.vue'), meta: { customer: true } },
        { path: 'cart', component: () => import('@/views/CartView.vue') },
        { path: 'favorites', component: () => import('@/views/FavoritesView.vue') },
        { path: 'history', component: () => import('@/views/HistoryView.vue') },
        { path: 'profile', component: () => import('@/views/ProfileView.vue') },
      ],
    },
    {
      path: '/merchant',
      component: () => import('@/layouts/MerchantLayout.vue'),
      meta: { roles: ['MERCHANT'] },
      children: [
        { path: '', redirect: '/merchant/products' },
        { path: 'products', component: () => import('@/views/merchant/MerchantProductView.vue') },
        { path: 'reviews', component: () => import('@/views/merchant/MerchantReviewView.vue') },
      ],
    },
    {
      path: '/workbench',
      component: () => import('@/layouts/ConsoleLayout.vue'),
      meta: { roles: ['AGENT', 'ADMIN'] },
      children: [
        { path: '', component: () => import('@/views/workbench/WorkbenchView.vue') },
        { path: 'conv/:id', component: () => import('@/views/workbench/WorkbenchConvView.vue') },
      ],
    },
    {
      path: '/admin',
      component: () => import('@/layouts/ConsoleLayout.vue'),
      meta: { roles: ['ADMIN'] },
      children: [
        { path: '', redirect: '/admin/products' },
        { path: 'products', component: () => import('@/views/admin/ProductManageView.vue') },
        { path: 'orders', component: () => import('@/views/admin/OrderManageView.vue') },
        { path: 'kb', component: () => import('@/views/admin/KbManageView.vue') },
        { path: 'users', component: () => import('@/views/admin/UserManageView.vue') },
        { path: 'stats', component: () => import('@/views/admin/StatsView.vue') },
      ],
    },
    { path: '/403', component: () => import('@/views/Error403.vue'), meta: { public: true } },
    { path: '/:pathMatch(.*)*', component: () => import('@/views/Error404.vue'), meta: { public: true } },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  const userStr = localStorage.getItem('user')
  let role = ''
  try {
    role = (JSON.parse(userStr || 'null')?.role as string) || ''
  } catch {
    role = ''
  }

  if (to.meta.public) {
    if (to.path === '/login' && token) {
      return role === 'ADMIN' ? '/admin/products' : role === 'AGENT' ? '/workbench'
        : role === 'MERCHANT' ? '/merchant/products' : '/'
    }
    return true
  }
  if (!token) {
    return `/login?redirect=${encodeURIComponent(to.fullPath)}`
  }
  const roles = (to.meta.roles as string[]) || (to.matched.find((r) => r.meta.roles)?.meta.roles as string[])
  if (roles && !roles.includes(role)) {
    ElMessage.warning('无权访问该页面')
    return '/403'
  }
  if (to.meta.customer && !['CUSTOMER', 'ADMIN'].includes(role)) {
    ElMessage.warning('请使用买家账号访问')
    return '/403'
  }
  return true
})

export default router
