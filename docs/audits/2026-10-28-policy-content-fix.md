# SPEC-01 policy-content fix — 2026-10-28

## Decision and implementation

**Accepted SPEC-01.** The bundled policy/FAQ and generator contained operational promises contradicted by the current README, after-sales contract and actual AfterSalePolicy/AfterSaleService transitions. Corrected content only; no new payment, approval, exchange or insurance capability was implemented.

- Canonical FAQ answers and policy workflows now distinguish application, explicit human approval, required return receipt, WAITING_REFUND and separately executed simulated refund. Completed refunds carry `refundMode=SIMULATED` and a `SIM-` reference; there is no bank/wallet settlement or guaranteed arrival time.
- Removed timeout automatic approval, cancellation-as-refund and cross-product/SKU price-difference exchange promises. Exchange is the original product/original SKU; an already-received exchange return that cannot be dispatched can be converted by the buyer to a refund request, still requiring operator execution.
- Corrected standalone FAQ answers concerning refusal, missing/wrong goods, delivery disputes and compensation so a direct FAQ answer does not depend on a distant disclaimer. Freight responsibility remains conditional policy information, not a promise of actual reimbursement, insurance, pickup or expedited settlement.
- Preserved seven-day consumer-rights background, product-condition qualifications, quality-problem remedies and the existing consumer-law reference list. Removed unconfigured universal seven-/fifteen-day operational guarantees and hard-coded counting rules; did not substitute a new legal deadline. This is not a legal review or legal advice.
- Generator facts, payment-domain vocabulary and all 15 standalone generated manuals now reflect the demo-operation boundary. All 15 outputs necessarily changed because each includes that shared boundary. Manifest character/chunk metadata was regenerated; deterministic `generatedAt` is 2026-10-28, schema `version` remains 1 (not a persisted KB document version).

**Rejected interpretations:** blanket deletion of all seven-day information; treating demo limits as eliminating lawful consumer rights; inventing replacement legal deadlines; implementing real payments, automatic approval, cross-SKU exchange, insurance or expedited payment channels to match obsolete prose. SPEC-02 FAQ validity/citation gating and SPEC-03–07 application/eval defects remain outside this worker's ownership.

## Red / green evidence

