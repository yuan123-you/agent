# Standards-axis audit — 2026-10-28

## Executive summary

**Final bounded-work status (2026-10-28): S1, S2, S5, S6, S7 and admin SPEC-07 are fixed in source with focused verification green.** Parent-owned S4 approval/price and buyer-dispatch changes passed the integration selection. S3 remains a reclassified robustness concern, not a proven wrong-order exploit; action-scoped keys must not be described as fixing such an exploit. Final verification: **189 Java tests / 16 selected classes, 4 admin UI tests, and frontend `tsc --noEmit` green**. No full suite, real deployment, production database migration, or real transaction was performed. The Maven slot was explicitly yielded after the successful focused run. Original findings and snapshot line references below are retained as historical provenance.

**Correction after parent integration counterevidence (2026-10-28): S3 is not a reproduced wrong-order defect on the migrated schema and is withdrawn from the proven P2 count.** The original seven-item assessment below is historical; its corrected classification is 2 P1 / 4 P2 behavioral findings plus one unproven cache-collision robustness concern, before accounting for later fixes. The parent separately reports genuine red failures for stale approved price, effective promotion quote mismatch, final-total drift, and buyer dispatch. Those results must not be conflated with S3.

**Initial audit: FAIL — 2 P1 and 5 P2 source-backed behavioral defects.** These are authorization/confirmation, inventory, persistence, and transaction-contract failures, not style findings. No claim is made that the complete application tests pass or that a deployed system was exploited. Every finding below has a deterministic reproduction/test proposal; service-level reproductions were deliberately not run against live data.

**Original read-only audit phase:** Only this report was written. No application source, dependency, migration, secret, or deployment setting was changed. No reset, commit, container operation, or full test suite was run.

## Provenance and governing standards

- Workspace: `D:\studyAgent\AI Mall`.
- HEAD verified: `ac4d87015dcba66ea0f7cbd917b1d88eefaf5ed0`.
- Commands: `git log -5 --oneline`, `git status --short`, `git diff HEAD --stat`, `git diff HEAD --numstat`, and `git diff HEAD` (captured in memory, 4,008 output lines at inspection time). **The diff is provenance, not the scope restriction.** The review included tracked unchanged files, modified files, and untracked application sources, notably the after-sale implementation and V15 migration. Working-tree changes continued concurrently; line numbers refer to the inspected live snapshot, not HEAD.
- Recent commits: `ac4d870` docs: record real-product photo rollout and production acceptance; `804a07c` fix: replace demo illustrations with verified official product photos; `5c5a5c4` docs: record production deployment and end-to-end verification; `f47e790` fix: scope platform policy lookups to global rules; `8cc816b` fix: serve verified policy excerpts on CPU deployment.
- User-provided AGENTS rules govern: clarify acceptance criteria; reproduce before fixing; simplicity; surgical changes; verify before claiming completion.
- `D:\studyAgent\AI Mall\CONTRIBUTING.md:8-10,49-56`: reproducing tests, scoped changes, affected-module verification, additive Flyway migrations, backend validation, and explicit confirmation for high-risk Agent operations.
- `D:\studyAgent\AI Mall\README.md:7,27,31,39-40,87,259-307`: backend-enforced business rules, independent SKU inventory, explicit confirmation, atomic order transitions, simulated—not real—payments, controlled deployment, and verification requirements.
- `D:\studyAgent\AI Mall\docs\after-sales.md:21-33`: refund quantity/money bounds, order locking, once-only stock restoration, and private evidence persistence.
- Alibaba open-code-review was requested as inspiration. An upstream web lookup was attempted but returned no usable page content in this session. No unverified upstream rules, release claims, or automated audit results are asserted. Repository rules take precedence over the supplied smell heuristics. This is the delegated **Standards axis**, not a separate Spec verdict or an external-tool execution.

## Hard violations / reproducible defects

### S1 — [P1] Production deployment discards private after-sale evidence on container replacement

**Follow-up status (2026-10-28): FIXED IN SOURCE, targeted regression green; not deployed.** The production backend now mounts the persistent private evidence directory. The original finding below describes the pre-fix snapshot. This S1 checkpoint predates the later commerce work. S3 is subsequently reclassified below and is not counted as a reproduced P2.

