# Order/Internal Numeric Integrity Implementation Plan

> Execute using test-driven-development, systematic-debugging and verification-before-completion. Shared checkout only; no commits or worktree copies.

**Goal:** Reject fractional/overflow integer JSON inputs before order/internal business effects, without changing business or permission semantics.

**Architecture:** Move the existing stateless exact Integer/Long parser into common code and retain ExactCartNumberDeserializers as an inherited compatibility facade. Apply only field-local annotations to the three OrderDtos integral fields and all 20 integral InternalToolController DTO fields. BigDecimal price filters are not integer fields and stay unchanged.

**Constraints:** No OrderController/OrderService/agent service/security/filter/frontend/schema changes; no global Jackson configuration or arbitrary new caps. Preserve getters/setters, constructors, integer strings, integral decimal/exponent tokens, signed Java ranges, nullable fields, order's existing Bean Validation quantity bound, internal null-quantity defaults, topK clamp, zero price and existing token/ownership checks. No production DB, real providers, git changes or deployments.

## Tasks
- [x] Add raw HTTP order/internal fractional, tiny-fraction and upper/lower overflow cases before production changes. Verify fixed 400/code 2001 and no mock business interactions.
- [x] Add source-authority coverage for every declared Long/Integer DTO field, signed boundaries and legacy integral tokens/direct setters. Explicitly exclude decimal prices.
- [x] Exercise the real InternalAuthFilter with synthetic tokens; missing/invalid tokens remain 401, conversation ownership/service errors remain enforced, and defaults/contracts remain unchanged.
- [x] Run new tests red and retain exact evidence under backend/target.
- [x] Move parser implementation to common/ExactNumberDeserializers.java; retain cart nested class names as thin inherited aliases, not duplicate parser code.
- [x] Annotate OrderDtos integral fields and InternalToolController DTO integral fields only. Do not modify endpoint/service bodies.
- [x] Run new focused tests plus existing cart regressions, then full backend sequentially. Record counts only after commands are terminal.

## Numeric source inventory
Order: CreateOrderRequest productId/quantity/addressId (3 fields).
Internal: ProductSearchBody userId/topK; ProductDetailBody userId/productId; OrderQueryBody userId; OrderCreateBody userId/conversationId/productId/quantity; EscalateBody userId/conversationId; OrderCancelBody userId/conversationId/orderId; AfterSalePrepareBody userId/conversationId/orderId/orderItemId/quantity; OrderConfirmBody userId (20 fields).

Token enforcement belongs to the existing InternalAuthFilter/SecurityConfig, not new DTO rules. Ownership/business decisions remain in the existing controller/services. Exact parsing controls precision/range only; it does not decide whether a signed integer is a valid business id or quantity.

## Red evidence before production changes

Initial 165-case run: 71 failures, 0 errors; expanded signed floating-overflow matrix then ran 211 cases with 109 failures, 0 errors, 0 skipped, exit 1. Retained final expanded log: `backend/target/order-internal-numeric-red.log`. No production code had changed at either red run. Source coverage failed for all 23 missing field-local annotations; raw fractions and decimal-form overflow produced HTTP success or incorrect business outcomes, and the order precision test observed 9007199254740993.0 -> 9007199254740992.

Existing API integer-overflow exceptions already use the fixed 400 handler; that does not prevent floating-number coercion. The fix must be field-local exact deserialization, not a service change or global ObjectMapper feature.

## Final verification (all commands terminal)

All Maven commands ran sequentially from `D:/studyAgent/AI Mall/backend`, using mocked services/mappers, MockMvc, synthetic tokens and the existing isolated H2 regression contexts. No production DB, Redis, provider, JWT service, frontend, deploy or git mutation was used.

| Run | Command | Exact result | Log |
| --- | --- | --- | --- |
| Expanded red before production edits | `mvn -Dtest=OrderNumericJsonIntegrityTest,InternalNumericJsonIntegrityTest,ExactNumericDtoCoverageTest test` | 211 tests, 109 failures, 0 errors, 0 skipped; exit 1 | `backend/target/order-internal-numeric-red.log` |
| Same new tests green | same command | 211 tests, 0 failures, 0 errors, 0 skipped; exit 0 | `backend/target/order-internal-numeric-green.log` |
| New slice plus all existing cart regressions | `mvn -Dtest=OrderNumericJsonIntegrityTest,InternalNumericJsonIntegrityTest,ExactNumericDtoCoverageTest,CartRequestValidationTest,CartUpdateRequestValidationTest,CartCheckoutInputIntegrityTest,CartConcurrencyTransactionTest test` | 317 tests, 0 failures, 0 errors, 0 skipped; exit 0 | `backend/target/order-internal-numeric-focused-cart.log` |
| Complete backend | `mvn test` | 484 tests, 0 failures, 0 errors, 0 skipped; exit 0 | `backend/target/order-internal-numeric-full-backend.log` |

