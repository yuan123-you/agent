# End-to-end after-sales implementation plan

**Goal:** Persist and operate refunds, returns and exchanges across buyer orders, merchant review, platform disputes and AI actions. Keep all money movements explicitly simulated.

**Architecture:** A shared transactional AfterSaleService owns authorization, order-row locking, quantity/discount allocation and state transitions. Buyer and staff controllers expose the same workflow. Order projections include server eligibility and after-sale summaries; dedicated Vue views own application, detail and staff operations.

**Tech stack:** Existing Spring Boot 3.3.5 / MyBatis-Plus / MySQL / Flyway, Vue 3 / Element Plus / Vitest.

## Invariants
- Never change payment/order status merely because an application is submitted.
- Lock the parent order before applying or mutating an after-sale; only one active case per order item.
- Allocate actual order payment deterministically to item cents, including coupon discounts. Completed/reserved quantities and refund amounts cannot exceed the original purchase.
- Use merchant account ownership, not a client-supplied merchant ID. Platform handles disputes and merchant-less historical products.
- Refund completion is simulated and idempotent; record its reference and timestamp.
- Return/refund and exchange require approval, a real operator-entered return address and return tracking before receipt processing.
- Only explicitly accepted sellable returns replenish stock. Unshipped refunds replenish reserved stock once. Exchange dispatch reserves replacement stock atomically.
- Evidence is limited to authenticated image uploads and only readable by parties authorized for that case.
- No invented delivery events, shipping insurance or accelerated-refund promises.

## Execution / verifiable deliverables
- [x] Policy tests: permitted services by fulfillment state, paid allocation rounding, reserved quantities, over-refunds, invalid types, state transition rules.
- [x] Flyway V15: extend after_sale with return/replacement logistics, evidence/history, refund reference and completion timestamps. Preserve existing AI rows.
- [x] Shared service and APIs: apply, eligibility/quote, list/detail, withdraw, return shipment, appeal, approve/reject, receive, simulated refund, replacement dispatch/receipt, resolve feedback. Every mutation appends an immutable history entry.
- [x] Regression tests: ownership/role isolation, merchant mapping, duplicate action keys, concurrent/terminal transitions, refund stock behavior, parent-order dispatch blocking, AI-to-manual consistency.
- [x] Buyer UI: application with reason/quantity/amount/images; after-sale list and timeline/detail with contextual actions.
- [x] Staff UI: same detail and timeline, server-permitted review/receipt/refund/exchange actions, denial reasons and return address entry.
- [x] Order list/detail, profile and navigation: application/progress links, item-level state, partial/full refunded amount, real logistics only. Remove unsupported guarantees.
- [x] AI actions: submit through the same service and link confirmed cases to their detail page.
- [x] Verify backend/frontend suites, builds and types; browser-check narrow layouts and application/review/return/refund/exchange states with isolated fixtures. Record environment limitations, not false success.

## Verification evidence (2026-10-28)
- Backend full Maven suite passed: 726 canonical test cases, 0 failures, 0 errors. Saved historical red-report copies are excluded.
- Frontend 445 tests passed; Vite production build passed. Buyer conversion from an accepted exchange to a refund was also exercised.
- Existing API interceptor type mismatch in `frontend/src/api/request.ts:93` still fails TypeScript checking; no after-sale TypeScript errors reported.
- Buyer application/return/refund and merchant replacement/buyer-receipt flows exercised using isolated browser fixtures. No live database migration or real funds were executed.
