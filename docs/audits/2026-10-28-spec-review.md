# SPEC-axis full-tree audit — 2026-10-28

## Decision and provenance

**SPEC result: changes required. Seven evidence-backed findings: two P1 and five P2.** This is a read-only implementation audit, apart from this requested report; no application/test sources were edited. No fix has been applied or claimed.

- Workspace: `D:\studyAgent\AI Mall` (live working tree, not a clean checkout).
- Verified HEAD: `ac4d87015dcba66ea0f7cbd917b1d88eefaf5ed0`.
- `git log -5 --oneline`:
  - `ac4d870 docs: record real-product photo rollout and production acceptance`
  - `804a07c fix: replace demo illustrations with verified official product photos`
  - `5c5a5c4 docs: record production deployment and end-to-end verification`
  - `f47e790 fix: scope platform policy lookups to global rules`
  - `8cc816b fix: serve verified policy excerpts on CPU deployment`
- `git diff HEAD` was captured with explicit `.env` exclusions at `C:\temp\aimall-spec-audit-88a64e805fa342e9b187b70d4c3be5f8\git-diff-HEAD.txt` (4,168 nonempty lines at capture). `git status --short` and source inventory included untracked after-sales/recovery implementations and tests. The diff is provenance, **not** the audit boundary.
- Full-tree source inventory considered 33 AI application Python files, 129 backend Java files, 89 non-spec frontend TS/Vue files, and eight eval Python files under the enumerated roots. These counts are inventory, not a claim that every line was exhaustively reviewed. Existing committed code/resources can fail the current spec; findings are not restricted to recent regressions.
- Concurrent work was preserved. Source locations describe the audit snapshot and must be revalidated before editing.

## Requirement precedence and method

Human intent for functional simulated commerce, truthful promises, and correct roles/states takes precedence, followed by the current README and after-sales contract. Initial design documents supply compatible details only; superseded restrictions such as “no cart/marketing” are not treated as current exclusions.

Primary requirements read:

1. `D:\studyAgent\AI Mall\README.md:5–7,28–43,87,324–329`: backend business authorization; prepare/confirm; current valid evidence; explicit degradation rather than invented policy.
2. `D:\studyAgent\AI Mall\docs\after-sales.md:3–34`: simulated funds, workflow, ownership, paid allocations, inventory, idempotency, evidence, and unsupported promises.
3. `D:\studyAgent\AI Mall\docs\01-产品需求文档-PRD.md:78–103,140–195,278,312–317`: current role definitions, simulated-payment boundary, authorization and order closure.
4. `D:\studyAgent\AI Mall\docs\04-API接口设计文档.md:160–223,321–322,451–465`: merchant ownership and order/API contracts.
5. `D:\studyAgent\AI Mall\docs\05-AI-Agent设计文档.md:128–186,249–279,328–340`: trusted identity, tool authority and product-scoped retrieval, as applicable after newer requirements.
6. Current plans: `D:\studyAgent\AI Mall\docs\superpowers\plans\2026-10-28-after-sales.md`, `D:\studyAgent\AI Mall\docs\superpowers\plans\2026-10-28-chat-recovery.md`, `D:\studyAgent\AI Mall\docs\superpowers\plans\2026-10-28-ai-latency.md`, and `D:\studyAgent\AI Mall\docs\superpowers\plans\2026-10-28-user-hot-content-cache.md`.
7. Eval contract: `D:\studyAgent\AI Mall\eval\README.md:37–53` and `D:\studyAgent\AI Mall\docs\superpowers\specs\2026-08-24-live-agent-eval-design.md:5–26`.

The requested Alibaba/open-code-review-style SPEC separation is applied as requirement → source path → concrete failure → reproduction/test, independently of Standards/style. No external checker was installed or executed; an authoritative Alibaba methodology artifact was not available in the supplied workspace/context, so this report does not assert vendor-tool certification. No code or private data was uploaded externally.

## A. Missing / partial requirements

### SPEC-02 — P2: FAQ fast path has no current-document validity or citation gate

**Requirement:** `D:\studyAgent\AI Mall\README.md:87` says knowledge answers must use current valid documents and citations; lines 327–329 require ACTIVE/current-version checking and degradation when evidence is unavailable.

**Exact source:** `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\chat\ChatService.java:138–152` returns FAQ text and persists SUCCESS before calling AI/RAG. `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\chat\FaqService.java:72–95` reads/caches the bundled classpath seed, not the active KB document/version. The terminal payload at ChatService lines 146–147 has no citations.

