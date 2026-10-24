import { describe, expect, it } from 'vitest'
import consoleLayoutSource from './ConsoleLayout.vue?raw'
import { consoleActiveMenu } from './consoleLayout'

describe('console layout', () => {
  it.each([
    ['/admin/dashboard', '/admin/dashboard'],
    ['/admin/users', '/admin/users'],
    ['/admin/users/42', '/admin/users'],
    ['/workbench/conv/12', '/workbench'],
  ])('maps %s to the matching menu index', (path, expected) => {
    expect(consoleActiveMenu(path)).toBe(expected)
  })

  it('switches the fixed sidebar to a mobile drawer navigation', () => {
    // 移动端：侧栏隐藏、汉堡入口显示、抽屉菜单承载导航
    expect(consoleLayoutSource).toMatch(/@media \(max-width: 768px\)[\s\S]*?\.aside\s*\{\s*display:\s*none/)
    expect(consoleLayoutSource).toMatch(/\.menu-toggle\s*\{[\s\S]*?display:\s*inline-flex/)
    expect(consoleLayoutSource).toContain('<el-drawer')
  })
})
