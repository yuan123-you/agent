/**
 * ⭐ 高亮链接渲染（LinkRenderer + 点击跳转）
 * - mall:// 白名单 scheme → 高亮 span（data-route），点击 router.push
 * - 其他 scheme（http/https/javascript 等）→ 纯文本，不可点击（安全红线）
 */
import { Marked } from 'marked'
import DOMPurify from 'dompurify'

/** mall:// 链接 → 站内路由（正则白名单） */
export function toRoute(href: string): string | null {
  let m = href.match(/^mall:\/\/product\/(\d+)$/)
  if (m) return `/products/${m[1]}`
  m = href.match(/^mall:\/\/order\/(\d+)$/)
  if (m) return `/orders/${m[1]}`
  m = href.match(/^mall:\/\/products\?category=([A-Za-z0-9_-]+)$/)
  if (m) return `/products?category=${m[1]}`
  return null
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

const marked = new Marked({ breaks: true, gfm: true })

marked.use({
  renderer: {
    link(token: { href?: string; text?: string }) {
      const href = token.href || ''
      const text = token.text || ''
      if (href.startsWith('mall://')) {
        const route = toRoute(href)
        if (route) {
          return `<span class="ai-link" data-route="${route}">${escapeHtml(text)}</span>`
        }
      }
      // 非白名单链接：纯文本（防 Prompt 注入外链）
      return escapeHtml(text)
    },
  },
})

/** Markdown → 消毒后的 HTML（v-html 渲染） */
export function renderMarkdown(text: string): string {
  if (!text) return ''
  const html = marked.parse(text) as string
  return DOMPurify.sanitize(html, { ADD_ATTR: ['data-route'] })
}
