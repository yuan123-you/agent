# Cart Concurrency Implementation Plan

> **For agentic workers:** Use test-driven-development, systematic-debugging and verification-before-completion. Execute in this shared checkout; no commits or worktree copies.

**Goal:** Prevent lost cart increments and invalid quantities, and commit order creation and cart persistence atomically.

**Architecture:** Keep the existing three-argument controller constructor and DTO/API fields. Use guarded SQL arithmetic for additions, the existing unique user/product constraint for first insert races, owner-scoped updates, and a controller transaction with locked cart snapshots for checkout. OrderService joins that transaction without being edited.

**Tech Stack:** Java, Spring transactions, MyBatis-Plus, JUnit 5, H2 MySQL mode.

**Spec:** User cart-concurrency dispatch of 2026-10-08.

## Global Constraints
- Initial scope: only CartController, CartItemMapper, related new tests and this plan. Parent follow-up authorizes fixture/boundary adaptations to CartCheckoutInputIntegrityTest only; no other pre-existing tests may change.
- Existing dirty files belong to other work; preserve them.
- No production database, AI, frontend, deployment, reset, commit or push.
- Add requests stay bounded to 1..99; accumulated cart quantity has no new global 99 cap.
- Zero price remains valid.
- Explicit checkout without cart membership remains valid. No new idempotency token or repeat-request prohibition.
- Existing migration V1__baseline.sql defines UNIQUE KEY uk_user_product (user_id, product_id).
- Partial-cart explicit cleanup semantics and repeated explicit requests require a user policy decision; preserve current whole matching-row cleanup, but only for rows locked before order creation.

## Task 1: Reproduce before implementation
- [x] Create CartConcurrencyTransactionTest with isolated H2/MyBatis/Spring context and real OrderService.
- [x] Exercise concurrent existing/first additions, stock limit, invalid add/update quantities, ownership, free-price checkout, order/cart rollback and an addition queued while checkout owns its snapshot.
- [x] Run `mvn -Dtest=CartConcurrencyTransactionTest test` and retain exact red output under backend/target.

## Task 2: Surgical fix
- [x] Activate @Valid on AddBody and validate direct add invocations too.
- [x] Replace read/whole-value write with `quantity = quantity + delta WHERE quantity <= stock - delta`; guarded first insert and unique-conflict retry.
- [x] Reject null, nonnumeric, fractional, overflowing and nonpositive update quantities using BigDecimal.intValueExact; use owner-scoped SQL updates with stock/status guards.
- [x] Annotate controller checkout @Transactional; select rows with FOR UPDATE in product order before invoking OrderService; delete only locked matching snapshots and reject a failed expected delete.
- [x] Validate all explicit entries before mapper/service calls; preserve checked-cart fallback and buy-now.

## Task 3: Verification
- [x] Run focused tests, cart legacy tests, then complete backend suite using only isolated test contexts.
- [x] Inspect scoped diff and report exact counts, logs, edited paths and any legacy-contract mismatch.

## Concurrency invariants
- Successful additions use atomic arithmetic and never read a quantity to compute its replacement.
- A checkout locks cart rows before inventory/order writes. Concurrent additions either precede the snapshot or resume after its deletion, and are not silently deleted.
- Order/item/stock/cart writes share one Spring transaction; failure of any expected cart cleanup rolls everything back.
- Stock changes outside cart operations can invalidate an existing cart; checkout remains the authoritative stock reservation.

## Verification evidence (2026-10-08 and runs crossing midnight into 2026-10-09)

All commands ran from `D:/studyAgent/AI Mall/backend` against generated H2 databases or mocked dependencies, not production services.

