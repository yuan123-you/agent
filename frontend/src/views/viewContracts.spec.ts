import { describe, expect, it } from 'vitest'

const views = import.meta.glob('./**/*.vue', { eager: true, query: '?raw', import: 'default' }) as Record<string, string>

describe('view component contracts', () => {
  it('uses the supported scrollbar loading API', () => {
    const legacy = Object.entries(views).filter(([, source]) => source.includes('v-infinite-scroll')).map(([file]) => file)
    expect(legacy).toEqual([])
  })

  it('does not show technical storage wording in any page', () => {
    const technicalLabels = Object.entries(views).filter(([, source]) => /参数\s*JSON/.test(source)).map(([file]) => file)
    expect(technicalLabels).toEqual([])
  })
})
