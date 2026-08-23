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

  it('switches the fixed sidebar to a full-width mobile navigation', () => {
    expect(consoleLayoutSource).toMatch(/@media \(max-width: 760px\)[\s\S]*?\.aside\s*\{[\s\S]*?width:\s*100%\s*!important/)
  })
})