**Trigger/consequence:** Disable or replace the platform policy through the KB administration workflow, then ask an exact FAQ such as `退款多久能到账？`. The fast path still serves the bundled answer as SUCCESS, including rules administrators withdrew. Even sanitizing the seed under SPEC-01 would not solve this separate current-version/revocation problem.

**Evidence:** Compiled current FaqService and invoked it without any KB service/database; `商家一直不处理售后怎么办？` returned its bundled promise. The path’s lack of any KB lookup is source-proven. An integrated KB-disable transaction was not executed.

**Reproducing test:** ChatService/FAQ integration test with a disabled seed document and then a newer ACTIVE revision. Assert the old answer cannot be emitted; any shortcut must provide current citation metadata or fall through to retrieval/degradation. Repeat with KB unavailable. This is a missing validity gate, not a request to add new FAQ features.

### SPEC-05 — P2: Mandatory policy lookup drops an already-known product scope

**Requirement:** `D:\studyAgent\AI Mall\docs\05-AI-Agent设计文档.md:260–277` requires contextual lookup and `product_id` filtering to prevent cross-product policy contamination. `D:\studyAgent\AI Mall\README.md:87` requires current applicable evidence rather than invented rules.

**Exact source:** `D:\studyAgent\AI Mall\ai-service\app\agent\nodes.py:303–341`, particularly lines 337–341, schedules the first mandatory KB lookup with only the latest text. It supplies a scope only when text explicitly mentions the platform, in which case it uses global `product_id=-1`; it never resolves a uniquely remembered product for this lookup. `D:\studyAgent\AI Mall\ai-service\app\rag\retrieval.py:81–90,286–293` leaves product filtering off when the ID is absent. `D:\studyAgent\AI Mall\ai-service\app\tools\tools.py:157–176` already has unambiguous product-reference resolution for other tools.

**Trigger/consequence:** Recommend exactly one product A, then ask `这款商品的退货条件是什么？`. The deterministic first policy search is unscoped and contains only a pronoun, so stronger B-specific evidence remains eligible. In extractive mode the next policy step can immediately render those hits, without a model opportunity to repair the scope. The wrong-evidence admission is deterministic; final wording is model/data dependent.

**Executed reproduction:** Executed the unchanged `agent_node` function extracted with Python AST, using a HumanMessage stand-in and `active_entities.last_products=[{id:101,name:...}]`. Output:

```text
kb_search args = {"query":"这款商品的退货条件是什么？"}
```

No `product_id` or contextual product name was supplied; the function returned before any model call.

**Reproducing test:** Two contradictory product policies for A/B plus a global rule; uniquely select A, ask the pronoun follow-up, and assert A/global-only retrieval and citations. Include an ordinal reference and an ambiguous multi-product reference; ambiguity must not silently select another product.

### SPEC-06 — P2: Live eval silently accepts truncated SSE as a completed replay

**Requirement:** `D:\studyAgent\AI Mall\eval\README.md:41–53` and `D:\studyAgent\AI Mall\docs\superpowers\specs\2026-08-24-live-agent-eval-design.md:13–25` promise actual final replies and real tool/latency metrics. Recovery’s explicit terminal-event requirement is also present in `D:\studyAgent\AI Mall\docs\superpowers\plans\2026-10-28-chat-recovery.md`.

**Exact source:** `D:\studyAgent\AI Mall\eval\live_eval.py:52–64` initializes `done={}` and returns it after EOF without requiring a terminal `done`. Lines 88–97 count observed tool names/arguments and lines 131–134 default absent latency/token metadata to zero.

**Trigger/consequence:** A provider/proxy closes an HTTP-200 SSE response after `tool_call` but before `tool_result`/`done`, without an explicit error frame. The runner counts the invocation as a successful tool-name/argument match, records zero latency, and does not flag an incomplete replay. This can turn an interrupted run into apparently perfect tool metrics.

**Executed reproduction:** Replaced only `urllib.request.urlopen` with an in-memory response containing one `product_search(category=PHONE)` tool-call frame and EOF. No network request occurred. Actual LiveClient + evaluate_live output:

```text
result = {tool_calls:[...], tool_results:[], done:{}}
toolCorrectness = 1.0
toolArgumentAccuracy = 1.0
latencyMs = {p50:0,p95:0}
```