All commands ran from `D:/studyAgent/AI Mall`, offline, using the already-installed Python/pytest. Tests parse the real canonical FAQ format (matching FaqService's multiline/first-answer-wins contract), execute the actual pure generator/writer, scan built and committed policy content, retain conditional-rights coverage, and compare every committed generated resource/manifest with offline regeneration. Text comparison normalizes checkout line endings.

1. Before any policy/generator fix: `python -m pytest backend/scripts/tests/test_policy_content.py -q -p no:cacheprovider --tb=no` → **11 failed, 1 passed**, exit 1. Failures reproduced unsupported exact FAQ replies, generator/derived promises and missing operational/conditional boundaries. Initial line-ending-only failure had already been corrected in the test before this red run.
2. Expanded direct-answer cases were also run red before their fixes: three conditional-rights cases failed before correction; the final six freight/refusal/dispute/compensation cases produced **6 failed, 19 passed**, exit 1 with the combined command below.
3. Final: `python -m pytest backend/scripts/tests/test_policy_content.py backend/scripts/tests/test_kb_dataset.py -q -p no:cacheprovider --tb=short` → **25 passed**, exit 0. One pre-existing installed pytest-asyncio/Python deprecation warning (`asyncio.get_event_loop_policy`); no application/config imports.
4. Bounded `git diff --check` passed. No full application, AI, browser or integration suite was run; these results certify content/generation contracts only, not persisted KB refresh or runtime FAQ citation validity.

Regeneration used `write_dataset` into a new temporary directory, including a temporary eval file, then copied only changed resource files inside the allowed kbseed generated directory. No standard generator CLI was run against the repo because it also writes the out-of-scope eval file. Stats: **15 documents, 287,884 characters, 572 estimated chunks**. No production DB/seed ingestion, live services, model/vector calls, secrets/.env reads, installs, commits or resets.

## Explicit out-of-scope handoffs

1. `D:/studyAgent/AI Mall/eval/dataset/kb_large_rag.jsonl` was **not edited**. Offline comparison found exactly three generator-derived row changes for its owner:

| 1-based row | Document key | Old must_hit | Generator's corrected must_hit |
| --- | --- | --- | --- |
| 3 | payment-refund | 按原支付路径退回; 退款详情 | 模拟退款; SIM- |
| 9 | seven-day-return | 签收当日; 自然日 | 不配置统一七天; 人工核实 |
| 10 | quality-exchange | 十五个自然日内; 免费换货 | 人工审核; 原 SKU |

Until the owning worker updates those rows, the committed eval expectations are stale. No false promise was retained in generator facts solely to satisfy them.

2. Existing persisted documents are skipped by title in `D:/studyAgent/AI Mall/backend/src/main/java/com/aimall/backend/kb/KbService.java` (`ensureSeedPolicy`) and `D:/studyAgent/AI Mall/backend/src/main/java/com/aimall/backend/kb/KbBulkSeedService.java` (`ensureSeeds`). Updating these files or manifest metadata does **not** update already-ingested documents/vectors. An authorized owner must handle document replacement/versioning/re-indexing separately; none was attempted. No Java, migrations (including V15+), deployment, AI app/tests or frontend files were edited.
3. `D:/studyAgent/AI Mall/backend/src/main/java/com/aimall/backend/chat/FaqService.java` caches its bundled seed on first use; deploying rebuilt resources/restarting is separate from this content edit. Its current-document/citation gate is SPEC-02, not fixed here.

Existing intentional after-sales/recovery/latency work was not reverted or edited. The following list is this worker's exact write set, not the whole dirty worktree.

## Exact changed paths

- `D:/studyAgent/AI Mall/backend/scripts/kb_dataset.py`
- `D:/studyAgent/AI Mall/backend/scripts/tests/test_policy_content.py`
- `D:/studyAgent/AI Mall/backend/src/main/resources/kbseed/platform-policies.md`
- `D:/studyAgent/AI Mall/backend/src/main/resources/kbseed/generated/manifest.json`
- `D:/studyAgent/AI Mall/backend/src/main/resources/kbseed/generated/docs/account-security-privacy.md`
- `D:/studyAgent/AI Mall/backend/src/main/resources/kbseed/generated/docs/complaint-mediation.md`
- `D:/studyAgent/AI Mall/backend/src/main/resources/kbseed/generated/docs/crossborder-remote-delivery.md`
- `D:/studyAgent/AI Mall/backend/src/main/resources/kbseed/generated/docs/digital-home-beauty-aftercare.md`
- `D:/studyAgent/AI Mall/backend/src/main/resources/kbseed/generated/docs/food-family-home-aftercare.md`
- `D:/studyAgent/AI Mall/backend/src/main/resources/kbseed/generated/docs/invoice-service.md`
- `D:/studyAgent/AI Mall/backend/src/main/resources/kbseed/generated/docs/membership-promotions.md`
- `D:/studyAgent/AI Mall/backend/src/main/resources/kbseed/generated/docs/order-change-cancel.md`
- `D:/studyAgent/AI Mall/backend/src/main/resources/kbseed/generated/docs/payment-refund.md`
- `D:/studyAgent/AI Mall/backend/src/main/resources/kbseed/generated/docs/platform-account-service.md`
- `D:/studyAgent/AI Mall/backend/src/main/resources/kbseed/generated/docs/quality-exchange.md`
- `D:/studyAgent/AI Mall/backend/src/main/resources/kbseed/generated/docs/seven-day-return.md`
- `D:/studyAgent/AI Mall/backend/src/main/resources/kbseed/generated/docs/special-delivery.md`
- `D:/studyAgent/AI Mall/backend/src/main/resources/kbseed/generated/docs/standard-delivery.md`
- `D:/studyAgent/AI Mall/backend/src/main/resources/kbseed/generated/docs/warranty-repair.md`
- `D:/studyAgent/AI Mall/docs/audits/2026-10-28-policy-content-fix.md`
