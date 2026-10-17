# Browser Image Cache Implementation Plan

> Execute inline with test-first checkpoints; do not delegate or commit automatically.

**Goal:** Persist successfully loaded storefront images in the browser and reduce unnecessary image loading.
**Architecture:** An image-only Service Worker uses Cache Storage with cache-first reads, bounded retention, expiry, duplicate-request coalescing, and network fallback. Register without delaying application mount; keep business APIs outside the cache.
**Tech Stack:** Vue 3, Vite, native Service Worker/Cache APIs, Vitest.
**Spec:** User request in this chat, clarified as browser-side caching only.

## Constraints
- No backend storage changes, new dependencies, unrelated refactors, or changes to pre-existing login work.
- Cache only same-origin GET images and public HTTPS cross-origin images with readable CORS responses; exclude failures, non-images, private/no-store responses and bypass requests.
- Keep URLs including query parameters distinct; expire within 30 days or earlier per HTTP max-age.
- Bound retained entries to 200; failures of browser storage must not break online images.
- HTTPS or localhost is required for Service Workers; unsupported environments retain ordinary loading.

## Task 1: Image cache worker
Files: create `frontend/public/image-cache-sw.js` and `frontend/src/utils/imageCacheWorker.spec.ts`.
- [x] Write tests exercising the actual worker in a VM with fake Cache Storage and fetch events: persistent hits across restarts, deduplication, expiry, invalid responses, bypass rules, eviction, storage failures and activation cleanup.
- [x] Run tests and observe missing-worker failures.
- [x] Implement the worker and rerun until passing.

## Task 2: Registration and image scheduling
Files: create `frontend/src/utils/imageCache.ts`, `frontend/src/utils/imageCache.spec.ts`; modify `frontend/src/main.ts`, image-bearing Vue components, and `frontend/nginx.conf`.
- [x] Test registration guards, base path, failure fallback and image loading attributes first.
- [x] Implement nonblocking registration with `updateViaCache: 'none'`; serve worker with no-cache headers.
- [x] Add lazy loading and asynchronous decoding to list/secondary images; prioritize the detail hero.

## Task 3: Verification
- [x] Run focused tests, the full frontend suite and production build.
- [x] Confirm the worker is copied to dist and inspect `git diff --check` and final diff.
- [x] Report actual evidence and HTTPS/first-activation limitations, without claiming measured speedups.

## Verification evidence
- Focused image-cache suite: 40/40 passing under bundled Node 24.19.0.
- Final full frontend suite: 22 test files / 143 tests passing. Earlier runs had intermittent failures in pre-existing untracked LoginView.spec.ts; no login changes were made by this task.
- Production build passed; dist worker SHA256 equals public worker SHA256.
- Real Chromium smoke fixture: Service Worker controlled page, Cache Storage entry present, two displayed images with one image request, second display successful after image endpoint returned 503.
- Cache writes run via fetch-event waitUntil rather than blocking the image response.
- git diff --check passed. No claim of measured latency improvement; final full suite is green.

## Review follow-up
- Added and verified three regression tests before fixing existing HTTP-response age, queued-write deadline extension, and blocking expired-cache deletion.

## Release preparation
- Type checking fixed without adding dependencies by using explicitly typed Node-only require helpers in tests.
- Production-specific Nginx configuration now also serves the worker with no-cache and a strict 404 fallback; regression test covers both configurations.
- Live production catalog uses Picsum/its CDN. Verified both redirect and image responses allow anonymous CORS; added readable CORS caching with normal-image fallback on CORS denial. Opaque responses remain uncached because their status/MIME cannot be validated.

- Final release validation: TypeScript noEmit passed, /aimall/ production build passed, 11 production-config tests passed, real browser persisted and redisplayed the actual cross-origin Picsum image.
- CORS cache misses bypass browser HTTP cache to avoid hidden Date/Age renewing freshness. CORS-denied, unauthorized, or non-image anonymous responses fall back to original loading and are not persisted.
