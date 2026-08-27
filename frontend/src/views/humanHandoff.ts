/** Remaining whole seconds in the human-agent waiting window. */
export function remainingHumanWaitSeconds(expiresAt?: string, now = Date.now()): number {
  if (!expiresAt) return 0
  const deadline = Date.parse(expiresAt.replace(' ', 'T'))
  if (!Number.isFinite(deadline)) return 0
  return Math.max(0, Math.ceil((deadline - now) / 1000))
}
