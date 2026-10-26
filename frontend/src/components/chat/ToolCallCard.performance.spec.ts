import { describe, expect, it } from 'vitest'
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import ToolCallCard from './ToolCallCard.vue'

describe('tool lifecycle feedback', () => {
  it('does not leave a spinner or success check on an interrupted tool', () => {
    const host = document.createElement('div')
    const app = createApp(ToolCallCard, { card: { callId: 'a', tool: 'product_search', status: 'interrupted' } }).use(ElementPlus)
    app.mount(host)
    try {
      expect(host.querySelector('.is-loading')).toBeNull()
      expect(host.querySelector('.done-icon')).toBeNull()
      expect(host.textContent).toContain('未完成')
    } finally { app.unmount() }
  })
})


describe('compact tool result disclosure', () => {
  it('puts the result toggle in the tool header and keeps the preview collapsed', () => {
    const host = document.createElement('div')
    const app = createApp(ToolCallCard, { card: {
      callId: 'search', tool: 'product_search', status: 'done',
      result: { preview: '找到三款商品' },
    } }).use(ElementPlus)
    app.mount(host)
    try {
      const disclosure = host.querySelector<HTMLDetailsElement>('details.tool-card')
      expect(disclosure).not.toBeNull()
      expect(disclosure!.open).toBe(false)
      expect(disclosure!.querySelector('summary')?.textContent).toContain('检索商品')
      expect(disclosure!.querySelector('.preview')?.textContent).toBe('找到三款商品')
      expect(host.textContent).not.toContain('查看结果')
    } finally { app.unmount() }
  })
})