| Run | Command | Exact result | Log |
| --- | --- | --- | --- |
| Initial red | `mvn -Dtest=CartConcurrencyTransactionTest test` | 21 tests, 15 failures, 2 errors, 0 skipped (4 passed) | `backend/target/cart-concurrency-red.log` |
| Original regressions green | `mvn -Dtest=CartConcurrencyTransactionTest test` | 21 tests, 0 failures, 0 errors, 0 skipped | `backend/target/cart-concurrency-green.log` |
| Before authorized fixture adaptation | `mvn -Dtest=CartConcurrencyTransactionTest,CartRequestValidationTest,CartCheckoutInputIntegrityTest test` | 41 tests, 1 failure, 2 errors, 0 skipped; all 34 new cases pass | `backend/target/cart-concurrency-cart-suite.log` |
| Initial new-test-only green | `mvn -Dtest=CartConcurrencyTransactionTest,CartRequestValidationTest test` | 34 tests, 0 failures, 0 errors, 0 skipped; exit 0 | `backend/target/cart-concurrency-focused-green.log` |
| Historical full backend before fixture adaptation | `mvn test` | 208 tests, 1 failure, 2 errors, 0 skipped (205 passed); exit 1 | `backend/target/cart-concurrency-full-backend.log` |
| Authorized fixture adaptation | `mvn -Dtest=CartCheckoutInputIntegrityTest test` | 11 tests, 0 failures, 0 errors, 0 skipped; exit 0 | `backend/target/cart-checkout-fixture-adaptation.log` |
| Final adapted focused | `mvn -Dtest=CartConcurrencyTransactionTest,CartRequestValidationTest,CartCheckoutInputIntegrityTest test` | 45 tests, 0 failures, 0 errors, 0 skipped; exit 0 | `backend/target/cart-concurrency-adapted-focused.log` |
| Final adapted full backend | `mvn test` | 212 tests, 0 failures, 0 errors, 0 skipped; exit 0 | `backend/target/cart-concurrency-adapted-full-backend.log` |

### Integration failures introduced by this worker, and authorized fixture adaptation

**Correction:** the parent baseline was 174 tests, all passing (parent-reported). The checkout test **file** already existed; the 1 failure and 2 errors in the 208-test run were **new integration failures introduced by the controller change**, not pre-existing failing tests. The earlier report confused file provenance with failure provenance.

The new writer changes the persistence boundary: it locks authoritative rows first, deletes only those snapshots, and requires one affected row per expected cleanup. The old controller blindly deleted matching product rows and ignored row counts. Thus the older passing mock fixtures did not establish successful persistence.

The parent explicitly authorized changes to `backend/src/test/java/com/aimall/backend/cart/CartCheckoutInputIntegrityTest.java` on follow-up. No other pre-existing test file or production source is changed in this adaptation.

Exact fixture and boundary changes:
- Keep the three-argument `new CartController(cart, products, orders)` constructor in the test fixture.
- Explicit success: stub an owned snapshot with id 81/user 7/product 10/quantity 5/checked 1 and deletion result 1. Requested quantity remains 2, preserving whole matching-row cleanup rather than silently inventing partial cleanup semantics.
- Checked-cart fallback (missing and empty explicit items): give the existing snapshot id 81/user 7/checked 1 and explicitly stub deletion result 1.
- Preserve all four null-entry tests and their no-interaction/HTTP 400/code 2001 assertions, unchanged.
- Strengthen explicit success to run for total 25.00 and 0.00 and assert code/orderId/orderNo/status/totalAmount.
- Add explicit no-cart buy-now success: empty snapshot list, existing response contract, and **no delete**, rather than expecting a blind delete.
- Add explicit and fallback zero-row cleanup tests: the same authoritative snapshot plus delete result 0 must throw BizException code 2004, not return success.
- Capture mapper wrappers and assert lock-before-order-before-cleanup ordering, FOR UPDATE, product order, owner plus explicit product or checked-selection guards, and exactly id/user/product/snapshot-quantity cleanup predicates. No extra mapper/order interactions are allowed.

### Bounded old/new zero-row proof

1. Old controller: captured before the production fix, `backend/target/cart-concurrency-red.log` lines 129-130 records `zeroAffectedCleanupMustNotReportCheckoutSuccess` failing with "Expected ... BizException to be thrown, but nothing was thrown." That test gates the real H2-backed mapper delete to return 0. The old controller falsely returned checkout success; the old mock fallback likewise had Mockito's implicit delete return 0 while asserting success. Parent's 174-pass baseline does not establish cart persistence.
2. New controller boundary: `zeroRowSnapshotCleanupCannotReturnSuccess` tests explicit and fallback paths with delete result 0, asserts code 2004, and inspects the locked snapshot predicates. The existing constructor is directly exercised.
3. New real transaction: `zeroAffectedCleanupMustNotReportCheckoutSuccess` in CartConcurrencyTransactionTest asserts rollback/no created order and preserved cart; the injected-delete-exception case additionally proves stock/items/notification rollback. These integration tests are not replaced with mocks.

