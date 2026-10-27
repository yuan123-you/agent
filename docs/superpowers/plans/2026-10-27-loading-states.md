# Consistent Loading States Implementation Plan

> Execute locally, task by task, with test-first verification; no subagent delegation is needed.

**Goal:** Replace bare-text loading throughout all customer, seller, admin and support pages with layout-aware skeletons, using a centered animated indicator where layout cannot be predicted.

**Architecture:** Add one small reusable LoadingState Vue component with detail, cards, list, table, stats and text skeleton variants plus a centered spinner. Keep existing content visible during pagination; replace only loading presentation, not business logic. Preserve existing home/chat skeletons and button progress indicators.

**Tech Stack:** Vue 3, TypeScript, Vite, Vitest/jsdom, existing CSS theme variables.

**Spec:** User request and attached screenshot in this chat (product detail bare loading text).

## Global Constraints
- No bare-text loading in any page or nested content loader.
- Skeletons are responsive, decorative and noninteractive; status has an accessible label.
- Honor reduced motion; use existing light/dark theme tokens.
- Do not alter API semantics, authentication, data or unrelated UI.

### Task 1: Reproduce and define loading contracts
**Files:** frontend/src/views/loadingStates.spec.ts; existing ProductDetailView, PersonalLists, LiveCatalogViews and OrderDetailView test files.
- [x] Add source-wide regression coverage against bare loading text.
- [x] Add pending-request DOM tests for detail, catalog, personal lists, cart and orders, including completion and append behavior.
- [x] Run new tests and confirm failures are due to absent visual loading UI.

### Task 2: Add reusable loading presentation
**Files:** frontend/src/components/common/LoadingState.vue and LoadingState.spec.ts.
- [x] Test every variant, accessible status, busy state, noninteractive placeholders, slot handoff and spinner centering.
- [x] Implement responsive skeleton layouts and reduced-motion styles, with no new dependencies.
- [x] Verify component tests.

### Task 3: Replace and fill loading states
**Files:** customer views ProductDetailView, ProductListView, FavoritesView, HistoryView, MyOrdersView, OrderDetailView, CartView, SeckillView, CouponCenterView, MyCouponsView; seller/admin/support views; address, coupon and quick-view components.
- [x] Replace bare initial and pagination loaders with appropriate skeleton layouts.
- [x] Replace predictable-layout overlay loaders with skeletons, without duplicating initial loaders.
- [x] Add missing initial loaders in cart, order detail, flash sales and support conversation.
- [x] Use centered spinner for unknown-format document preview.
- [x] Keep already loaded items visible during pagination, and keep action-button loading behavior.

### Task 4: Verify
- [x] Run focused regression tests then full frontend tests.
- [x] Build frontend and review diff for scope/whitespace.
- [x] Exercise loading UI in browser where available, at mobile and desktop widths.
- [x] Report evidence and any verification limits.

## Verification evidence
- Test-first runs reproduced bare-text/absent loading UI; separate metadata/SKU tests failed before their independent loading states were added.
- Final frontend suite: 41 test files, 326 tests passed (`npm test -- --reporter=dot`).
- Production build succeeded (`npm run build`, 16.95s); `git diff --check` has no whitespace errors.
- Browser: held the real product detail API pending and verified a 390px mobile detail skeleton with no loading text or horizontal overflow.
- Isolated real-component fixtures: 320px dark cards have two columns and no overflow; desktop detail is capped at 860px in a 1440px viewport.
- Spinner center offset is less than 1 CSS pixel in standalone and real Element Plus dialog fixtures; reduced-motion mode sets skeleton/spinner animation to `none`.
- Preview fixture: `frontend/tests/loading.html`; screenshots are local QA artifacts under `docs/qa/loading-states/`.
- Follow-up regression: support polling keeps existing conversation cards mounted rather than replacing them with skeletons every 10 seconds.
