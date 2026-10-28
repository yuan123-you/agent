# OpenCodeReview-informed AI Mall review and repairs — 2026-10-28

## Result and provenance

Completed this bounded **full-tree** review and repair iteration, not merely a diff review. The initial selection manifest contains 508 source/config entries; the final manifest contains 530 entries plus 15 separately regenerated/validated policy documents. Selection is **not** a claim that every line, runtime path or dependency has been formally proved safe.

- Reference: Alibaba `open-code-review`, pinned commit `375f64cd6f67a48a135da83cfcf59c52669a09cb`.
- Project baseline: `ac4d87015dcba66ea0f7cbd917b1d88eefaf5ed0` **plus** the live existing uncommitted/untracked work. Current HEAD: `ac4d87015dcba66ea0f7cbd917b1d88eefaf5ed0`. No resets, branch switches, commits, pushes or deployments were performed.
- Upstream study covers orchestration, full scan vs diff vs delegation, layered rules, context retrieval, location verification, conservative candidate filtering, coverage limits and provider/session/telemetry boundaries. See `D:/studyAgent/AI Mall/docs/audits/2026-10-28-open-code-review-reference.md` (64 pinned source-range references).
- The upstream installer/CLI and its provider runtime were **not** executed. No project source was sent to an additional review provider. No secrets, `.env` files, live user DB or production evidence were read or modified for review.

## Standards

The original Standards report retains its initial hypotheses and subsequent counterevidence/status, rather than rewriting history: `D:/studyAgent/AI Mall/docs/audits/2026-10-28-standards-review.md`.

| ID | Initial severity | Verified disposition / repair | Primary evidence |
|---|---|---|---|
| S1 | P1 | Fixed production private-evidence named-volume mount; frontend cannot serve that volume. No real evidence copy or deployment claimed. | `deploy/test_production.py`; production Compose persistence test |
| S2 | P1 | SKU-backed products now require an explicit valid variant; null/zero/negative IDs cannot silently use aggregate stock. True no-SKU products remain supported. | `OrderSkuAndAgentQuoteTest`, SKU transaction suites |
| S3 | P2 hypothesis | **Wrong-order consequence not reproduced**: the real DB unique action/order constraint prevented cross-action rebinding. Scoped the cache key to action identity as a lower-severity robustness improvement; do not count this as a demonstrated wrong-order exploit. | Two new real H2 action tests; `uk_agent_action_order`; after-commit cache tests |
| S4 | P2 | Effective promotion quote is persisted in the prepared action. Current quote and final created total must equal the reviewed amount, or error 2015 rolls back/refuses the order and requires renewed approval. | Agent quote/price tests + H2 stale-price test |
| S5 | P2 | Per-buyer campaign quota is serialized and cumulative across requests and duplicate checkout lines. Pending orders reserve quota; unpaid cancellation releases it; paid/refunded purchases retain it (explicit conservative rule). | `SeckillEntitlementTransactionTest` |
| S6 | P2 | Explicit checkout consumes only purchased cart units, retaining unmatched/unpurchased units and ownership/SKU/quantity CAS + rollback. | Cart H2 concurrency/SKU tests; updated mock contract |
| S7 | P2 | Persist pre-shipment fulfillment reductions in V16; retain original purchased quantities and expose authoritative `dispatchableQuantity` to admin dispatch. Block zero-unit shipments. | Fulfillment/migration/partial-refund transaction tests |

### Additional frontend Standards repairs

| ID | Severity | Reproduced failure and repair |
|---|---|---|
| F1 | P2 | The image-URL walker converted Blob/ArrayBuffer values to empty objects. Limit traversal to plain JSON records and preserve binary identity, restoring private evidence downloads. |
| F2 | P2 | The response interceptor violated AxiosResponse's type/runtime contract and failed the TypeScript gate. Keep the internal response intact and unwrap `.data` at the typed public facade for every HTTP verb/upload. |
| F3 | P1 | Delayed refresh/401 replay/private responses could cross a login/logout boundary or erase a newer session. Bind requests/replays to opaque session markers, suppress stale personal responses, preserve legitimate same-session peer refreshes (including refresh failure), and keep refresh credentials out of auxiliary session/error metadata. Only reviewed shared catalog cache routes can finish across a session change; per-user coupon state cannot. |
| F4 | P2 | Malformed persisted user JSON/shape crashed startup or retained unusable credentials. Validate/cache-recover to a signed-out state; retain valid accounts and optional profile data. |
| F5 | P2 | An older asynchronous logout's `finally` cleared a newer login. Only complete local logout for the session that initiated it; a peer access-token refresh in that same session does not defeat intended logout. |

Evidence: `D:/studyAgent/AI Mall/frontend/src/api/request.spec.ts`, `D:/studyAgent/AI Mall/frontend/src/api/hotContent.spec.ts`, `D:/studyAgent/AI Mall/frontend/src/stores/auth.session.spec.ts`. All were verified through focused and full frontend tests, not type casts that mask errors.

## Spec

The independent Spec report and exact source/test mapping are retained at `D:/studyAgent/AI Mall/docs/audits/2026-10-28-spec-review.md`.