**Reproducing test:** HTTP-fixture tests for empty stream, token-only, tool-call-only, and partial final frames must fail/classify the replay as incomplete rather than supply a successful result; a valid terminal `done` remains accepted. Retain documented name/argument metric definitions; do not confuse this finding with a request for semantic answer grading.

## B. Wrong implementation

### SPEC-01 — P1: Live policy/FAQ sources promise explicitly unsupported after-sales behavior

**Requirement:** `D:\studyAgent\AI Mall\docs\after-sales.md:4,18,34` specifies simulated funds only, original-product/SKU exchange only, and explicitly says **“No unconfigured seven-day promise, automatic timeout approval ... or accelerated real-fund refund is advertised.”** New human intent overrides the initial seeded policy text.

**Exact source:** `D:\studyAgent\AI Mall\backend\src\main\resources\kbseed\platform-policies.md:172,175,178,182,281–283` still states automatic approval after 48 hours, cancellation-as-refund, refunds to real payment channels, and channel-specific real-fund timings. Lines 140–141 promise cross-model exchange with price differences. These are active application resources, not archived design prose: `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\kb\KbSeedInitializer.java:17–21` registers the seed, while `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\chat\FaqService.java:30,90–105` extracts its FAQ for direct replies.

**Trigger/consequence:** Ask `商家一直不处理售后怎么办？`; current FaqService returns `商家48小时未处理售后申请，系统会自动同意您的申请...`. Ask `退款多久能到账？`; it advertises original-channel payments and WeChat/Alipay/bank timings. Actual cases remain pending until explicit operator action; no real payment rail exists. Grounding/citation checks cannot make these obsolete source claims true. Current README’s product disclaimers do not cure an explicit operational promise in the chat reply.

**Evidence:** Exact FAQ parser reproduction returned both answers. Current FaqService was also compiled and invoked in a local JVM, reproducing the automatic-approval answer. SHA-256 comparison confirmed the test classpath seed resource matched the current source resource. This is not a hypothetical model hallucination.

**Reproducing test:** Resource/FAQ contract tests for those exact questions must reject timeout auto-approval, real-channel settlement promises and unsupported cross-product exchanges; policy retrieval tests must use the same current lifecycle contract. Audit generated KB documents/generator inputs too so regeneration cannot resurrect excluded promises. Do not implement those obsolete promises as new features.

### SPEC-03 — P1: Settled pre-shipment partial refunds leave refunded units in fulfillable order lines

**Requirement:** Current human intent requires functional refund/fulfillment state correctness. `D:\studyAgent\AI Mall\docs\after-sales.md:22–27` binds original quantities, stock restoration and refund settlement; `D:\studyAgent\AI Mall\docs\superpowers\plans\2026-10-28-after-sales.md:16,24,27` promises original-stock consistency and authoritative order projections. A unit whose original reservation was restored cannot still be represented as an ordinary reserved unit awaiting dispatch.

**Exact source:** `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\aftersale\AfterSaleService.java:189–204` restores a refunded unit’s stock at line 194 but only changes the parent order when **all** quantities were refunded. `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\mapper\OrderInfoMapper.java:25–28` excludes REFUNDED cases from dispatch blockers. `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\order\OrderService.java:195–209` then ships the original order without a residual fulfillable-quantity calculation. `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\order\AdminOrderController.java:54` returns original item quantities to fulfillment UI.

**Trigger/consequence:** PAID order has quantity 2, paid ¥80, current stock 5. Refund one unit for ¥40 before shipment and settle it. Stock becomes 6, parent remains PAID. Dispatch then succeeds with the original two-unit order line, even though one unit is refunded and its inventory is already available for resale. Admin fulfillment sees `×2`; there is no server-provided remaining dispatch quantity. This is inconsistent allocation/fulfillment, not a request to overwrite historical purchased quantity.

**Executed reproduction:** Recompiled current AfterSaleService/Policy, OrderService and relevant mappers with the existing H2 transaction fixture into a temporary directory. Applied → approved → refunded one unit, then called ship. Output:

```text
SPEC_PROBE_PARTIAL_SHIPMENT={STATUS=SHIPPED},items=2,stock=6,refunded=40.00
```

**Reproducing test:** Extend the H2 transaction fixture: two units (and separately two different items), settle one unshipped refund, then dispatch. Assert fulfilled quantities exclude settled unshipped refunds or dispatch is rejected until a valid residual fulfillment is represented. Verify the stock is not available to both the original shipment and a second buyer. Preserve historical purchase/payment records and legitimate post-delivery compensation semantics.