Counts: OrderNumericJsonIntegrityTest 29; InternalNumericJsonIntegrityTest 134; ExactNumericDtoCoverageTest 48; new total 211. Existing cart regression total 106 remains passing through the compatibility facade. Complete suite increased from parent-verified 273 to 484 by exactly the 211 new cases. No pre-existing test was removed or edited.

### What the tests establish
- Raw fractional/tiny-fraction/upper and lower integer/decimal-form overflow requests for each of the 23 integral fields reject with fixed HTTP 400/code 2001 before any mock business mapper/service interaction.
- Each declared Long/Integer field has its own common exact-deserializer annotation; BigDecimal minPrice/maxPrice explicitly do not have integer annotations.
- All 23 fields preserve exact signed min/max, integral numeric 2/2.0/2e0, legacy integer string "2", nullable values, getter/setter signatures and direct setter usage.
- Order create retains its existing @Valid @Min(1)/@Max(99) quantity bounds, principal-derived userId, exact large product/address ids, zero-price and response fields.
- Internal token requests use the real InternalAuthFilter with synthetic configuration; invalid/missing tokens remain 401/code 1003 before business effects, and valid tokens yield ROLE_INTERNAL. This is not a full deployed SecurityFilterChain/JWT integration test; those sources are unchanged.
- Existing conversation ownership remains enforced by the real controller's check (403/no update), and action-service permission failures remain 403 rather than being bypassed.
- Existing internal missing/null quantity defaults remain 1; internal quantity 150 is forwarded without a new parser 99 cap; existing topK clamp remains 10; decimal price filters remain BigDecimal; confirmation still forwards exact user ids and keeps response links/fields.
- An unannotated synthetic test DTO still exhibits default Jackson coercion, proving the fix remains field-local rather than changing global ObjectMapper rules.

### Source-scope and parser reuse evidence

`backend/target/order-internal-numeric-source-scope.log` records whitespace-normalized comparisons against the pre-existing clean source, stripping only the new imports/field annotations. Both OrderDtos and InternalToolController are identical otherwise. Endpoint bodies, service delegation, defaulting and ownership logic did not change.

The numeric parser implementation was moved verbatim from the prior cart helper to common/ExactNumberDeserializers (class name/package changed; nested classes are extensible solely for the compatibility facade). Cart/ExactCartNumberDeserializers retains its outer/nested class names as thin inherited aliases. There is one parsing implementation, no duplicated conversion logic, and no new global mapper registration. Existing cart DTO annotations, controller and mapper were not edited.

### Directly edited paths in this slice

- `D:/studyAgent/AI Mall/backend/src/main/java/com/aimall/backend/order/OrderDtos.java`
- `D:/studyAgent/AI Mall/backend/src/main/java/com/aimall/backend/internal/InternalToolController.java` (DTO annotations/imports only)
- `D:/studyAgent/AI Mall/backend/src/main/java/com/aimall/backend/common/ExactNumberDeserializers.java` (new shared implementation)
- `D:/studyAgent/AI Mall/backend/src/main/java/com/aimall/backend/cart/ExactCartNumberDeserializers.java` (compatibility facade)
- `D:/studyAgent/AI Mall/backend/src/test/java/com/aimall/backend/order/OrderNumericJsonIntegrityTest.java` (new)
- `D:/studyAgent/AI Mall/backend/src/test/java/com/aimall/backend/internal/InternalNumericJsonIntegrityTest.java` (new)
- `D:/studyAgent/AI Mall/backend/src/test/java/com/aimall/backend/common/ExactNumericDtoCoverageTest.java` (new)
- `D:/studyAgent/AI Mall/docs/superpowers/plans/2026-10-08-order-internal-numeric-integrity.md` (new)

### Limits and untouched next-slice policies

- Exact signed parsing does not invent positive-id, required-field, authorization, quantity-cap or idempotency decisions; existing services/controllers keep those business decisions. Ordinary signed values in range still parse.
- Other controllers/agent-service records or unannotated DTOs outside this explicit field inventory retain their existing binding. This is not a claim of application-wide coercion hardening.
- Permission tests are isolated filter/controller/service-boundary tests; live deployment/provider/token systems were not contacted.
- Main exam Dept/schema/history, the separate MySQL worker and all other dirty files/tests remain untouched. No OrderService/agent-service/security/frontend/schema/dependency edits and no reset/commit/push/deployment.

All requested work and verification in this slice are complete; no Maven/background command remains running from this worker.
