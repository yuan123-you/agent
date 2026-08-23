import { afterEach, describe, expect, it, vi } from 'vitest'
import { releaseKbPreview, toKbPreview } from './kbPreview'

describe('knowledge base document preview', () => {
  afterEach(() => vi.restoreAllMocks())

  it('creates an object URL for PDF content', async () => {
    const createObjectURL = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:policy')
    const blob = new Blob(['%PDF'], { type: 'application/pdf' })

    const preview = await toKbPreview(blob, 'pdf')

    expect(preview).toEqual({ kind: 'pdf', url: 'blob:policy' })
    expect(createObjectURL).toHaveBeenCalledWith(blob)
  })

  it('reads markdown and text content as text', async () => {
    const preview = await toKbPreview(new Blob(['# 规则']), 'MD')

    expect(preview).toEqual({ kind: 'text', content: '# 规则' })
  })

  it('revokes PDF object URLs when the preview closes', () => {
    const revokeObjectURL = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)

    releaseKbPreview({ kind: 'pdf', url: 'blob:policy' })

    expect(revokeObjectURL).toHaveBeenCalledWith('blob:policy')
  })
})
