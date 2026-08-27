import { describe, expect, it } from 'vitest'
import { remainingHumanWaitSeconds } from './humanHandoff'

describe('remainingHumanWaitSeconds', () => {
  it('rounds up so the countdown does not reach zero before the deadline', () => {
    expect(remainingHumanWaitSeconds('2026-08-24T10:01:00', Date.parse('2026-08-24T10:00:00.100'))).toBe(60)
  })

  it('stays at zero after the deadline', () => {
    expect(remainingHumanWaitSeconds('2026-08-24T10:01:00', Date.parse('2026-08-24T10:01:01'))).toBe(0)
  })
})
