/** Optional cache for storefront display data only; never transaction or personal state. */
import { API_BASE } from './base'

const PREFIX = `aimall:hot-content:v1:${encodeURIComponent(API_BASE)}:`
const MAX_ENTRIES = 50
const MAX_CHARACTERS = 1_000_000
const TTL = new Map([
  ['/products', 60_000],
  ['/products/categories', 600_000],
  ['/catalog/categories', 600_000],
  ['/catalog/brands', 600_000],
])

/** Only these reviewed catalog payloads are public display data, not per-user promotion state. */
export function isPublicHotContentRoute(url: string): boolean { return TTL.has(url.split('?')[0]) }

interface Entry {
  key: string
  expiresAt: number
  data: unknown
}

const pending = new Map<string, Promise<unknown>>()
let generation = 0

function scope(): string | null {
  try {
    if (!localStorage.getItem('token')) return `${PREFIX}guest`
    const user = JSON.parse(localStorage.getItem('user') || 'null')
    return Number.isSafeInteger(user?.userId) && user.userId > 0
      ? `${PREFIX}user:${user.userId}` : null
  } catch {
    return null
  }
}

function queryKey(url: string, params: unknown): string | null {
  if (params == null) return JSON.stringify([url, []])
  if (typeof params !== 'object' || Object.getPrototypeOf(params) !== Object.prototype) return null
  const values = Object.entries(params).filter(([, value]) => value != null)
  if (values.some(([, value]) => !['string', 'number', 'boolean'].includes(typeof value)
    || (typeof value === 'number' && !Number.isFinite(value)))) return null
  values.sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)
  return JSON.stringify([url, values])
}

function entriesFor(owner: string): Entry[] {
  try {
    const entries: unknown = JSON.parse(localStorage.getItem(owner) || '[]')
    if (!Array.isArray(entries)) return []
    return entries.filter((entry): entry is Entry => entry !== null && typeof entry === 'object'
      && typeof entry.key === 'string' && Number.isFinite(entry.expiresAt)
      && entry.expiresAt > Date.now() && 'data' in entry)
  } catch {
    return []
  }
}

// Entries are ordered least-to-most recently used; storage is always best-effort.
function save(owner: string, entries: Entry[]): void {
  try {
    entries = entries.slice(-MAX_ENTRIES)
    let serialized = JSON.stringify(entries)
    while (serialized.length > MAX_CHARACTERS && entries.length) {
      entries.shift()
      serialized = JSON.stringify(entries)
    }
    localStorage.setItem(owner, serialized)
  } catch {
    // Corrupt, disabled or full storage must not turn a successful read into an error.
  }
}

/** Invalidate both persisted data and outstanding fills before changing authentication. */
export function clearHotContentCache(): void {
  generation++
  pending.clear()
  const owner = scope()
  if (owner) {
    try { localStorage.removeItem(owner) } catch { /* Optional storage. */ }
  }
}

export async function readHotContent<T>(url: string, params: unknown, load: () => Promise<T>): Promise<T> {
  const ttl = TTL.get(url)
  const owner = ttl ? scope() : null
  const key = owner ? queryKey(url, params) : null
  if (!owner || !ttl || key === null) return load()

  const entries = entriesFor(owner)
  const index = entries.findIndex(entry => entry.key === key)
  if (index !== -1) {
    const [hit] = entries.splice(index, 1)
    entries.push(hit!)
    save(owner, entries)
    return hit!.data as T
  }

  const pendingKey = JSON.stringify([owner, key])
  const existing = pending.get(pendingKey)
  if (existing) return existing as Promise<T>

  const startedAt = generation
  const task = load().then(value => {
    if (generation === startedAt && scope() === owner) {
      const current = entriesFor(owner).filter(entry => entry.key !== key)
      current.push({ key, expiresAt: Date.now() + ttl, data: value })
      save(owner, current)
    }
    return value
  }).finally(() => {
    if (pending.get(pendingKey) === task) pending.delete(pendingKey)
  })
  pending.set(pendingKey, task)
  return task
}
