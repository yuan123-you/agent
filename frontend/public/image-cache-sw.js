/* Image-only persistent browser cache. Bump the version if cache semantics change. */
const CACHE_PREFIX = 'ai-mall-images-'
const CACHE_NAME = `${CACHE_PREFIX}v1`
const MAX_ENTRIES = 200
const MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000
const EXPIRES_HEADER = 'X-AI-Mall-Image-Expires'
const inFlight = new Map()
let writes = Promise.resolve()

self.addEventListener('install', event => {
  event.waitUntil(self.skipWaiting())
})

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    try {
      const names = await caches.keys()
      await Promise.all(names
        .filter(name => name.startsWith(CACHE_PREFIX) && name !== CACHE_NAME)
        .map(name => caches.delete(name)))
    } catch {
      // Storage can be disabled independently of Service Workers.
    }
    await self.clients.claim()
  })())
})

function lifetime(response, receivedAt) {
  const control = response.headers.get('Cache-Control') || ''
  if (/(?:^|,)\s*(?:no-store|private|no-cache)\b/i.test(control)) return 0
  if (response.headers.get('Vary') === '*') return 0
  const maxAge = control.match(/(?:^|,)\s*max-age\s*=\s*"?(\d+)/i)
  const apparentAge = Math.max(0, receivedAt - Date.parse(response.headers.get('Date'))) || 0
  const age = Math.max(apparentAge, (Number(response.headers.get('Age')) || 0) * 1000)
  return Math.max(0, Math.min(MAX_AGE_MS, maxAge ? Number(maxAge[1]) * 1000 : MAX_AGE_MS) - age)
}

async function loadImage(request, event) {
  let cache
  try {
    cache = await caches.open(CACHE_NAME)
    const cached = await cache.match(request)
    if (cached) {
      const expires = Number(cached.headers.get(EXPIRES_HEADER))
      if (expires > Date.now()) return cached
      // Queue deletion before replacement, but never delay the network fetch for it.
      writes = writes.then(() => cache.delete(request)).catch(() => {})
      event.waitUntil(writes)
    }
  } catch {
    // Cache failures must never prevent normal network image loading.
  }

  let response
  let canCache = true
  if (new URL(request.url).origin !== self.location.origin) {
    try {
      // Public third-party images (including CDN redirects) can be cached only
      // when CORS exposes a successful image response; never cache opaque errors.
      // Reload prevents an unobservable browser HTTP-cache age from renewing TTL:
      // CORS does not expose Date/Age unless the remote host opts in.
      response = await fetch(request, { mode: 'cors', credentials: 'omit', cache: 'reload' })
    } catch {
      // An inaccessible CORS response is handled by the original request below.
    }
    if (!response || response.status !== 200
        || !(response.headers.get('Content-Type') || '').toLowerCase().startsWith('image/')) {
      // Preserve cookie-dependent/CORS-denied image loading, but never persist it.
      canCache = false
      response = await fetch(request)
    }
  } else {
    response = await fetch(request)
  }
  const receivedAt = Date.now()
  const ttl = lifetime(response, receivedAt)
  const expiresAt = receivedAt + ttl
  if (cache && canCache && response.status === 200 && ttl > 0
      && (response.headers.get('Content-Type') || '').toLowerCase().startsWith('image/')) {
    const copy = response.clone()
    // Serialize writes so concurrent image loads cannot exceed the entry limit.
    writes = writes.then(async () => {
      if (Date.now() >= expiresAt) return
      const headers = new Headers(copy.headers)
      headers.set(EXPIRES_HEADER, String(expiresAt))
      // Fetch exposes decoded bytes; do not retain wire-encoding/length metadata.
      headers.delete('Content-Encoding')
      headers.delete('Content-Length')
      await cache.put(request, new Response(copy.body, { status: 200, headers }))
      const keys = await cache.keys()
      await Promise.all(keys.slice(0, Math.max(0, keys.length - MAX_ENTRIES))
        .map(key => cache.delete(key)))
    }).catch(() => {
      // Quota/private-mode failures are nonfatal; future requests can retry.
    })
    event.waitUntil(writes)
  }
  return response
}

self.addEventListener('fetch', event => {
  const request = event.request
  const url = new URL(request.url)
  if (request.method !== 'GET' || request.destination !== 'image'
      || (url.origin !== self.location.origin && url.protocol !== 'https:')
      || ['no-store', 'reload', 'no-cache'].includes(request.cache)
      || request.headers.has('Range') || request.headers.has('Authorization')) return

  // Share the fetch, but clone its response so each <img> receives its own body.
  let pending = inFlight.get(request.url)
  if (!pending) {
    pending = loadImage(request, event).finally(() => inFlight.delete(request.url))
    inFlight.set(request.url, pending)
  }
  event.respondWith(pending.then(response => response.clone()))
})
