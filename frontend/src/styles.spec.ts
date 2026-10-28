import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'

const dialogStyles = readFileSync(createRequire(import.meta.url).resolve('element-plus/theme-chalk/el-dialog.css'), 'utf8')
const mallStyles = readFileSync(createRequire(import.meta.url).resolve('./styles.css'), 'utf8')

describe('移动端弹窗间距', () => {
  it.each([
    ['el-dialog is-align-center', 'auto'],
    ['el-dialog', '16px'],
  ])('%s 保留对应的垂直外边距', (className, expectedMargin) => {
    const source = document.createElement('style')
    source.textContent = mallStyles
    document.head.appendChild(source)
    // jsdom does not evaluate viewport media queries, so activate the mobile rules explicitly.
    const mobileRules = [...source.sheet!.cssRules]
      .filter((rule): rule is CSSMediaRule => rule instanceof CSSMediaRule && rule.conditionText === '(max-width: 768px)')
      .flatMap(rule => [...rule.cssRules].map(child => child.cssText))
      .join('\n')
    source.remove()

    const style = document.createElement('style')
    style.textContent = `${dialogStyles}\n${mobileRules}`
    const dialog = document.createElement('div')
    dialog.className = className
    document.head.appendChild(style)
    document.body.appendChild(dialog)
    try {
      expect(getComputedStyle(dialog).marginTop).toBe(expectedMargin)
      expect(getComputedStyle(dialog).marginBottom).toBe(expectedMargin)
    } finally {
      dialog.remove()
      style.remove()
    }
  })
})