Historical failed-run logs are retained as evidence, not described as the final state.

### Policy uncertainty deliberately preserved

Explicit items can still order products absent from the cart, can still be submitted repeatedly without a key, and still remove the entire pre-existing matching cart row even when the explicit order quantity is smaller. A user decision is needed to change buy-now vs cart-partial/repeat semantics. No idempotency token or new membership/repeat restriction was introduced. Rows inserted after an empty explicit snapshot are not removed.

### Limits and directly edited files

H2 verifies real SQL, transaction propagation, rollback, and forced thread order; it is not a substitute for an isolated MySQL/InnoDB compatibility run. Product stock is not reserved by cart operations; later inventory changes remain checked by OrderService at checkout.

- `backend/src/main/java/com/aimall/backend/cart/CartController.java`
- `backend/src/main/java/com/aimall/backend/mapper/CartItemMapper.java`
- `backend/src/test/java/com/aimall/backend/cart/CartConcurrencyTransactionTest.java` (new)
- `backend/src/test/java/com/aimall/backend/cart/CartRequestValidationTest.java` (new)
- `backend/src/test/java/com/aimall/backend/cart/CartCheckoutInputIntegrityTest.java` (pre-existing file; authorized fixture/boundary adaptation on follow-up)
- `docs/superpowers/plans/2026-10-08-cart-concurrency.md` (new)

Existing controller null-entry validation and all other dirty work outside the explicitly authorized checkout test are preserved. No OrderService, internal AI, frontend, schema, dependency, deployment, worktree, commit or push change was made.

## Follow-up completion and remaining source risks

- [x] Adapt only the newly authorized pre-existing checkout test; preserve null-entry assertions and strengthen snapshot/row-count/response/zero-price checks.
- [x] Verify old zero-row false success against captured pre-fix red evidence; verify new explicit/fallback rejection and existing real transaction rollback tests.
- [x] Rerun focused and full backend: 45/45 and 212/212 pass. The increase from historical 208 to 212 is four additional checkout-test cases (7 -> 11); no original test is removed.
- [x] Correct failure provenance: earlier 1 failure/2 errors were this worker's integration regressions relative to the parent's 174-pass baseline.

Remaining source risks are not hidden by the green suite:
1. **Historical Integer DTO JSON coercion (cart DTO fields subsequently fixed in Task 5):** a bounded source-launch probe with the project's test classpath and default Jackson ObjectMapper deserializes quantity 1.5 as 1 in both AddBody and CheckoutItemBody. Output: `Default ObjectMapper fractional quantity probe: add=1, checkout=1`. The repository search found no explicit ACCEPT_FLOAT_AS_INT/coercion configuration. Actual deployment HTTP configuration was not separately exercised by this probe. Strict DTO JSON quantity coercion was not fixed in that fixture-only follow-up; Task 5 below fixes the five cart DTO fields, not other DTOs; Map-based update quantities are separately validated with intValueExact. Evidence: `backend/target/CartQuantityCoercionProbe.java`, `backend/target/cart-quantity-coercion-probe.log` (generated isolated diagnostic artifacts, not production source).
2. **MySQL/InnoDB coverage:** tests use H2, not an isolated MySQL database. Gap locks, lock-order contention and INSERT SELECT/unique-conflict deadlocks need MySQL-specific verification; there is no blanket retry for database deadlocks.
3. **Cart is not an inventory reservation:** inventory can change after cart writes; checkout remains the authoritative reservation boundary.
4. **Policy choices intentionally unchanged:** explicit partial quantity still clears the whole locked matching row; no-key explicit repeated requests may create repeated orders. Changing these requires a user decision, not fixture adaptation.

This follow-up directly edited only the authorized CartCheckoutInputIntegrityTest and this plan (plus generated target test/probe logs). Production controller/mapper and all other dirty tests are unchanged from the previous worker turn.
## Task 5: Authorized cart-local exact JSON boundary