**Primary location:** `D:\studyAgent\AI Mall\deploy\compose.production.yml:141-178` (backend service has no volume mount).

**Supporting locations:** `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\aftersale\AfterSaleEvidenceStorage.java:16,25-26,34`; `D:\studyAgent\AI Mall\backend\Dockerfile:9-13`; `D:\studyAgent\AI Mall\docs\after-sales.md:33`.

**Trigger:** Upload an authenticated evidence image and attach its token to a case using the checked-in production Compose deployment. Rebuild/recreate the backend container during an ordinary release. The default path resolves beneath `/app/data/after-sale-evidence`, but that directory exists only in the old container's writable layer. MySQL retains the case and token; the replacement backend cannot read the file. Root development Compose already mounts this path; production Compose does not.

**Consequence:** Loss of dispute evidence after routine deployment, while the case still advertises an evidence token. This is a persistence/integrity failure, **not an evidence-authentication bypass**.

**Reproduction/test:** In an isolated deployment, upload/attach a small PNG, verify authorized download, recreate only backend without deleting named volumes, and verify byte-identical download again. Add a static production-Compose regression requiring a named private volume mounted at the actual configured storage root. Existing three deployment checks below do not assert this.

**Bounded fix:** Add the production backend mount and declared named volume, plus the regression. Back up/copy any existing container-layer evidence before replacing a real container; adding a mount alone does not recover old files.

### S2 — [P1] Omitting `skuId` bypasses independent SKU reservation

**Final status:** FIXED IN SOURCE. Explicit valid SKUs are required for SKU-backed products, including all-disabled variants; legacy no-SKU products remain supported. The Agent quote/order paths reject missing variants with an actionable choose-spec message instead of silently selecting one.

**Primary location:** `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\order\OrderService.java:361-364`.

**Supporting locations:** same file `:65-80,83-85,299-320`; `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\entity\MallSku.java:13-14`; `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\product\CatalogService.java:260-289`; `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\product\AdminCatalogController.java:100-104`.

**Trigger:** An on-sale product has enabled SKUs and positive aggregate stock. Call direct order creation with a valid address, quantity 1, and omitted/zero/negative `skuId`. The shared resolver returns null without checking whether the product has SKUs. Only aggregate product stock is deducted; the order item has no SKU. Explicit-item cart checkout reaches the same resolver. The normal cart-add path's stricter resolution does not protect these paths.

**Consequence:** Orders are accepted without reserving any purchasable variant. For example, with one SKU stock 2 and product aggregate 2, a SKU-less order changes only product stock to 1. A normal admin aggregate refresh restores product stock from untouched SKU stock to 2; further orders can exceed the actual variant inventory. Disabled variants can also be bypassed where aggregate stock remains positive. This contradicts the documented SKU-vs-no-SKU boundary.

**Reproduction/test:** Transaction test: seed one enabled SKU with stock 2; omit SKU on direct create and explicit checkout; assert rejection (or an explicitly selected/reserved valid SKU), never a null-SKU order. Cover null, zero, negative, and all-disabled variants; preserve the true no-SKU legacy-product case. Assert stock totals before/after aggregate refresh. AI order creation omits SKU too, so its desired variant-selection behavior must be confirmed before a fix.

### S3 — Reclassified: cache-collision / exception-path robustness concern (no proven P2 wrong-order defect)

**Status:** Excluded from the hard-violation/P2 count. The original source-only hypothesis missed a database invariant. No wrong-order exploit is claimed or reproduced on the actual migrated schema.

**Original source location (pre-fix snapshot):** `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\internal\AgentOrderActionService.java:236-245,469-470`.

**Original hypothesis, retained as superseded provenance:** A cache key containing only conversation and product could hit an earlier order when a distinct action changed quantity/address or when the earlier order had been cancelled. Reading the cache-hit branch in isolation suggested it would mark the new action confirmed against that old order and report the wrong operation successful. **That claimed consequence is withdrawn for the migrated schema.**

