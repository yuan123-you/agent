// Isolated visual fixture: no API requests, user data or authentication state.
import { createApp, h } from 'vue'
import { ElDialog } from 'element-plus'
import 'element-plus/es/components/dialog/style/css'
import LoadingState from '../src/components/common/LoadingState.vue'
import 'element-plus/theme-chalk/base.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import '../src/styles.css'

const params = new URLSearchParams(location.search)
const variants = ['detail', 'cards', 'list', 'table', 'stats', 'text', 'spinner'] as const
const variant = variants.find(value => value === params.get('variant')) || 'detail'
document.documentElement.classList.toggle('dark', params.has('dark'))
const content = () => h(LoadingState, { variant, fullPage: variant === 'spinner', count: 6 })
createApp({ render: () => params.has('dialog')
  ? h(ElDialog, { modelValue: true, title: '文档预览', width: '80%', top: '5vh' }, {
      default: () => h('div', { style: { minHeight: '60vh' } }, [content()]),
    })
  : content(),
}).mount('#loading-preview')
