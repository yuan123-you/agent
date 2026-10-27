import { createApp } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from './stores/auth'
import { createPinia } from 'pinia'
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import App from './App.vue'
import router from './router'
import './styles.css'
import { registerImageCache } from './utils/imageCache'
import { initTheme } from './composables/useTheme'
import { initMallTheme } from './composables/useMallConfig'
import { setUnauthorizedHandler } from './api/request'

void registerImageCache()
initTheme()
initMallTheme()

// 全局未登录处理：清理失效会话；仅受保护页面跳登录（带回跳），1.5s 内去重
let authRedirecting = false
setUnauthorizedHandler(() => {
  const auth = useAuthStore()
  auth.logoutLocal()
  if (authRedirecting) return
  const cur = router.currentRoute.value
  // Public browsing must not be interrupted by an expired background cart request.
  if (cur.meta.public || cur.path === '/login') return
  authRedirecting = true
  ElMessage.warning('请先登录')
  void router.push({ path: '/login', query: { redirect: cur.fullPath } })
  setTimeout(() => (authRedirecting = false), 1500)
})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