Parent extends scope to new cart-local exact integer JSON deserializers, CartController DTO annotations, CartRequestValidationTest and a narrow HttpMessageNotReadableException handler in GlobalExceptionHandler. No Order DTO/OrderService or application-wide Jackson configuration change.

Caller inspection: frontend apiCartAdd(productId: number, quantity: number) sends numeric fields; CheckoutDeliveryPayload.addressId is optional number. Existing Java DTO getters/setters and three-argument controller constructor remain unchanged. Preserve legacy integer-string tokens and nullable/blank optional address values; floating numeric tokens must be mathematically integral and in Integer/Long range.

- [x] Add raw HTTP fractional/precision/overflow add and checkout tests, malformed JSON tests, and integral-token compatibility/response tests before production changes.
- [x] Confirm red: `mvn -Dtest=CartRequestValidationTest test`: 37 tests, 26 failures, 0 errors, 0 skipped; exit 1. Log `backend/target/cart-json-exact-red.log`.
- [x] Add ExactCartNumberDeserializers with IntegerValue/LongValue using original parser decimal values and intValueExact/longValueExact; preserve integer strings/null without touching global Jackson settings.
- [x] Annotate AddBody productId/quantity, CheckoutBody addressId, CheckoutItemBody productId/quantity.
- [x] Handle HttpMessageNotReadableException as HTTP 400/code 2001 with fixed message; do not return or log raw request/error contents.
- [x] Run focused and complete backend tests; report OrderDtos/internal numeric DTOs as unaddressed follow-up.

### Task 5 evidence and exact outcome

All prior commands were terminal before starting this follow-up; Maven runs remained sequential. No production DB, AI or deployment services were used.

| Run | Exact result | Log |
| --- | --- | --- |
| Raw HTTP red, before source changes | 37 tests, 26 failures, 0 errors, 0 skipped; exit 1 | `backend/target/cart-json-exact-red.log` |
| Same raw HTTP cases green | 37 tests, 0 failures, 0 errors, 0 skipped; exit 0 | `backend/target/cart-json-exact-green.log` |
| Supplemental legacy nullable-address red | 4 tests, 0 failures, 1 error, 0 skipped; exit 1 | `backend/target/cart-json-legacy-null-red.log` |
| Final cart-focused suite | 84 tests, 0 failures, 0 errors, 0 skipped; exit 0 | `backend/target/cart-json-exact-focused.log` |
| Final complete backend | 251 tests, 0 failures, 0 errors, 0 skipped; exit 0 | `backend/target/cart-json-exact-full-backend.log` |

Final focused command: `mvn -Dtest=CartRequestValidationTest,CartCheckoutInputIntegrityTest,CartConcurrencyTransactionTest test`. Full command: `mvn test`. Final focused cases: 45 HTTP/DTO cases + 11 fixture cases + 28 SQL/transaction/concurrency cases. Full suite increased from 212 to 251 because CartRequestValidationTest increased from 6 to 45; no tests were removed.

Raw JSON tests exercise fractional quantities and ids (including tiny fractions that round to an integer if converted through double), integer/floating overflow, add/explicit checkout/address fields, wrong scalar shapes, malformed JSON, stable code/message without raw-body leakage, integral decimal/exponent tokens, integer strings, exact 9007199254740993 and Long.MAX_VALUE tokens, zero price, checkout quantity 150 (no global 99 cap), unchanged DTO accessors/constructor, and an unrelated runtime error remaining HTTP 500/code 9999.

The supplemental red proved that default Jackson accepts addressId string "null" as null. The cart helper now preserves JSON null, blank/whitespace strings and textual "null", while noninteger numeric strings remain rejected. Default-Jackson compatibility probe: `backend/target/cart-json-legacy-and-order-followup-probe.log`.

Directly edited in Task 5:
- `backend/src/main/java/com/aimall/backend/cart/CartController.java`: only five @JsonDeserialize field annotations plus import relative to previous worker state.
- `backend/src/main/java/com/aimall/backend/cart/ExactCartNumberDeserializers.java`: new, cart-local exact Integer/Long parsing.
- `backend/src/main/java/com/aimall/backend/common/GlobalExceptionHandler.java`: narrow HttpMessageNotReadableException -> HTTP 400/code 2001/fixed message, no raw parser/request details logged or returned by this handler.
- `backend/src/test/java/com/aimall/backend/cart/CartRequestValidationTest.java`: additive red/green and compatibility cases; all original invalid-add cases retained.
- `docs/superpowers/plans/2026-10-08-cart-concurrency.md`.