| ID | Severity | Verified disposition / repair |
|---|---|---|
| SPEC-01 | P1 | Corrected canonical policy/FAQ resources, generator facts and all 15 derived documents: explicit review, simulated refunds, original-product/original-SKU exchanges, no automatic approval/real-channel/insurance promises. Legitimate conditional consumer-rights information was not blanket-erased. Existing live ingestion is a separate operator action. |
| SPEC-02 | P2 | Retired the unchecked bundled FAQ answer/cache shortcut while retaining caller compatibility; business questions proceed through the existing current-evidence/RAG validation path, with no unsafe bundled fallback on failure. |
| SPEC-03 | P1 | Same underlying partial-refund fulfillment defect as Standards S7; fixed once and verified on both axes. Do **not** add the two axis counts as separate vulnerabilities. |
| SPEC-04 | P2 | Persist a normalized original-request fingerprint in the immutable APPLY event. Explicit amount vs default-maximum semantics cannot silently change on replay; equivalent decimal formatting works and default retries do not requote changed eligibility. Legacy rows without a fingerprint fail closed for ambiguous omitted-amount replays. |
| SPEC-05 | P2 | Carry an unambiguously selected product into mandatory policy retrieval; ambiguous product references trigger clarification, not a policy for a different item. |
| SPEC-06 | P2 | Live evaluation requires an explicit successful SSE `done`. Truncation, provider errors, malformed events and timed-out completion cannot yield successful tool/latency scores. Updated three stale policy expectation rows to the current operational contract. |
| SPEC-07 | P2 | Buyer dispatch endpoint now fails closed and the buyer UI no longer offers it. Admin dispatch requires entered tracking, never fabricates SF numbers, and validates 100/80 tracking/carrier bounds; V17 widens the stored columns without editing published migrations. |

### Additional counterevidence

The image Service Worker was not labelled a private-evidence cache bypass: its fetch handler is restricted to image destinations, excludes Authorization/range/cache-bypass requests, and respects private/no-store response policies. Private evidence uses authenticated XHR/Blob reads. These guards were inspected at `D:/studyAgent/AI Mall/frontend/public/image-cache-sw.js`; no unnecessary worker rewrite was made.

## Final verification

| Layer | Actual result |
|---|---|
| Backend | **773 tests passed** across 79 canonical Surefire suites; 0 failures, 0 errors; Maven package passed |
| Frontend | **473 tests passed**; `tsc --noEmit` passed; Vite production build passed |
| AI service | **449 tests passed** with dotenv/model credentials/disk checkpoints disabled and live HTTP/external DNS blocked; dependency deprecation warnings remain |
| Eval / data / hygiene / deployment contracts | **232 tests passed** under the offline guard |

- Full results: `D:/studyAgent/AI Mall/docs/audits/2026-10-28-open-code-review-verification.json`.
- Current-source fingerprints: `D:/studyAgent/AI Mall/docs/audits/2026-10-28-audit-final-manifest.json`.
- Historical `*-p1-red.xml` copies in `backend/target/surefire-reports` are preserved but excluded from canonical final counts. Expected error-handler logs are not test failures.
- The first full backend integration run exposed two stale mock tests that explicitly expected buying two units to delete all five. They now assert the remaining three while retaining lock/order/CAS/rollback verification; the real H2 partial-checkout regressions also pass. No production exception was swallowed to force green.

Reproducible command groups: backend `mvn -q -f backend/pom.xml test` and package; frontend local Vitest, `npx tsc --noEmit`, `npm run build`; AI and deterministic tooling pytest using the ignored local offline guard `D:/studyAgent/AI Mall/.playwright-cli/open-review-offline-pytest.py`. This guard allows mock/ASGI transports and loopback event-loop socketpairs, not real model/backend HTTP requests; it is an audit harness, not an application change.

## Coverage and limits

- Human/semantic focus: backend authorization/ownership, atomic orders/inventory/quotas, explicit AI approval/amounts, refunds/returns/exchanges, private media, FAQ/RAG scope/evidence, SSE completion/evaluation, frontend transport/cache/authentication, migrations and production persistence.
- Remaining selected source was covered through build, unit/transaction, generator and configuration contracts as applicable; this is not a line-by-line certification of every selected file.
- Excluded from manual source selection: credentials/private deployment data, vendor/build/cache/lockfiles, media payloads and generated catalog bodies. Generated KB policy documents were separately regenerated and checked against their source of truth.
- No real payment/carrier processing, live DB migration/KB ingestion/container recreation, penetration/load test, dependency-advisory scan or real-model semantic-quality certification was performed. Existing/concurrent work was preserved; manifest changes do not establish authorship of every dirty file.

## Required operational follow-up — not performed by this source audit

1. Before production backend replacement, back up/copy any evidence still in the old container layer into the new private named volume. Adding an empty mount does not recover existing files.
2. Publish the new build through the normal controlled process and apply additive V16/V17 migrations (and confirm the prior V15 has been applied). No published migration was edited.
3. Replace/version/disable outdated **already-ingested** policy documents and rebuild their indexes through the authorized KB workflow. Resource/manifest edits and restart alone do not replace existing title-matched KB documents.
4. Transactions remain **simulated**. Validate real-environment compatibility and real-model RAG behavior separately before production claims; offline tests are not proof of live service quality or absence of all vulnerabilities.

**Axis summary:** Standards: seven original candidates (six confirmed repairs, one downgraded with counterevidence and robustness correction), plus five frontend defects; the highest confirmed Standards risks concerned SKU inventory and session isolation. Spec: seven findings repaired in source/resources (one shares Standards S7's repair); the highest Spec risks concerned unsupported operational promises and partial-refund fulfillment.
