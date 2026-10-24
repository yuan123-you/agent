import { afterEach, describe, expect, it, vi } from 'vitest'
// Match the existing test setup without adding @types/node to the browser project.
declare function require(id: 'node:fs'): { readFileSync(path: URL, encoding: string): string }
const { readFileSync } = require('node:fs')
import { registerImageCache } from './imageCache'

const register = vi.fn(async () => ({}))
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); vi.clearAllMocks() })

function browser(secure = true) {
  vi.stubGlobal('isSecureContext', secure)
  vi.stubGlobal('navigator', { serviceWorker: { register } })
}

describe('image cache registration', () => {
  it('registers without HTTP-caching the worker and respects the deployment base', async () => {
    browser()
    vi.stubEnv('BASE_URL', '/mall/')
    await registerImageCache()
    expect(register).toHaveBeenCalledWith('/mall/image-cache-sw.js', {
      scope: '/mall/', updateViaCache: 'none',
    })
  })
  it('skips insecure contexts and unsupported browsers', async () => {
    browser(false)
    await registerImageCache()
    expect(register).not.toHaveBeenCalled()
    browser()
    vi.stubGlobal('navigator', {})
    await registerImageCache()
    expect(register).not.toHaveBeenCalled()
  })
  it('does not break startup on registration failure', async () => {
    browser()
    register.mockRejectedValueOnce(new Error('disabled'))
    await expect(registerImageCache()).resolves.toBeUndefined()
  })
})

const read = (path: string) => readFileSync(new URL(path, import.meta.url), 'utf8')
describe('image loading integration', () => {
  it('registers the cache from the app entry point', () => {
    expect(read('../main.ts')).toContain('registerImageCache()')
  })
  it.each([
    '../views/CartView.vue',
    '../views/FavoritesView.vue', '../views/HistoryView.vue', '../views/merchant/MerchantProductView.vue',
  ])('defers and asynchronously decodes list images in %s', path => {
    const tags = read(path).match(/<el-image\b[^>]*>/g) || []
    expect(tags.length).toBeGreaterThan(0)
    for (const tag of tags) {
      expect(tag).toMatch(/\blazy\b/)
      expect(tag).toContain('decoding="async"')
    }
  })
  it('prioritizes the detail hero and defers the secondary image', () => {
    const tags = read('../views/ProductDetailView.vue').match(/<el-image\b[^>]*>/g)!
    expect(tags[0]).toContain('fetchpriority="high"')
    expect(tags[0]).not.toMatch(/\blazy\b/)
    expect(tags[1]).toMatch(/\blazy\b/)
    expect(tags[1]).toContain('decoding="async"')
  })
  it('serves worker updates with revalidation rather than SPA fallback', () => {
    for (const path of ['../../nginx.conf', '../../../deploy/frontend.production.conf']) {
      expect(read(path)).toMatch(/location = \/image-cache-sw\.js\s*\{[^}]*no-cache[^}]*try_files \$uri =404/s)
    }
  })
})