### SPEC-04 — P2: Idempotency comparison ignores an explicit-to-default refund-amount change

**Requirement:** `D:\studyAgent\AI Mall\docs\after-sales.md:23`: **“Idempotency keys cannot silently accept a changed payload.”**

**Exact source:** `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\aftersale\AfterSaleService.java:99–106`, particularly line 104, compares the amount only if the replayed `refundAmount` is non-null. Lines 110–112 define null as the newly calculated maximum for a new application.

**Trigger/consequence:** With a ¥40 cap, submit a ¥10 request under requestId K. Replay K with identical other fields but omit/set null refundAmount (which would mean the ¥40 default). The server silently accepts the changed payload, returns the existing ¥10 case, and does not tell the client its changed amount was rejected. The inverse/equivalent-normalization question should be resolved consistently, but this specific materially different default must not be silently accepted.

**Executed reproduction:** In the isolated current-source H2 fixture, called apply twice with that exact change:

```text
SPEC_PROBE_CHANGED_AMOUNT_ACCEPTED=true,requested=10.00
```

**Reproducing test:** Explicit smaller amount → null/omitted under the same key must conflict. Identical explicit amount must return the original case; null→null replay must remain idempotent after eligibility changes, without recalculating away the original request. Keep amount normalization consistent between web and AI requests.

### SPEC-07 — P2: Buyer and blank-admin shipping paths persist fabricated carrier events

**Requirement:** `D:\studyAgent\AI Mall\docs\superpowers\plans\2026-10-28-after-sales.md:18` says **“No invented delivery events”** and line 27 says **“real logistics only.”** Current human intent requires role/state correctness; `D:\studyAgent\AI Mall\docs\01-产品需求文档-PRD.md:312` assigns shipment to the administrator. Simulated funds do not authorize presenting invented named-carrier tracking as real logistics.

**Exact source:** `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\order\OrderController.java:74–80` exposes buyer-owned `/simulate-ship`, manufactures an SF number, and sets carrier to 顺丰速运. `D:\studyAgent\AI Mall\backend\src\main\java\com\aimall\backend\order\AdminOrderController.java:59–65` manufactures an SF number for absent/blank tracking. `D:\studyAgent\AI Mall\frontend\src\views\admin\OrderManageView.vue:54–60` still advertises “留空自动生成”. The backend's ordinary authenticated-order route rules do not restrict the buyer helper to an operator. `D:\studyAgent\AI Mall\frontend\src\views\OrderDetailView.vue:21–22,185–195` explicitly labels its initiation as simulated; this is an intentional legacy demonstration path, not a hidden UI action. The mismatch is with the newer no-invented-events contract and the unmarked normal carrier/order record, not an assertion that every UI label conceals simulation.

**Trigger/consequence:** An authenticated buyer POSTs their PAID order’s `/simulate-ship`; or an admin submits `{}` to `/ship`. The actual business order becomes SHIPPED and buyer/API projections expose a fabricated named-carrier tracking value without a persisted simulation marker. Removing or relabeling only the buyer button would not correct the callable mutation or its persisted tracking representation.

**Executed reproduction:** Compiled current controllers and called them against the isolated transaction fixture (one fresh fixture per scenario):

```text
SPEC_PROBE_BUYER_SHIPPING={STATUS=SHIPPED, LOGISTICS_NO=SF3169480111, DELIVERY_COMPANY=顺丰速运}
SPEC_PROBE_ADMIN_EMPTY_TRACKING={STATUS=SHIPPED, LOGISTICS_NO=SF1793169480684, DELIVERY_COMPANY=null}
```

These values are generated test values, not actual shipments.

**Reproducing test:** Controller/security tests must prevent buyer-originated operator fulfillment mutations; admin shipment with missing/blank tracking must not manufacture an apparently real carrier record. If a deliberate isolated demonstration mode remains desired, it needs an explicit product decision and clearly distinct simulated representation, not silent live-order mutation. Keep buyer confirmation-of-receipt separate from dispatch authority.

## C. Scope creep

**No defensible independent scope-creep finding.** Cart, promotion, merchant and other capabilities exist beyond the initial minimal PRD, but current README/plans explicitly describe their presence; treating them as unauthorized additions would ignore precedence. The contradictory policy promises above are wrong behavior, not a recommendation to implement extra payment, timeout, insurance, shipping or exchange capabilities.

