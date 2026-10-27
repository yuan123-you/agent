# Page Loading Performance Implementation Plan

**Goal:** Reduce shared startup payload and unnecessary assistant startup waits without changing business behavior.

**Architecture:** Resolve Element Plus components/directives and their styles per view rather than registering the entire library. Keep Markdown out of the bootstrap graph. Reuse already-loaded assistant list data and initialize newly created empty conversations from the create response, preserving request race protection.

**Tech Stack:** Vue 3, Pinia, Element Plus, Vite, Vitest.

**Scope:** User report: many pages load slowly, especially the AI assistant. No backend/API contract changes, unrelated refactors, or speculative caches.

## Task 1: Shared startup dependencies
- [x] Add a real production-build regression test for initial dependency size, unused UI components, and deferred Markdown; observe failures.
- [x] Enable on-demand component/directive resolution and CSS; preserve Chinese locale and service styles.
- [x] Remove chunk groups that force unused UI/Markdown modules into bootstrap dependencies.
- [x] Verify production build and component tests.

## Task 2: Assistant startup requests
- [x] Test that cached sidebar data opens history without waiting for list revalidation.
- [x] Test that creating a new conversation enables the composer without detail/history round trips, including a stale previous selection.
- [x] Make minimal view/store changes and run focused tests.

## Task 3: Verification
- [x] Run all frontend tests, TypeScript checking, production build, and diff checks.
- [x] Check rendered local pages and required loading/message/dialog/locale behavior where environment permits.
- [x] Report measured payload changes and distinguish verified local improvements from unmeasured production latency.

## Verified results

- Original production-build regression: 3 failures, including 420,096 bytes of gzip-compressed static entry JavaScript and eager UI/Markdown dependencies.
- Root cause: the old `id.includes('vue')` chunk rule also matched dependency paths containing compiled `.vue` components, pulling them into the bootstrap chunk. Match actual framework package boundaries instead.
- Final production artifacts: 105,558 bytes of compressed entry JavaScript (74.9% less). This measures the shared bootstrap graph, not every route's complete payload or online response latency.
- All 39 frontend test files / 316 tests passed with `vitest run --maxWorkers=2` on the bundled Node 24 runtime. TypeScript no-emit checking and the production build passed.
- Production build tests replace the obsolete source-text check for a monolithic UI vendor chunk. Unit tests retain their explicit UI registrations/stubs; the browser harness now uses the production on-demand registration and captures unresolved component/directive warnings.
- Browser: assistant and direct-conversation pages passed at 375px and 1280px; Chinese confirmation buttons and Markdown history rendered correctly without global Element Plus registration. The wider 33-case-per-width harness had no unresolved component/directive warnings, but still reported missing SKU/catalog/coupon fixtures and layout overflows outside this fix. These are not counted as a full visual-suite pass.
- No live backend or model latency claim; no deployment performed. Concurrent workspace changes outside the files for this fix were left intact.
