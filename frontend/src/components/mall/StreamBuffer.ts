/**
 * ⭐ 流式链接标记缓冲器（StreamBuffer）
 * token 流会把 `[星耀 X5 Pro](mall://product/1001)` 切成多个片段，
 * 直接渲染会闪现半截 markdown 原文；此处扣留疑似未闭合的链接尾部。
 */
export class StreamBuffer {
  private buf = ''

  push(text: string): void {
    this.buf += text
  }

  /** 完整文本（终态渲染用） */
  get full(): string {
    return this.buf
  }

  /** 可安全渲染的部分（流式期间用） */
  get renderable(): string {
    const idx = this.buf.lastIndexOf('[')
    if (idx === -1) return this.buf
    const tail = this.buf.slice(idx)
    // 尾部已是完整链接 → 全部可渲染
    if (/\[[^\]\n]*\]\([^)\n]*\)/.test(tail)) return this.buf
    // 疑似未闭合链接开始 → 扣留尾部等下一批 token
    if (tail.length <= 250) return this.buf.slice(0, idx)
    // 过长则视为普通文本
    return this.buf
  }

  reset(): void {
    this.buf = ''
  }
}