**Counterevidence:** `D:\studyAgent\AI Mall\backend\src\main\resources\db\migration\V3__agent_action.sql:14` declares `UNIQUE KEY uk_agent_action_order (order_id)`. A second action cannot bind to an order already linked to the first action. The constraint error from the attempted cache-hit confirmation is caught by the existing broad exception path, which falls through to fresh order creation. The unique constraint—not just the Java owner check—must be considered when assessing the complete transaction.

**Actual-schema test evidence:** `D:\studyAgent\AI Mall\backend\src\test\java\com\aimall\backend\internal\AgentOrderActionTransactionTest.java:111` recreates the unique index. The parent's RED integration reports that both `differentApprovedActionsInOneConversationDoNotReuseAnOlderOrder` (`:287-294`) and `aCancelledOrderCannotSatisfyANewlyApprovedAction` (`:295-299`) **already pass before changing the cache key**. The first asserts a distinct order, requested quantity/address, and stock; the second asserts a new pending order rather than the cancelled old order. These are counterexamples to the original claimed consequence, not red reproductions of S3. This worker verified the constraint/test sources but did not rerun Maven during the parent's reserved window.

**Remaining bounded concern:** The coarse key creates erroneous cross-action cache hits and unnecessary database constraint-exception fallbacks. Correctness on that path relies on the unique constraint and exception handling. This is a cache-collision/exception-path robustness concern, not a demonstrated P2 business-authorization or wrong-order vulnerability. No additional failure under the intact schema is asserted.

**Parent's planned change and honest claim:** Scope cache keys to persisted action identity while preserving the unique constraint, action row locking, and after-commit cache publication. Describe the change as removing cross-action cache collisions/exception fallbacks, **not as fixing a reproduced wrong-order exploit**. Keep same-action replay coverage and both already-passing distinct-action tests.

### S4 — [P2] Confirming an AI order silently replaces the reviewed amount

**Final status:** Parent-owned source fix verified in the focused integration selection. Prepare/confirm use effective quotes, renewed approval is required for drift (2015), and final created totals are checked. This worker did not edit the Agent action service.

**Primary location:** `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\internal\AgentOrderActionService.java:233-234,254-262`.

**Supporting locations:** same file `:89-105`; `D:\studyAgent\AI Mall\frontend\src\components\chat\ToolCallCard.vue:10,47-58,104`; `D:\studyAgent\AI Mall\backend\src\test\java\com\aimall\backend\internal\AgentOrderActionServiceTest.java:109-121`.

**Trigger:** Prepare a no-SKU/non-seckill product at 99, quantity 2: the pending card shows payable 198. Increase product price to 120 before confirmation. Confirmation calculates `currentAmount` but never compares it to the persisted prepared amount; order creation uses current price and overwrites the action amount with 240. No updated-price confirmation is requested.

**Consequence:** The amount on the high-risk confirmation card is not bound to the operation executed. The order is pending-payment and payments are simulated; this is **not a claim of real unauthorized fund transfer**. It is a concrete approval-integrity defect.

**Reproduction/test:** Prepare at 99, change to 120, then confirm; require a conflict/requote and no newly confirmed order until the revised quote is approved. Also cover promotion changes and unchanged-price replay. The existing test explicitly accepts current-price creation, so changing that expectation requires a scoped acceptance decision, not blindly adding a comparison or freezing stale prices.

### S5 — [P2] “Per-person” seckill limit is checked per line/request only

**Final status:** FIXED IN SOURCE. Buyer-row serialization plus current locking reads enforce entitlement across requests and duplicate checkout lines. Pending orders reserve quota; only unpaid cancellation releases it. Paid/shipped/delivered/refunded purchases retain quota conservatively. The read-only Agent quote checks entitlement without reservations or writes. This explicit rule is documented in the promotion service; no quota schema/counter was introduced.

**Primary location:** `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\promotion\PromotionService.java:190-198`.

**Supporting locations:** `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\order\OrderService.java:67-73,299-306`; `D:\studyAgent\AI Mall\backend\src\main\resources\db\migration\V10__mall_promotion.sql:53`; `D:\studyAgent\AI Mall\docs\09-对标mall商品中心改造说明.md:90-95`.

