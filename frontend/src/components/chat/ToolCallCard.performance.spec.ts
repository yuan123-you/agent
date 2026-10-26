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
