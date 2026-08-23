import { describe, it, expect } from 'vitest'
import { StreamBuffer } from './StreamBuffer'

/** 流式链接缓冲器：token 流切分链接时的渲染安全性 */
describe('StreamBuffer', () => {
  it('无链接时原样返回', () => {
    const b = new StreamBuffer()
    b.push('你好，这是普通文本。')
    expect(b.renderable).toBe('你好，这是普通文本。')
  })

  it('尾部是完整链接时全部可渲染', () => {
    const b = new StreamBuffer()
    b.push('推荐这款 [星耀 X5 Pro](mall://product/1001)')
    expect(b.renderable).toBe('推荐这款 [星耀 X5 Pro](mall://product/1001)')
  })

  it('未闭合链接开头被扣留，等下一批 token', () => {
    const b = new StreamBuffer()
    b.push('这款手机是 [星耀 X5 Pro]')
    // 末尾 "[" 未闭合 → 扣留，不渲染半截 markdown
    expect(b.renderable).toBe('这款手机是 ')
  })

  it('长尾部视为普通文本全部返回', () => {
    const b = new StreamBuffer()
    const body = 'x'.repeat(300)
    b.push(`普通内容 [${body}`)
    expect(b.renderable).toBe(`普通内容 [${body}`)
  })

  it('reset 清空缓冲', () => {
    const b = new StreamBuffer()
    b.push('abc')
    b.reset()
    expect(b.full).toBe('')
  })
})