**Trigger:** Set campaign stock 10 and per-person limit 1. The same authenticated buyer submits two quantity-1 orders, sequentially or concurrently. Both pass: validation receives no user identity and queries no previous purchases/reservations. A single explicit checkout with two lines for the same campaign also validates each line independently.

**Consequence:** One buyer can consume the campaign pool despite the advertised per-person limit. The optimistic inventory update still prevents the campaign stock going negative; it does not enforce purchase entitlement.

**Reproduction/test:** Verify first purchase succeeds and subsequent sequential/concurrent purchases for that user/campaign do not exceed the configured limit; also test duplicate product lines in one checkout and an independent second user. Clarify whether pending orders reserve the entitlement and whether cancellation releases it before fixing.

### S6 — [P2] Explicit partial checkout deletes the full existing cart quantity

**Final status:** FIXED IN SOURCE. Cleanup subtracts the combined actually purchased quantity for the matching product/SKU, retains unpurchased units, and preserves snapshot quantity CAS, locking, and rollback behavior.

**Primary location:** `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\cart\CartController.java:327-334`.

**Supporting location:** same file `:287-308,324-326`.

**Trigger:** Cart contains product P/SKU S with quantity 5. Submit explicit checkout for the same pair with quantity 1, as permitted by this buy-now endpoint. It creates an order for 1, but selects the whole quantity-5 cart row as a cleanup snapshot and deletes it. The equality predicate compares the row to the snapshot, not the purchased quantity.

**Consequence:** Four unpurchased cart units disappear. Locking prevents a concurrent stale deletion but does not make the quantity accounting correct. The checked-cart path, which purchases the complete row, is not the problematic case.

**Reproduction/test:** Seed quantity 5, explicitly buy 1, assert order quantity 1 and remaining cart quantity 4—or keep the buy-now cart untouched if that is the chosen contract. Cover duplicate explicit lines, a matching SKU, and rollback. Confirm which of these two cart-cleanup contracts is intended before changing code.

### S7 — [P2] Partial pre-shipment refunds release stock but leave refunded units in dispatch

**Final status:** FIXED IN SOURCE with parent integration. V16 persists the per-case release marker; the parent atomically sets it in the PAID + REFUND_ONLY stock-restoration block. Admin fulfillment exposes dispatchable quantity separately from immutable purchased quantity and rejects zero-unit shipments. Admin tracking is required/bounded; V17 aligns persistent columns with the approved bounds.

**Primary location:** `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\aftersale\AfterSaleService.java:194-200`.

**Supporting locations:** `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\mapper\OrderInfoMapper.java:27-29`; `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\order\OrderService.java:180-182,194-208`; `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\order\AdminOrderController.java:54-55`; `D:\studyAgent\AI Mall\frontend\src\views\admin\OrderManageView.vue:22,43`.

**Trigger:** Pay for a two-unit line; complete a refund-only case for one unit before shipment. One unit is immediately restored to available stock, but not all units were refunded, so the order remains PAID. The completed case no longer blocks shipping. Ship the order: original line quantity remains 2, and both the admin API and dispatch view expose those original two units with no effective outstanding quantity.

**Consequence:** The system offers the same refunded unit for resale while the fulfillment contract still instructs dispatch of both units. It permits shipping stock no longer reserved for that order. This is a source/API contract defect; actual warehouse shipment was not executed during the audit.

**Reproduction/test:** In the H2 after-sale transaction fixture, purchase/pay quantity 2, refund quantity 1, then invoke shipping and inspect its authoritative item representation. Require only one dispatchable unit, with original purchase snapshots retained for refund arithmetic. Cover a fully refunded line inside a multi-line order as well. Clarify whether a fulfillment-quantity projection or a narrower dispatch restriction is desired; do not rewrite immutable order snapshots casually.

## Optional smells — not hard violations

**None promoted to findings.** Dense after-sale methods, duplicated stock loops, repeated status switches, primitive role/status values, and similar shapes are only heuristics. No cosmetic rename, framework migration, general service split, or speculative abstraction is requested. Tool-enforced typing/format issues are excluded from this axis; the parent's request/interceptor fix is not duplicated.

## Covered areas and explicit exclusions

### Covered / sampled

