import { createApp } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from './stores/auth'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import App from './App.vue'
import router from './router'
import './styles.css'
import { registerImageCache } from './utils/imageCache'
import { initTheme } from './composables/useTheme'
import { setUnauthorizedHandler } from './api/request'

void registerImageCache()
initTheme()

// 全局未登录处理：401/1003 时清态并跳登录页（带当前页回跳），1.5s 内去重
let authRedirecting = false
setUnauthorizedHandler(() => {
  if (authRedirecting) return
  const cur = router.currentRoute.value
  if (cur.path === '/login') return
  authRedirecting = true
  const auth = useAuthStore()
  auth.user = null
  ElMessage.warning('请先登录')
  void router.push({ path: '/login', query: { redirect: cur.fullPath } })
  setTimeout(() => (authRedirecting = false), 1500)
})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.mount('#app')