## Verification and evidence limits

Executed, bounded checks only:

1. `python -m pytest eval/tests/test_live_eval.py -q -p no:cacheprovider` from `D:\studyAgent\AI Mall`: **3 passed, one existing pytest-asyncio/Python deprecation warning**. This proves only those existing tests pass; they do not cover SPEC-06.
2. Python standard-library/AST probes of the current agent scheduling function, current FAQ resource parser, and actual eval LiveClient/evaluator. Application configuration imports were deliberately avoided because `D:\studyAgent\AI Mall\ai-service\app\config.py:2–13` loads dotenv on import. No secrets or `.env` files were read.
3. Narrow Java recompilation into `C:\temp\aimall-spec-audit-88a64e805fa342e9b187b70d4c3be5f8` using already-installed project dependencies, followed by the existing H2 transaction fixture with synthetic identities/orders only. This did not start Spring Boot, load production configuration, call a provider, use live Redis/MySQL, or change project sources. Re-run the preserved probes with:

```powershell
java '@C:\temp\aimall-spec-audit-88a64e805fa342e9b187b70d4c3be5f8\run.args'
java '@C:\temp\aimall-spec-audit-88a64e805fa342e9b187b70d4c3be5f8\shipping-run.args'
```

The two Java files and compile argument files in that temporary directory preserve the reproductions. Production behavior under MySQL repeatable-read, real browser integration and service failures was source-traced, not live-benchmarked. No full-suite run, deployment, migration, reset, commit or downloaded checker execution occurred.

## Coverage / exclusions

| Area | Coverage and boundary |
| --- | --- |
| AI retrieval/grounding | Deep-read agent routing, mandatory lookup, tool context, request policy, RRF/answerability, citations, vector current-version checks, backend KB callbacks, seeded knowledge and FAQ bypass. Reviewed retrieval/grounding tests. Product-scope defect is SPEC-05; ordinary vector current-version filtering exists and is not reported missing. No live Milvus, reranker or model quality run. |
| Tool identity / approval | Traced injected user/conversation identity through Python tools/client, internal request DTOs, owned-conversation/action validation, buyer confirmation and the shared after-sale transaction. Existing prepare-only and backend ownership guards are present; no claim that the model itself can confirm arbitrary actions. No forged credential testing. |
| Streaming / recovery | Read current ChatService, ChatStreamRecovery, SseEmitterManager, AI SSE/state/regeneration, browser SSE consumer/store recovery, plus current recovery tests/plan. Reconnect replays Redis events rather than reinvoking tools; regeneration validates latest FAILED reply and guards recorded business tools. No new independent runtime recovery finding beyond the eval terminal-event defect; no live Redis/crash/replica test and no universal recovery guarantee. |
| Refund / returns / exchange | Deep-read all new after-sale service/policy/controller/evidence files, V15, existing order/action/controller/mapper integration, current H2 tests, UI permissions and amount/status types/projections. Checked explicit receipt prerequisites, same-SKU exchange, conversion, stock/coupon allocation, merchant mapping and private evidence authorization. H2 probes cover the specific defects; they do not certify the entire new workflow. |
| Remaining tree | Full-root inventory and targeted contract/entry-point scans across auth/RBAC, merchant/product, cart/promotion, workbench/handoff, order projections, frontend routing/APIs and deployment volume integration. These checks informed cross-layer boundaries, not an exhaustive Standards/security/performance certification of all 259 enumerated source files. |
| Explicit exclusions | Parent owns frontend request interceptor / global type-check failure; not duplicated here. No `.env`, credentials, deployment-private contents, live user records or private uploads were opened. No production access, external source uploads or downloaded-code execution. No frontend full suite/build, full backend/AI suites, actual payment/carrier exercise or legal-policy review. Visual assets, dependency trees, worktrees and generated/build artifacts were excluded from semantic full-source review; existing build outputs were used only as dependencies for isolated probes. |

**Next step:** Parent may assign bounded, disjoint fix ownership against these finding IDs. Keep this report’s observed failures separate from existing tests that happen to pass; recheck concurrent source lines and reproduce before applying a fix.

## Assigned SPEC fix status — 2026-10-28

This status update covers only this worker's assigned SPEC-02/05/06 scope and the subsequently authorized stale eval labels; the original audit evidence above is retained as a historical snapshot.