- Inventoried the complete backend Java source tree (129 Java files), rather than only changed hunks. Manual depth focused on security filters/configuration, auth/registration and admin status controls; buyer/address ownership; merchant product/review ownership; order creation/cancellation/shipping/receipt, cart checkout, SKU and promotion inventory; prepared AI actions; after-sale policy/service/controller/evidence storage; relevant mapper SQL/entities and transaction fixtures.
- Sampled workbench ownership, chat conversation ownership and principal injection; internal tool/memory/file boundaries; knowledge-base admin/content/current-version entry points. Existing positive controls were considered before raising findings.
- Reviewed V15 as a new migration; no tracked historical migration changes appeared in the baseline migration diff. The targeted uniqueness test found no duplicate Flyway version labels. No database migration was applied.
- Inspected both public Compose definitions, backend Dockerfile, relevant application settings with secret placeholders, production frontend Nginx boundary, and CI job definitions. The AI internal-token middleware and backend outbound internal-token/header boundary were sampled; production AI is not exposed through a public Compose port.
- Frontend sampling was limited to AI confirmation-card amount presentation, admin dispatch quantities, and image-worker private/no-store/auth-header handling. Evidence download does check case authorization, token membership, owner path, image type/size, and no-store/nosniff headers; no unsupported public-file leak is alleged.
- CI review observed backend, frontend, AI, eval-baseline and AI-image smoke jobs. Missing build/test gates alone were not elevated into speculative defects. No third-party vulnerability/version audit was performed.

### Excluded / not certified

- `D:\studyAgent\AI Mall\.env`, any `.env` variants, private deployment directories, keys/tokens/credentials, production data, container filesystems, remote systems, and deployment-helper/archive contents. No environment expansion or `docker compose config` that might load the real `.env` was used.
- `D:\studyAgent\AI Mall\frontend\src\api\request.ts` and its interceptor/Blob/ArrayBuffer tests are owned by the parent and were not changed or independently audited here.
- No exhaustive functional/UI/RAG/model-quality review, no real checkout/payment/shipping/refund, no load test, and no exhaustive inspection of every inventoried source body. The full-tree **selection scope** should not be confused with an assertion of line-by-line complete coverage.
- Concurrent uncommitted work is not evidence of violating test-first workflow. Test ideas below are requirements for a future scoped patch, not claims that the author failed to run tests.

## Narrow verification actually run

Executed only these independent read-only test methods, with bytecode-cache writing disabled:

```text
python -B -m unittest deploy.test_production.ProductionTests.test_unique_migration_versions deploy.test_production.ProductionTests.test_production_network_and_secrets deploy.test_production.ProductionTests.test_frontend_preserves_verified_visitor_ip -v
Result: 3 tests, 0.002 seconds, OK.
```

A separate in-memory source/config probe reported:

```text
production_backend_has_volume_declaration = False
production_mentions_evidence = False
root_compose_persists_evidence = True
```

These checks read explicitly named public sources/configs, did not execute application services, did not read secrets, did not modify project sources/build artifacts, and did not compete with the parent's full baseline suites. They do **not** establish regression tests for S2–S7; those require a newly authorized scope and red-first tests.

## Snapshot fingerprints

Sampled at `2026-10-28T14:36:05+08:00` (SHA-256; use these when concurrent changes move line numbers):

| Absolute path | SHA-256 |
| --- | --- |
| `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\order\OrderService.java` | `B84D56101484673E647EAA508D30C702D89E41E6015C1903E12280A0D9BDE63E` |
| `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\internal\AgentOrderActionService.java` | `51C63F3609C56FB0FEA3E5BF2EBD944FE3C28968C9FA5322D03F38C46666B134` |
| `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\aftersale\AfterSaleService.java` | `523066BEFDE32EEFE3F08620404FF0B622C0A36C084721F7A33E91FAF9A7AC60` |
| `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\cart\CartController.java` | `2912470E2E718374C7B1067F636FD5819AC01CEFB1EA030A51764CBA3C055C1A` |
| `D:\studyAgent\AI Mall\deploy\compose.production.yml` | `0F817208C126397952DF5F66297E502AFBD81A47D058450190D66554BBFF3F90` |

