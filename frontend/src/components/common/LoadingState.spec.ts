import { afterEach, describe, expect, it } from 'vitest'
import { createApp, h, nextTick, reactive, type App } from 'vue'
import LoadingState from './LoadingState.vue'
import source from './LoadingState.vue?raw'

let app: App | undefined
let host: HTMLDivElement
function mount(props: Record<string, unknown> = {}) {
  host = document.createElement('div'); document.body.appendChild(host)
  app = createApp(LoadingState, props)
  app.mount(host)
}
afterEach(() => { app?.unmount(); host?.remove() })

describe('LoadingState', () => {
  it.each(['detail', 'cards', 'list', 'table', 'stats', 'text'])('%s presents decorative, noninteractive skeletons with an accessible status', variant => {
    mount({ variant, label: '正在获取内容', count: 3 })
    const status = host.querySelector('[role="status"]')!
    expect(status.getAttribute('aria-label')).toBe('正在获取内容')
    expect(status.getAttribute('aria-busy')).toBe('true')
    expect(host.querySelector(`[data-loading-variant="${variant}"]`)).not.toBeNull()
    expect(host.querySelector('[aria-hidden="true"] .loading-shape')).not.toBeNull()
    expect(host.querySelector('button, a, input')).toBeNull()
    expect(host.textContent?.trim()).toBe('')
  })

  it('renders the requested number of placeholder cards', () => {
    mount({ variant: 'cards', count: 6 })
    expect(host.querySelectorAll('.loading-card')).toHaveLength(6)
  })

  it('shows an animated, centered spinner instead of a standalone loading label', () => {
    mount({ variant: 'spinner', label: '正在预览文档', fullPage: true })
    expect(host.querySelector('.loading-spinner')).not.toBeNull()
    expect(host.querySelector('.loading-state--full-page')).not.toBeNull()
    expect(host.textContent?.trim()).toBe('')
    expect(source).toContain('place-items: center')
  })

  it('hands off to actual content when loading ends, without a wrapper affecting page layout', async () => {
    const props = reactive({ loading: true, variant: 'list' })
    host = document.createElement('div'); document.body.appendChild(host)
    app = createApp({ render: () => h(LoadingState, props, { default: () => h('section', '真实内容') }) })
    app.mount(host)
    expect(host.textContent).not.toContain('真实内容')
    props.loading = false; await nextTick()
    expect(host.querySelector('[role="status"]')).toBeNull()
    expect(host.firstElementChild?.tagName).toBe('SECTION')
    expect(host.textContent).toBe('真实内容')
  })

  it('supports theme tokens, mobile layout and reduced motion', () => {
    expect(source).toContain('var(--el-fill-color')
    expect(source).toContain('prefers-reduced-motion: reduce')
    expect(source).toContain('@media (max-width: 640px)')
  })
})