- **SPEC-02: FIXED in source; focused Java red/green complete.** After the parent explicitly granted the exclusive Java slot, re-read `D:/studyAgent/AI Mall/backend/src/main/java/com/aimall/backend/chat/FaqService.java` and the prepared FAQ tests. The red run reproduced the bypass: **7 tests, 5 failures, 0 errors**; all four routing regressions observed no AI client call because the classpath answer returned first. Retired only the bundled matcher/cache in FaqService, retaining its `match` interface and Spring bean so ChatService always continues into the existing current-evidence/citation pipeline. No new KB API or ChatService/recovery/latency implementation change was needed. Focused green: **31 tests, 0 failures/errors/skips**, including all seven FAQ regressions plus adjacent chat/recovery suites. Existing current-chunk/citation validation remains in the AI pipeline; Java consumer tests mock that boundary and do not claim a live KB-disable/refresh integration test. No live ingestion or persisted-document refresh was performed. **Maven slot explicitly yielded to the parent after green; no Java process remains running.**
- **SPEC-05: FIXED in source; focused offline green.** The first mandatory policy lookup now uses an unambiguous remembered product, ordinal or exact remembered name; explicit platform questions and questions without a selected product use global-only scope. Ambiguous/out-of-range/conflicting references ask for clarification without unscoped retrieval. SSE emits only the deterministic clarification (empty citations), not an evidence-free policy claim; all other policy answers retain citation validation. Existing latency/recovery edits were preserved.
  - Initial red: new product-scope file **10 failed, 1 passed**, including actual other-product text in the extractive answer.
  - Additional red: full graph/SSE clarification regression **1 failed** because the citation gate replaced the clarification; conflicting ordinal/name regression **1 failed, 4 passed** before its narrow fix.
- **SPEC-06: FIXED in source; focused offline green.** LiveClient requires an explicit successful `done`; empty/token-only/tool-only/truncated streams and timed-out `done` events raise. Provider errors and malformed JSON propagate rather than becoming successful metrics. Valid explicit completion at EOF preserves metadata.
  - Red: new live-completion regressions **6 failed, 3 passed**. After the completion guard, the live-completion and existing live-eval targets passed.
- **Authorized eval-label follow-up: FIXED.** The actual file is `D:/studyAgent/AI Mall/eval/dataset/kb_large_rag.jsonl` (the mentioned `eval/data/rag_eval.jsonl` does not exist here). Changed only `must_hit` in rows 3, 9 and 10 to `["模拟退款", "SIM-"]`, `["不配置统一七天", "人工核实"]`, and `["人工审核", "原 SKU"]`. New tests assert the literal contract, corresponding current resource text, and pure-generator alignment. Red **4 failed**; final targets green. Policy resources/generator and live ingestion were not changed by this worker.

### Exact files edited by this worker

1. `D:/studyAgent/AI Mall/ai-service/app/agent/nodes.py` — mandatory policy scope/clarification only; existing unrelated uncommitted changes retained.
2. `D:/studyAgent/AI Mall/ai-service/app/api/chat.py` — deterministic clarification finalization only; existing unrelated uncommitted changes retained.
3. `D:/studyAgent/AI Mall/ai-service/tests/test_policy_product_scope.py` — new scope, real retrieval/extractive-answer and graph/SSE regressions.
4. `D:/studyAgent/AI Mall/eval/live_eval.py` — successful-terminal guard and timeout rejection.
5. `D:/studyAgent/AI Mall/eval/tests/test_live_completion.py` — new offline HTTP-boundary and metric regressions.
6. `D:/studyAgent/AI Mall/eval/tests/test_policy_expectations.py` — new corrected-label/resource/generator regression assertions.
7. `D:/studyAgent/AI Mall/eval/dataset/kb_large_rag.jsonl` — three label-only row changes.
8. `D:/studyAgent/AI Mall/backend/src/main/java/com/aimall/backend/chat/FaqService.java` — retired unverified bundled FAQ/cache shortcut; caller-compatible interface retained.
9. `D:/studyAgent/AI Mall/backend/src/test/java/com/aimall/backend/chat/FaqServiceTest.java` — updated exact-FAQ expectation for current-evidence routing; RED reproduced, GREEN verified.
10. `D:/studyAgent/AI Mall/backend/src/test/java/com/aimall/backend/chat/FaqCurrentEvidenceRoutingTest.java` — new focused consumer regressions; RED reproduced, GREEN verified.
11. `D:/studyAgent/AI Mall/docs/audits/2026-10-28-spec-review.md` — this findings-status section only.

