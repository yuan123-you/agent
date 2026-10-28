# User-scoped browser hot-content cache implementation plan

> Execute inline, test-first; no delegation or unrelated refactoring.

**Goal:** Persist frequently read storefront display data in a bounded, user-isolated browser cache without caching live transaction state.

**Architecture:** Add an explicit allowlist cache around the existing GET helper. Persist plain response data in localStorage buckets keyed by API base and `user.userId` (separate guest bucket); retain existing axios authentication and error handling. Clear the active bucket on successful business writes and authentication transitions; guard late responses from repopulating cleared caches.

**Tech Stack:** Existing TypeScript, axios, Pinia, Vitest/jsdom; no new dependencies.

**Spec:** User request in this chat: cache frequently accessed data on the browser, isolated per user.

## Global constraints
- Minimal frontend-only changes; do not cache credentials, addresses, chat, orders, cart, coupons, product detail or SKU state.
- Cache `/products` for 60 seconds; `/products/categories`, `/catalog/categories`, `/catalog/brands` for 10 minutes.
- Include all supported flat query parameters in a stable key. Bypass unsupported/custom request configurations and expired access tokens.
- Persist across reloads; cap each bucket at 50 entries and 1,000,000 serialized characters using least-recently-used eviction.
- Storage corruption/unavailability/quota failures must never fail a successful network request.

### Task 1: Cache behavior and lifecycle regression tests
**Files:** Create `frontend/src/api/hotContent.spec.ts`.
- [x] Exercise real GET helpers with an axios adapter, not a mocked cache.
- [x] Verify duplicate/persistent hits, query separation, expiry, guest/user isolation, result mutation isolation, concurrent deduplication and retry after failure.
- [x] Verify allowlist exclusions, explicit `cache: false`, custom config bypass, expired-token refresh, corruption and unavailable storage, bounded eviction.
- [x] Verify successful writes, logout, forced auth expiry, account switch and late responses invalidate safely.
- [x] Run `npm test -- src/api/hotContent.spec.ts` and confirm expected missing-feature failures.

### Task 2: Minimal cache and integration
**Files:** Create `frontend/src/api/hotContentCache.ts`; modify `frontend/src/api/request.ts`, `frontend/src/stores/auth.ts`.
**Interfaces:** `readHotContent<T>(url: string, params: unknown, load: () => Promise<T>): Promise<T>`; `clearHotContentCache(): void`. Extend GET config with `cache?: false`.
- [x] Implement exact allowlist TTLs, scoped bucket persistence, stable keys, bounded LRU, deduplication and generation/scope guards.
- [x] Integrate cache in GET only for standard requests and non-expired tokens. Preserve network behavior on bypass.
- [x] Invalidate after successful non-auth writes and before auth identity changes or clearing authentication.
- [x] Run focused tests and fix only issues covered by regression tests.

### Task 3: Documentation and verification
**Files:** Modify `docs/06-前端设计文档.md` with cache policy and bypass usage.
- [ ] Run `npm test` and `npm run build` from `frontend`.
- [x] Review diff for accidental changes, cache/auth races and missing exclusions; run `git diff --check`.
- [ ] Report exact coverage, verification results and remaining limitations. Do not commit or push without a request.

## Verification evidence
- Initial feature-only red run: 14 cache behavior failures, before production changes.
- Latest focused run: 62 passing tests across `hotContent.spec.ts` (44), `request.spec.ts` (12) and `auth.spec.ts` (6).
- Production build: `npm run build --prefix frontend` exited 0 (13.56 seconds); only third-party Rollup annotation warnings.
- First full-suite snapshot: 389 passing tests. A later snapshot, after other chats added tests, had 395 passing and 9 failing tests: 8 chat-recovery cases and 1 image-deployment case. The image-deployment case subsequently passed in the focused run; chat-recovery work is outside this task.
- TypeScript check: no remaining errors in cache/request/auth additions; separate in-progress chat-recovery files have type errors. Do not modify them as part of this task.
- Full-project test/type-check completion remains open while those unrelated parallel changes are unfinished. No commit or push performed.
