import { describe, expect, it } from 'vitest'
declare const process: { cwd(): string }
declare function require(id: 'node:fs'): { readFileSync(path: string): Uint8Array; readFileSync(path: string, encoding: string): string }
const { readFileSync } = require('node:fs')

describe('favicon deployment', () => {
  it.each(['/', '/aimall/'])('resolves a valid icon inside the deployment base %s', base => {
    const html = readFileSync(`${process.cwd()}/index.html`, 'utf8').replaceAll('%BASE_URL%', base)
    const doc = new DOMParser().parseFromString(html, 'text/html')
    const href = doc.querySelector('link[rel="icon"]')?.getAttribute('href')
    expect(href).toBe(`${base}favicon.ico`)
    const bytes = readFileSync(`${process.cwd()}/public/favicon.ico`)
    expect([...bytes.slice(0, 4)]).toEqual([0, 0, 1, 0])
  })
})
