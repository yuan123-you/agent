# Order Input Integrity Implementation Plan

> **For agentic workers:** Execute inline using test-driven-development, systematic-debugging and verification-before-completion. No parallel dispatch: defects share the same service and bounded write scope.

**Goal:** Prevent malformed order inputs and prices from creating invalid inventory or monetary snapshots.
**Architecture:** Shared service validation for REST and AI, checkout structural preflight, price validation before stock deduction. Retain existing transaction/lifecycle/SSE code.
**Tech Stack:** Java 17, Spring, MyBatis-Plus, JUnit 5, Mockito, existing H2 tests.
**Spec:** User request in this chat, 2026-10-08.

## Constraints and Verified Root
- Only OrderService.java, focused new tests, and this plan may change. No commit/reset/push/deploy, frontend, real AI/DB, or worktree. Preserve dirty baseline.
- No applicable AGENTS.md found in ancestor paths or repository.
- REST uses @Valid with DTO @NotNull/@Min(1)/@Max(99); AI action calls create directly. Service must enforce positivity without inventing a service maximum.
- create deducts stock before quantity validation or price arithmetic. Negative quantity credits stock; null quantity/price causes NPE; zero quantity or negative price creates an invalid snapshot.
- checkout validates quantity during deduction loop; null entries/IDs are not preflighted, permitting earlier write attempts before a later structural failure.
- Null/negative price must fail before that product deduction; existing transaction handles rollback across products. Zero price remains allowed.
- Full tests use mocks and explicit in-memory H2 contexts, not application boot or external services.

## Task: Service Invariants
**Files:** backend/src/main/java/com/aimall/backend/order/OrderService.java; backend/src/test/java/com/aimall/backend/order/OrderInputIntegrityTest.java; this plan.
- [x] Inspect root, contract, dirty baseline and REST/AI/cart callsites.
- [x] Write parameterized direct-service regressions for USER/AI invalid quantity, null request/ID, malformed price, invalid later checkout entry; controls for zero/positive prices and quantity 100.
- [x] Observe red via `mvn -B -Dtest=OrderInputIntegrityTest test` in backend. Assert BizException(2001) and no stock/order/notification writes for malformed input.
- [x] Add minimal request and shared product ID/quantity checks; preflight all checkout entries; guard price before deductStock. Keep existing availability/inventory errors.
- [x] Run focused test and full `mvn -B test`, inspect Surefire counts and final diff; report limitations without commit.

## Evidence
Initial test invocation was a setup failure (wrong file-write working directory, no test matched); not counted as regression red. Production code unchanged.
### Red/Green Verification (2026-10-08, Asia/Shanghai)
- Regression red: `mvn -B -f backend/pom.xml -Dtest=OrderInputIntegrityTest test`, exit 1, finished 21:06:19; 21 tests, 17 failures, 0 errors, 0 skipped. Expected invalid-input assertion failures included null quantity/request/price NPE, accepted zero/negative quantity or price, and earlier stock update attempts for malformed later checkout entries.
- Focused green: same command, exit 0, finished 21:07:06; 21 tests, 0 failures/errors/skipped.
- Removed redundant per-item quantity check after adding full structural preflight; full suite verified the final service version.
- Full backend: `mvn -B -f backend/pom.xml test`, exit 0, finished 21:08:20; 157 tests, 0 failures/errors/skipped, BUILD SUCCESS. Includes OrderInputIntegrityTest (21), OrderServiceTest (6), OrderLifecycleTest (15) and OrderLifecycleTransactionTest (9 explicit isolated H2 cases).
- `git diff --check` exit 0; only line-ending warnings. Existing lifecycle/after-commit changes remain untouched. This worker wrote only the three listed files; Maven generated ignored backend target outputs.

### Initial Upstream Findings and Boundaries (upstream findings resolved below)
- AgentOrderActionService.prepare (lines 84-85) and confirmCreate (238-239) multiply unchecked product prices before calling OrderService; requireAvailableProduct checks status/stock but not price (432-442). Null catalog price can still NPE in that upstream path; negative prepare quote can still be produced. Service prevents malformed order persistence once reached. No upstream edits authorized.
- CartController loops CheckoutItemBody entries and dereferences each before calling checkout (around 180-181); null JSON entries can still NPE there, although direct checkout now returns business errors before any writes.
- REST DTO retains existing @Max(99); direct service/AI does not add a cap (positive quantity 100 control passes). Policy harmonization is deliberately outside scope.
- A malformed later product price may be discovered after earlier product stock update attempts; @Transactional rollback remains the atomicity contract. Only structural checkout inputs are preflighted before all stock writes. New tests are Mockito-only; existing full suite tests rollback with H2, not real infrastructure.
## Authorized Upstream Extension (2026-10-08)
The user extended write scope to AgentOrderActionService preparation/quote validation and CartController null-entry handling, focused new tests, and this plan. No other production files change in this extension.

