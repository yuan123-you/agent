import { describe, it, expect } from 'vitest'
import { toRoute, renderMarkdown } from './link'

/** 链接白名单路由：仅 mall:// 白名单 scheme 可点击，其他一律纯文本 */
describe('toRoute', () => {
  it('商品链接 → 商品路由', () => {
    expect(toRoute('mall://product/1001')).toBe('/products/1001')
  })

  it('订单链接 → 订单路由', () => {
    expect(toRoute('mall://order/42')).toBe('/orders/42')
  })

  it('商品列表分类链接 → 列表路由', () => {
    expect(toRoute('mall://products?category=PHONE')).toBe('/products?category=PHONE')
  })

  it('非白名单 scheme 返回 null（安全红线：不可点击）', () => {
    expect(toRoute('http://evil.com')).toBeNull()
    expect(toRoute('javascript:alert(1)')).toBeNull()
    expect(toRoute('#')).toBeNull()
    expect(toRoute('')).toBeNull()
  })
})

/** Markdown 渲染：白名单链接高亮，外部/危险链接降级为纯文本 */
describe('renderMarkdown', () => {
  it('白名单商品链接渲染为可跳转 span', () => {
    const html = renderMarkdown('见 [星耀](mall://product/1)')
    expect(html).toContain('data-route="/products/1"')
    expect(html).toContain('ai-link')
  })

  it('外部链接降级为纯文本，不产生可点击 a 标签', () => {
    const html = renderMarkdown('[点我](http://evil.com)')
    expect(html).not.toContain('<a ')
    expect(html).toContain('点我')
  })

  it('XSS 脚本被 DOMPurify 消毒', () => {
    const html = renderMarkdown('<img src=x onerror=alert(1)>')
    expect(html).not.toContain('onerror')
  })

  it('空输入返回空串', () => {
    expect(renderMarkdown('')).toBe('')
  })
})