## Bounded scope requested from parent

1. **First patch proposal:** S1 only: production evidence persistence mount/volume plus one deployment-config regression; confirm how any existing evidence is backed up before a real redeploy. No frontend request changes.
2. **Separate acceptance decisions:** S2 SKU omission behavior (including AI compatibility); S3 action-scoped idempotency; S4 renewed price approval; S5 entitlement/cancellation accounting; S6 buy-now cart cleanup; S7 partial-refund fulfillment semantics.
3. For each approved slice, add a failing reproducer first, make the smallest targeted change, and run only affected tests until the parent coordinates the final cross-module verification matrix.

**The original audit did not implement fixes. The parent subsequently authorized S1 only; its bounded source fix and verification are recorded below. S2–S7 remain read-only pending separate scope.**


## S1-only authorized implementation — 2026-10-28

**Status:** Source/configuration fix complete, focused checks green, no deployment performed. S2–S7 were not changed.

### Exact changed paths

- `D:\studyAgent\AI Mall\deploy\compose.production.yml`: add only the backend mount `after-sale-evidence:/app/data/after-sale-evidence` and its top-level named-volume declaration. The pre-existing environment/configuration changes were preserved byte-for-byte; removing just these two inserted lines recovers the pre-worker SHA-256 `0f817208c126397952df5f66297e502afbd81a47d058450190d66554bbff3f90`. Post-fix Compose SHA-256: `f0da1d3ead1da2be39c2027045e7a320cde0b2db293047fc4eafbfb99f97ca2a`.
- `D:\studyAgent\AI Mall\deploy\test_production.py`: add one standard-library `unittest` regression following the existing deployment-test conventions. It requires the exact application directory to use a declared named volume, rejects sharing that volume with other/public services, and rejects direct evidence-path serving in the production static Nginx configuration. No new dependency was added.
- `D:\studyAgent\AI Mall\docs\audits\2026-10-28-standards-review.md`: update S1 status and record this red/green evidence. Original snapshot fingerprints above remain historical.

### Red-first evidence

Before changing production Compose, ran:

```text
python -B -m unittest deploy.test_production.ProductionTests.test_production_persists_private_after_sale_evidence -v
```

Result: **1 test, FAILED (failures=1)** at the persistence assertion, with `AssertionError: unexpectedly None : Backend evidence directory needs a persistent named-volume mount`. This was the expected configuration defect, not an import, parser, dependency, or runtime error.

### Green evidence

After adding the two Compose lines, ran:

```text
python -B -m unittest deploy.test_production.ProductionTests.test_production_persists_private_after_sale_evidence deploy.test_production.ProductionTests.test_production_network_and_secrets deploy.test_production.ProductionTests.test_frontend_preserves_verified_visitor_ip deploy.test_production.ProductionTests.test_nginx_hides_internal_routes -v
```

Result: **4 tests, OK** (0.004 seconds). Scoped `git diff --check` passed. The new mount belongs only to backend; frontend/static Nginx receives no evidence volume or public serving route. Existing authenticated evidence handlers were not changed. These are source/configuration checks, not a real container-recreation or deployed-authorization test.

### Operational boundary / backup requirement

No real deployment, container restart/recreation, backup/copy operation, secret access, commit, or broad test suite was performed. Before a future real deployment, back up/copy any evidence already in the old backend container's writable layer into the persistent private volume using the approved operational procedure. An initially empty mounted volume hides existing container-layer files; this source fix does not migrate or recover those files. Preserve the named volume during normal upgrades and backup retention. The parent must coordinate any later deployment and remaining findings separately.


## Final bounded commerce implementation and integration verification

### Contracts and ownership

