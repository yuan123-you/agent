/** Optional image caching: startup and image loading still work without it. */
export async function registerImageCache(): Promise<void> {
  if (!window.isSecureContext || !('serviceWorker' in navigator)) return
  try {
    const base = import.meta.env.BASE_URL
    await navigator.serviceWorker.register(`${base}image-cache-sw.js`, {
      scope: base,
      updateViaCache: 'none',
    })
  } catch {
    // Unsupported/disabled Service Workers fall back to normal browser HTTP caching.
  }
}
