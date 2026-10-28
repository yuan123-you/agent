# Refunds, returns and exchanges

## Scope and payment boundary
The application uses simulated payments. Every settled refund has `refundMode=SIMULATED`, a `SIM-` reference and an explicit UI warning. No bank, wallet, payment gateway or carrier API is called. An approval is never displayed as a completed refund.

## Entry points
- Buyer: `/after-sales`, `/after-sales/:id`, order-list actions, order-detail item actions and the profile menu.
- Merchant: `/merchant/after-sales` and detail; restricted to the merchant account mapped to the case's merchant ID.
- Platform: `/admin/after-sales` and detail; disputes enter platform handling, and an administrator can explicitly take over an open merchant case with an audit reason.
- AI: confirmed `AFTER_SALE_APPLY` actions use the same transactional service and link to the same case detail.

## Workflow
- Refund only: application -> merchant/platform review -> waiting refund -> simulated refund completed.
- Return/refund: application -> review with return address -> buyer return tracking -> operator receipt -> waiting refund -> simulated refund completed.
- Exchange: application -> review with return address -> buyer return tracking -> operator receipt -> replacement dispatch with tracking -> buyer confirms replacement -> exchange completed.
- If an accepted exchange cannot be dispatched, the buyer can convert the already-received return to a refund request. The server recalculates the paid-amount cap; an operator still must execute the simulated refund.
- Buyer can withdraw before returning goods. Rejection can be appealed once to the platform, subject to current quantity and active-case checks.
- Exchange currently replaces the original product and SKU; price-difference and cross-product exchange are not supported or promised.

## Financial / inventory invariants
- Refund limits use original paid money, not the product's current price. Coupon discounts are allocated deterministically using cumulative rounding to cents across order items and quantities.
- One active case per item; completed/reserved quantities and refund amounts are bounded by the original purchase.
- The parent order is locked for mutations. Current locking reads are used under MySQL repeatable-read isolation. Idempotency keys cannot silently accept a changed payload.
- An open refund/return/exchange prevents dispatch of a still-paid order. An application does not cancel or refund its parent order.
- Unshipped refund-only cases restore their reserved product/SKU or seckill stock once. Received returns default to **no** stock restoration; operators explicitly opt in only for inspected sellable goods.
- Replacement dispatch checks product/SKU status and stock atomically; a failed SKU reservation rolls back the product reservation and shipment state.
- The order becomes refunded only when its purchased quantities have been settled as refunds. Actual refunded money remains separately visible. Original coupon release is limited to a full monetary refund and uses the existing coupon service/expiry rules.

## Evidence and deployment
- Authenticated PNG/JPEG uploads: maximum five per case, five MB each, up to 30 megapixels. Server validates content, generates filenames and checks ownership; original filenames never select a path.
- Evidence reads require authorization to the case and membership of the token in that case. Files are not exposed as public static assets.
- Flyway migration: `V15__after_sale_lifecycle.sql`. Existing AI-created records retain their identifiers and gain lifecycle fields.
- Local storage defaults to `./data/after-sale-evidence` relative to the backend working directory. Configure `app.after-sale.evidence-dir` when required. Root Docker Compose persists `/app/data/after-sale-evidence` in the `after-sale-evidence` named volume. Other deployment setups must mount/back up this private directory too.
- No unconfigured seven-day promise, automatic timeout approval, shipping insurance, pickup service or accelerated real-fund refund is advertised. Return addresses are entered by the authorized reviewer; no sample address is injected into live cases.

## Verification
Backend includes policy, service, private-image storage and H2 transaction tests for duplicate/concurrent applications, refund replay, paid/coupon allocation, cross-account access, original/replacement stock, receipt prerequisites and dispatch blocking. Frontend tests cover authoritative action permissions, draft retention, stable request keys, stale quotes/responses, management routes and unsupported-promise removal.
The browser harness `/tests/after-sales.html` provides isolated buyer/merchant/platform actors and local HTTP fixtures. It never operates real orders or funds.


## 2026-10-28 review hardening
- Original purchased `quantity` is immutable; admin fulfillment uses `dispatchableQuantity` derived from persisted per-case `cancelledFulfillmentQuantity`. V16 backfills the eligible historic pre-shipment reductions. Zero-unit orders cannot dispatch.
- Buyer dispatch is disabled. Authorized operators enter tracking themselves; absent values never manufacture a carrier number. V17 widens tracking/carrier columns to the validated 100/80-character limits.
- Refund request replay identity includes whether the original amount was explicit or default-maximum, normalized decimal amount and original evidence/reason. New APPLY history stores its digest; an identical default replay returns its original case without recalculating current eligibility. Legacy ambiguous omitted-amount replays require reading the existing case rather than guessing.
- Production Compose now declares private evidence persistence; copy old container-layer evidence before any real rollout. No live evidence copy, database migration or KB publication was executed by the audit.
- Campaign entitlement is cumulative per buyer: pending orders reserve it, unpaid cancellation releases it, and paid/refunded purchases retain it. Exchanges/refunds never silently promise a replacement campaign entitlement.
