// @vitest-environment node
import { beforeAll, describe, expect, it } from 'vitest'
import { build } from 'vite'
import { gzipSync } from 'node:zlib'
import { fileURLToPath } from 'node:url'
import type { OutputChunk } from 'rollup'

let initialChunks: OutputChunk[]
beforeAll(async () => {
  const result = await build({
    root: fileURLToPath(new URL('..', import.meta.url)),
    logLevel: 'silent',
    build: { write: false },
  })
  if (Array.isArray(result) || !('output' in result)) throw new Error('Expected a single client build')
  const chunks = result.output.filter((output): output is OutputChunk => output.type === 'chunk')
  const entry = chunks.find(chunk => chunk.isEntry)!
  const visited = new Set<string>()
  initialChunks = []
  function visit(chunk: OutputChunk) {
    if (visited.has(chunk.fileName)) return
    visited.add(chunk.fileName)
    initialChunks.push(chunk)
    for (const dependency of chunk.imports) {
      const imported = chunks.find(candidate => candidate.fileName === dependency)
      if (imported) visit(imported)
    }
  }
  visit(entry)
}, 60000)

describe('production startup payload', () => {
  it('does not ship unused UI components before the first route is selected', () => {
    const modules = initialChunks.flatMap(chunk => Object.keys(chunk.modules))
    expect(modules.filter(id => /element-plus\/es\/components\/(table|upload|calendar)\//.test(id))).toEqual([])
  })

  it('keeps the assistant Markdown renderer out of the shared bootstrap graph', () => {
    const modules = initialChunks.flatMap(chunk => Object.keys(chunk.modules))
    expect(modules.filter(id => /node_modules\/(marked|dompurify)\//.test(id))).toEqual([])
  })

  it('keeps initial compressed JavaScript below 180 kB', () => {
    const bytes = initialChunks.reduce((sum, chunk) => sum + gzipSync(chunk.code).length, 0)
    expect(bytes).toBeLessThan(180_000)
  })
})