### Root and Implementation Plan
- [x] Re-inspect dirty status, ancestor/repository AGENTS (none), existing agent tests, prepare/confirm callers, cart mapping, and GlobalExceptionHandler (2001 -> HTTP 400).
- Agent prepare and pending confirmation share requireAvailableProduct; it validates status/stock only before price multiplication. Add the existing service invariant (price != null and signum >= 0, BizException 2001) once in that existing helper so both quote paths reject malformed catalog data without changing confirmation/idempotency sequencing. Do not widen OrderService's private API merely to share three guard lines across modules.
- CartController maps explicit CheckoutItemBody before reaching service preflight; guard null entries before dereference, using BizException(2001). Do not alter fallback-to-checked-cart or successful cart cleanup behavior.
- [x] Write new AgentOrderPriceIntegrityTest: null and negative prices rejected before action/order/Redis writes for preparation and pending confirmation; zero/positive price arithmetic and unchanged confirmation controls.
- [x] Write new CartCheckoutInputIntegrityTest: null first/later entries yield BizException and HTTP 400/business code 2001 with no service/mapper writes; retain valid explicit checkout and checked-cart fallback controls.
- [x] Observe both tests failing before production changes using `mvn -B -f backend/pom.xml -Dtest=AgentOrderPriceIntegrityTest,CartCheckoutInputIntegrityTest test`.
- [x] Add only the two minimal upstream guards, run focused coverage (including existing agent/order tests) and the full backend suite, then update evidence and limitations.
### Upstream Extension Evidence So Far
- Initial new-test run at 21:13:07 had 17 tests / 12 failures, including two incorrect test expectations for the existing Redis key. Corrected the tests to use the inspected `ai:order:20:10` key and supplied a working downstream order stub so negative-confirmation regressions fail on missing validation, not a null mock return. No production code changed before the corrected red run.
- Corrected regression red: `mvn -B -f backend/pom.xml "-Dtest=AgentOrderPriceIntegrityTest,CartCheckoutInputIntegrityTest" test`, exit 1, finished 2026-10-08 21:13:59 +08:00; 17 tests, 10 failures, 0 errors/skipped. Six malformed-price regressions failed (NPE or accepted negative data); four null-entry regressions failed (NPE or HTTP 500). Seven valid-path controls passed.
- Focused green: `mvn -B -f backend/pom.xml "-Dtest=AgentOrderPriceIntegrityTest,CartCheckoutInputIntegrityTest,AgentOrderActionServiceTest,OrderInputIntegrityTest,OrderServiceTest" test`, exit 0, finished 21:15:00; 58 tests, 0 failures/errors/skipped. Breakdown: new price tests 10, new cart tests 7, existing agent tests 14, previous order-integrity tests 21, existing order service tests 6.
- Upstream production diff: exactly 3 guard lines in AgentOrderActionService.requireAvailableProduct and 3 guard lines in the CartController explicit-item loop. No confirmation/idempotency/retry, quantity-limit, pricing-policy, cart-fallback or cleanup rewrites.- Final full backend: `mvn -B -f backend/pom.xml test`, exit 0, finished 2026-10-08 21:15:43 +08:00; 174 tests, 0 failures/errors/skipped, BUILD SUCCESS, duration 26.922 seconds. Existing 9 H2 transaction tests and all 17 new upstream tests passed. Surefire XML summary independently checked after run.
- Final targeted `git diff --check` exit 0 (existing OrderService LF/CRLF warning only).

### Final Scope Inventory and Blockers
Cumulative worker changes (7 files):
1. backend/src/main/java/com/aimall/backend/order/OrderService.java (initial phase only; existing dirty lifecycle work preserved)
2. backend/src/test/java/com/aimall/backend/order/OrderInputIntegrityTest.java (initial phase only)
3. backend/src/main/java/com/aimall/backend/internal/AgentOrderActionService.java (extension)
4. backend/src/test/java/com/aimall/backend/internal/AgentOrderPriceIntegrityTest.java (extension)
5. backend/src/main/java/com/aimall/backend/cart/CartController.java (extension)
6. backend/src/test/java/com/aimall/backend/cart/CartCheckoutInputIntegrityTest.java (extension)
7. docs/superpowers/plans/2026-10-08-order-input-integrity.md (both phases)

No actual blockers remain for the authorized fixes. Both originally reported upstream issues are resolved for the inspected paths. Zero-price preparation and confirmation remain supported, Redis key/TTL and confirmation behavior remain unchanged, and null entries return business code 2001 / HTTP 400 before service or mapper calls. Real infrastructure was deliberately not exercised; only Mockito, standalone MockMvc, and existing isolated H2 tests. Malformed later product prices in multi-product checkout still rely on existing transaction rollback for earlier stock deductions, as documented above; this is not a new all-product preflight feature. Parent review remains independent. No frontend/provider/live resource changes, resets, commits, pushes, deployment or worktree operations.