### Final focused verification

Both final commands ran from `D:/studyAgent/AI Mall/ai-service` using the parent's unchanged ignored safe runner, which disables dotenv/credentials and disk checkpoints and blocks real external transports. External boundaries were mocked; in-memory graph/checkpoints and pure-generator/resource reads only.

```powershell
python "D:/studyAgent/AI Mall/.playwright-cli/open-review-offline-pytest.py" -q tests/test_policy_product_scope.py tests/test_policy_grounding.py tests/test_chat_rag_citations.py tests/test_kb_search_tool.py tests/test_rag_retrieval.py tests/test_vectorstore_current_chunks.py tests/test_retrieval_regressions.py tests/test_pipeline_latency.py tests/test_chat_regeneration.py tests/test_context_memory.py --disable-warnings
# 131 passed, 811 dependency/deprecation warnings, 3.79s; exit 0.

python "D:/studyAgent/AI Mall/.playwright-cli/open-review-offline-pytest.py" -q ../eval/tests/test_live_completion.py ../eval/tests/test_live_eval.py ../eval/tests/test_policy_expectations.py --disable-warnings
# 16 passed, 1 dependency/deprecation warning, 0.06s; exit 0.
```

Earlier red/focused eval commands used `python -m pytest` on the listed eval-only files with `-p no:cacheprovider`; those modules import only pure code, all `urlopen` calls are mocked, and no application settings/dotenv loader is imported. No errors were swallowed to achieve green. Bounded `git diff --check` passed. No full suite, credentials/`.env` reads, real model/backend/network calls, KB ingestion, deployment, reset or commit was used. At this earlier Python checkpoint SPEC-02 was still awaiting the Java slot; the subsequently authorized FAQ red/green window and source-fixed status are recorded below. Parent full-matrix review/integration remains necessary.


### Scheduling checkpoint — Java slot still parent-owned

Preserved all source fixes and pending FAQ tests. No Maven/Java invocation. Fresh guarded Python checks on the concurrent tree: `tests/test_policy_product_scope.py tests/test_policy_grounding.py tests/test_chat_rag_citations.py tests/test_vectorstore_current_chunks.py` → **52 passed, 379 warnings, 1.14s**; the same three eval targets above → **16 passed, 1 warning, 0.07s**. Both used the unchanged safe runner with `-q --disable-warnings` from the AI-service directory. These narrower fresh checks supplement, not replace, the prior 131-test focused run. SPEC-02 remains pending its serialized red/green window; SPEC-05/06 and eval-label edits are ready for parent review/integration.


### SPEC-02 exclusive Java window — completed and yielded

The previous scheduling checkpoints are historical: the parent subsequently granted this worker the exclusive slot after Standards yielded. Both commands ran offline from `D:/studyAgent/AI Mall`, using unit fixtures and mocked AI/Redis/emitter boundaries, without starting Spring Boot or using live services.

```powershell
mvn -o -q -f backend/pom.xml "-Dtest=FaqServiceTest,FaqCurrentEvidenceRoutingTest" test
# RED: 7 tests, 5 failures, 0 errors; exit 1. Bundled answers bypassed the AI client.

# Then changed only FaqService.java production source.
mvn -o -q -f backend/pom.xml "-Dtest=FaqServiceTest,FaqCurrentEvidenceRoutingTest,ChatServiceRecoveryTest,ChatServiceHandoffTest,ChatStreamRecoveryTest,SseEmitterManagerRecoveryTest" test
# GREEN: 31 tests, 0 failures/errors/skips; exit 0.
```

Verified fresh Surefire suite headers: FaqServiceTest 3, FaqCurrentEvidenceRoutingTest 4, ChatServiceRecoveryTest 8, ChatServiceHandoffTest 4, ChatStreamRecoveryTest 11, SseEmitterManagerRecoveryTest 1. Expected ChatService warning logs came from deliberately injected upstream errors. Bounded `git diff --check` passed. No other production Java file, KB resource, frontend, deployment, migration or credential file was changed by this worker. No full backend suite was run by this worker. Parent full-matrix integration remains pending; the slot is free and all assigned SPEC-02/05/06 source fixes plus the authorized eval-label follow-up are ready for parent integration. Existing live KB content refresh remains a separately authorized operator/deployment action.