- `OrderService.quoteForAgent(Long userId, Long productId, int quantity)` returns `BigDecimal` effective **TOTAL**. It validates product/SKU/promotion/stock and buyer campaign entitlement without reservations or order writes. The signature was kept stable for the parent.
- `AfterSale.cancelledFulfillmentQuantity` is an `Integer` initialized to `0`, persisted as `cancelled_fulfillment_quantity INT NOT NULL DEFAULT 0` by V16. Parent-owned code atomically sets it to the case quantity only in the original pre-shipment refund stock-release block.
- `OrderItem.dispatchableQuantity` is a non-persistent admin/API projection. Original `quantity`, prices, and subtotals remain purchase snapshots for refund arithmetic. Shipping checks the persisted reductions under the parent order lock, never refund-money inference.
- V16 backfills only completed refund-only cases on orders still PAID without a shipment timestamp; ambiguous historical terminal cases stay zero. V17 widens tracking to 100 and optional carrier to 80, preserving values and nullability. No published migration was edited and no V17 quota table is needed.
- Admin shipping never manufactures tracking numbers; it rejects missing/blank or over-100-character trimmed tracking and over-80-character trimmed carrier. The optional carrier remains backward-compatible. The UI requires operator input, blocks empty/oversized submissions, and disables zero-unit dispatch.
- Existing public constructors were preserved. The worker did not edit the parent-owned Agent action service, after-sale service, buyer OrderController, or buyer OrderDetail UI. Their integration tests were executed only within the released Maven window.
- S3 counterevidence remains decisive: the unique action/order constraint made the two distinct-action tests pass before the key change. The parent's action-key change removes collisions and exception fallbacks, not a reproduced wrong-order exploit.

### Exact files changed by this worker (including completed S1)

```text
D:\studyAgent\AI Mall\deploy\compose.production.yml
D:\studyAgent\AI Mall\deploy\test_production.py
D:\studyAgent\AI Mall\docs\audits\2026-10-28-standards-review.md
D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\order\OrderService.java
D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\order\AdminOrderController.java
D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\cart\CartController.java
D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\promotion\PromotionService.java
D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\entity\AfterSale.java
D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\entity\OrderItem.java
D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\mapper\MallSeckillMapper.java
D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\mapper\OrderItemMapper.java
D:\studyAgent\AI Mall\backend\src\main\resources\db\migration\V16__after_sale_fulfillment_quantity.sql
D:\studyAgent\AI Mall\backend\src\main\resources\db\migration\V17__shipping_metadata_lengths.sql
D:\studyAgent\AI Mall\backend\src\test\java\com\aimall\backend\order\AdminOrderShippingValidationTest.java
D:\studyAgent\AI Mall\backend\src\test\java\com\aimall\backend\order\AfterSaleFulfillmentMigrationTest.java
D:\studyAgent\AI Mall\backend\src\test\java\com\aimall\backend\order\OrderShippingMetadataMigrationTest.java
D:\studyAgent\AI Mall\backend\src\test\java\com\aimall\backend\order\OrderSkuAndAgentQuoteTest.java
D:\studyAgent\AI Mall\backend\src\test\java\com\aimall\backend\order\SeckillEntitlementTransactionTest.java
D:\studyAgent\AI Mall\backend\src\test\java\com\aimall\backend\order\OrderLifecycleTest.java
D:\studyAgent\AI Mall\backend\src\test\java\com\aimall\backend\order\OrderLifecycleTransactionTest.java
D:\studyAgent\AI Mall\backend\src\test\java\com\aimall\backend\cart\CartConcurrencyTransactionTest.java
D:\studyAgent\AI Mall\backend\src\test\java\com\aimall\backend\cart\CartSkuBoundaryTransactionTest.java
D:\studyAgent\AI Mall\frontend\src\types\api.d.ts
D:\studyAgent\AI Mall\frontend\src\views\admin\OrderManageView.vue
D:\studyAgent\AI Mall\frontend\src\views\admin\OrderManageView.spec.ts
```

Pre-existing/concurrent edits in these shared files were retained. Other modified files shown by Git belong to the parent or earlier work; this list does not attribute those edits to this worker.

### Red-first evidence