CartItemMapper, CartCheckoutInputIntegrityTest, CartConcurrencyTransactionTest, OrderDtos, OrderService, internal DTOs and all other dirty work were not edited in Task 5. No global Jackson coercion feature was changed; no new quantity caps, idempotency token or explicit/partial/no-key policy changes.

### Remaining coercion follow-ups, not claimed solved

Bounded generated probe `backend/target/CartJsonRemainingCoercionProbe.java`, output `backend/target/cart-json-remaining-coercion-probe.log`:
- Unchanged `OrderDtos.CreateOrderRequest` under default Jackson still maps productId 10.5 -> 10, quantity 2.5 -> 2, addressId 3.5 -> 3. This is outside the permitted Order DTO scope; do not describe it as fixed by the cart annotations.
- Source inspection finds similarly unannotated numeric fields in `InternalToolController.OrderCreateBody` and `AfterSalePrepareBody`; their HTTP behavior was not invoked. They require separate review by the owner, not edits in this worker's scope.
- **Historical Map-based cart update HTTP raw-precision gap (fixed at the HTTP boundary in Task 6):** default Jackson decodes raw quantity 2.0000000000000000000000001 into Double 2.0 before requireQuantity/intValueExact runs. The isolated mock/direct-controller probe verifies response code 0 and setQuantity(...,2,...). Typed-field deserializers cannot protect an untyped Map. Task 6 below now routes HTTP through an exact typed body; the retained direct Map helper cannot recover precision already lost by its caller; ordinary nonintegral values such as 1.5 still reject in the existing update tests. No Map binding/global float configuration change was made here.

MySQL/InnoDB verification and the previously documented explicit-partial/no-key policy choices remain outstanding.
## Task 6: Bounded HTTP update precision and proven Long-path binding follow-up

Authorization: protect update raw quantity with a cart-local presence-aware DTO; retain constructor and direct Map helper; only add a path numeric binding handler where actual red evidence exists. Main exam owns owner-delete/class predicates; MySQL work belongs to another worker. No overlap edits to delete/business SQL or those tests.

Inspection: direct test callers use controller.update(Long, Long, Map); frontend uses optional numeric quantity and optional Boolean checked. Existing checkbox code is Boolean.TRUE.equals(value), so only Boolean true is on and other supplied values are off. Preserve that policy with an Object checked field plus explicit presence; do not silently add strict/coercing Boolean rules.

- [x] Write raw HTTP tiny-fraction 2.0000000000000000000000001 test before source change, with the old quantity=2 mapper write stubbed to return 1 so false success is visible.
- [x] Write valid integral 2/2.0/string2, missing fields, checkbox-only, explicit quantity null, row-count-zero guard, and unrelated-runtime tests.
- [x] Write invalid Long path HTTP tests before adding any binding handler; retain query-binding mismatch and runtime 500 cases as narrowness checks.
- [x] Run red: 22 tests, 8 failures, 0 errors, 0 skipped; exit 1. Tiny fraction returned 200 rather than 400; all three invalid Long path cases returned 500. Log `backend/target/cart-update-json-red.log`.
- [x] Add UpdateBody with exact quantity deserialization and supplied-field flags, route HTTP through it, then delegate to unchanged direct Map helper.
- [x] Add narrowly gated Long @PathVariable MethodArgumentTypeMismatchException handler returning fixed 400/code 2001; non-path mismatches delegate to existing 500 handler.
- [x] Run update-only, all focused cart, then full backend sequentially; update counts only after commands are terminal.

### Task 6 final evidence (updated only after all commands were terminal)

| Run | Command | Exact result | Log |
| --- | --- | --- | --- |
| Strengthened HTTP red before source edits | `mvn -Dtest=CartUpdateRequestValidationTest test` | 22 tests, 8 failures, 0 errors, 0 skipped; exit 1 | `backend/target/cart-update-json-red.log` |
| Same tests green | `mvn -Dtest=CartUpdateRequestValidationTest test` | 22 tests, 0 failures, 0 errors, 0 skipped; exit 0 | `backend/target/cart-update-json-green.log` |
| Final focused cart | `mvn -Dtest=CartRequestValidationTest,CartUpdateRequestValidationTest,CartCheckoutInputIntegrityTest,CartConcurrencyTransactionTest test` | 106 tests, 0 failures, 0 errors, 0 skipped; exit 0 | `backend/target/cart-update-json-focused.log` |
| Full backend | `mvn test` | 273 tests, 0 failures, 0 errors, 0 skipped; exit 0 | `backend/target/cart-update-json-full-backend.log` |

The increase from 251 to 273 is the 22 cases in the new update-boundary test class; none of the existing tests were removed or edited. The focused 106 cases comprise 45 add/checkout HTTP cases, 22 update/path cases, 11 existing checkout-fixture cases and 28 real H2 SQL/transaction/concurrency cases. Existing direct Map callers and the three-argument controller constructor still compile and pass the full suite.

Red causality:
- With the old untyped Map binding, raw `2.0000000000000000000000001` rounded to Double 2.0, invoked setQuantity(..., 2, ...) and returned HTTP 200 when the write returned 1. The captured red expected 400 but got 200.
- Invalid Long paths `not-a-long`, `81.5`, `9223372036854775808` returned 500 before the new narrowly gated path handler. This is actual HTTP evidence, not an inferred exception policy.
- Requested HTTP string quantity "2" previously rejected under the Number-only Map helper; the typed HTTP route now accepts it through the same cart-local exact deserializer used by add/checkout. The direct Map helper itself is unchanged.

Implemented boundary:
- UpdateBody tracks whether quantity and checked setters were supplied, including explicit null. Missing quantity is omitted from the delegated Map; supplied null quantity is included and rejected by the existing positive-integer guard.
- Checked remains Object and delegates through the existing Boolean.TRUE.equals rule. True/false/null/string "true"/number 1/object tests retain their former on/off behavior; no new checkbox policy or default is introduced.
- Invalid raw fraction/overflow is rejected during typed body binding, before cart lookup or persistence. Integral 2 and 2.0, and requested integer string "2", reach the guarded quantity write unchanged as Integer 2.
- Quantity/checkbox zero-row writes still fail with the existing codes 2006/2002, and runtime failures remain 500/code 9999.
- The path handler is explicitly limited to MethodArgumentTypeMismatchException for boxed Long @PathVariable parameters, returning fixed message/code 2001/400. Query binding mismatches and other binding policies keep existing handling; there is no global numeric-conversion change.

Direct edits in Task 6:
- `backend/src/main/java/com/aimall/backend/cart/CartController.java`: UpdateBody and updateHttp route; preserve direct update(Long,Long,Map) implementation and constructor. No delete/checkAll/checkout/SQL changes.
- `backend/src/main/java/com/aimall/backend/common/GlobalExceptionHandler.java`: proven Long-path conversion error handler and imports only, relative to Task 5.
- `backend/src/test/java/com/aimall/backend/cart/CartUpdateRequestValidationTest.java`: new isolated MockMvc/mock test class.
- `docs/superpowers/plans/2026-10-08-cart-concurrency.md`.

### Explicit next-slice tracking

- OrderDtos.CreateOrderRequest productId/quantity/addressId still exhibit default-Jackson truncation in the existing bounded probe. Order DTO/OrderService are **not fixed or edited** by Task 6.
- InternalToolController.OrderCreateBody, AfterSalePrepareBody and other unannotated internal numeric fields require the next owner's exact-JSON boundary review; no internal/AI HTTP calls or source edits here.
- Direct Java callers passing already rounded Number objects to the retained Map compatibility helper remain responsible for their parsing. The public cart HTTP endpoint no longer binds raw JSON through that helper's Map input.
- MySQL/InnoDB evidence belongs to the separate worker; no MySQL changes or claims were made here. Parent owner-delete/class-final work and all other dirty files/tests remain untouched.

All commands for this follow-up have exited; no background worker or Maven command remains running from this worker turn.