- S2/Agent quote: `OrderSkuAndAgentQuoteTest` initially ran 7 tests with 5 failures: missing SKU failed to reject and the quote method did not yet exist. Its same behavior selection became green; tests now call the implemented quote signature directly.
- S7 marker/migration: `AfterSaleFulfillmentMigrationTest` initially demonstrated the missing field and V16 resource, then passed after the entity/migration addition.
- S5/S6/S7/admin tracking: the focused pre-fix selection of 79 tests had 16 assertion failures and 4 missing-result/API errors. Quota tests demonstrated repeat/concurrent/duplicate-line bypass; cart tests demonstrated lost rows; dispatch tests demonstrated zero-unit shipment acceptance and the absent projection; tracking tests demonstrated generated/unchecked input. These became green after scoped changes. Two old shipping fixture expectations were updated to provide a legitimate dispatchable item and allow the new read-only validation queries, rather than bypassing production checks.
- Admin UI: all 4 reproducing tests initially failed (original-only quantities, zero-unit shipping offered, empty tracking submitted, bounds unchecked), then all 4 passed.
- V17: `OrderShippingMetadataMigrationTest` first ran with **1 assertion failure**, because the required sizing migration did not exist. Initial combined-column SQL hit an H2 syntax incompatibility; splitting the migration into two ordinary `ALTER TABLE ... MODIFY COLUMN ...` statements resolved it. The final migration test passes, verifies acceptance at 100/80, and verifies rejection at 101/81. This is H2 MySQL-mode evidence, not a claim that a live MySQL deployment was migrated.

Evidence logs generated by focused runs (ignored build artifacts, not committed source):

```text
D:\studyAgent\AI Mall\backend\target\commerce-bounded-red.log
D:\studyAgent\AI Mall\backend\target\commerce-bounded-green.log
D:\studyAgent\AI Mall\backend\target\shipping-v17-red.log
D:\studyAgent\AI Mall\backend\target\shipping-v17-green.log
D:\studyAgent\AI Mall\backend\target\commerce-integration-final.log
```

### Final focused verification (after parent approval/marker changes)

From `D:\studyAgent\AI Mall`:

```text
mvn -B -q -f backend/pom.xml -Dtest=AfterSaleFulfillmentMigrationTest,OrderShippingMetadataMigrationTest,OrderSkuAndAgentQuoteTest,SeckillEntitlementTransactionTest,CartConcurrencyTransactionTest,CartSkuBoundaryTransactionTest,AdminOrderShippingValidationTest,OrderLifecycleTransactionTest,OrderLifecycleTest,OrderInputIntegrityTest,AgentOrderActionServiceTest,AgentOrderActionTransactionTest,AgentOrderPriceIntegrityTest,OrderShippingAuthorityTest,AfterSaleServiceTest,AfterSaleTransactionTest test
```

Final session `82282` exited **0**. Surefire XML for exactly these 16 selected classes totals **189 tests, 0 failures, 0 errors, 0 skipped**:

| Selected test class | Tests |
| --- | ---: |
| AfterSaleFulfillmentMigrationTest | 2 |
| OrderShippingMetadataMigrationTest | 1 |
| OrderSkuAndAgentQuoteTest | 7 |
| SeckillEntitlementTransactionTest | 12 |
| CartConcurrencyTransactionTest | 32 |
| CartSkuBoundaryTransactionTest | 9 |
| AdminOrderShippingValidationTest | 5 |
| OrderLifecycleTransactionTest | 25 |
| OrderLifecycleTest | 15 |
| OrderInputIntegrityTest | 21 |
| AgentOrderActionServiceTest (parent-owned) | 16 |
| AgentOrderActionTransactionTest (parent-owned) | 13 |
| AgentOrderPriceIntegrityTest (parent-owned) | 10 |
| OrderShippingAuthorityTest (parent-owned) | 1 |
| AfterSaleServiceTest (parent-owned) | 13 |
| AfterSaleTransactionTest (parent-owned) | 7 |

From `D:\studyAgent\AI Mall\frontend`:

```text
npx vitest run src/views/admin/OrderManageView.spec.ts
npx tsc --noEmit
```

Result: **4 UI tests passed; type check exited 0** (session `76108`). Scoped `git diff --check` passed. S1's earlier 4 deployment checks remain recorded above; no new deployment operation was performed.

**Maven coordination:** the final Java command has completed and the slot was explicitly released to the Spec FAQ worker/parent. No further Maven command will be started by this worker without a new release. Full-suite/build/deployment verification remains parent-coordinated. No reset, commit, real backup, secret access, deployment, container restart, or production migration was performed.
