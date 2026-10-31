# Semantic request routing implementation plan

**Goal:** Replace keyword-led business decisions with semantic intent/action understanding while retaining transaction safety.
**Spec:** docs/superpowers/specs/2026-10-31-semantic-request-routing.md
**Architecture:** One request-decision module owns schema, embedding-example classification and safe abstention; the existing router contextualizes and validates model fallback. Agent execution consumes the decision instead of rediscovering intent from words.
**Stack:** Existing Python/LangGraph/LangChain, existing embedding/model adapters; no new dependencies or vector indexes.

### 1. Decision boundary and semantic matching
Files: app/agent/request_decision.py (new), app/config.py, tests/test_semantic_routing.py (new).
- [ ] Add red schema/score/margin/vector-validation/cache/provider failure cases.
- [ ] Implement controlled decisions and in-process example-vector cache with bounded initialization/query work.
- [ ] Validate on held-out real embedding questions before enabling production routing.

### 2. Contextual understanding and execution
Files: app/agent/routing.py, nodes.py, prompts.py, state.py, app/api/chat.py, clients/llm.py, request_policy.py; focused existing tests.
- [ ] Add red unseen-paraphrase, multi-turn, explicit-goal, malformed planner, complaint distinction and per-turn reset tests.
- [ ] Remove business-keyword fast paths and word-based clarification. Return/consume one validated decision including next step and missing information.
- [ ] Preserve authorization, evidence and streaming boundaries; ensure real legacy intent token limits reach the HTTP wire.

### 3. Regression and actual-runtime acceptance
Files: focused tests, existing routing/knowledge tests, QA report and deployment configuration documentation.
- [ ] Update obsolete tests to assert the new semantic contract rather than that business phrases never invoke a classifier.
- [ ] Run full AI and evaluation/hygiene suites, inspect diff and obtain a bounded correctness review.
- [ ] Run real held-out semantic/contextual scenarios. Deploy AI only after acceptance; verify exact screenshots and unseen phrasing through HTTP SSE, preservation and health.
- [ ] Push code and measured QA evidence; do not claim universal language coverage or instant CPU inference.

## Development evidence

- Red baseline: five unseen purchase complaints, a contextual known-goal continuation, provider failure and stale per-turn state all reproduced the old decision problem.
- Actual embeddings: two separate 20/21-question development sets exposed both useful paraphrase similarity and wrong nearest neighbours (especially human negation/identity and generic shipping versus a specific order). Keep absolute-score and margin abstention plus authorization checks; production thresholds are model-specific, not vector probabilities.
- The 1.5B model did not reliably fill three planner fields. A compact one-card response was substantially more reliable; the application expands the card into the validated typed decision.
- Rejected experiment: a second generic goal-check call sometimes replaced appropriate clarification with an unsolicited order flow. It is not part of the implementation. Explicit goals are instead handled by the semantic card and contextual decision contract.
- Independent review found purchase-selection protection overwrote a legitimate missing-product clarification; reproduced and restricted the downgrade to executable purchase decisions. Also isolated the synthetic-example cache task from request identity context.

## Original 1.5B checkpoint: not released

The current configured `qwen2.5:1.5b` still fails actual multi-turn semantic acceptance (for example, an established return request followed only by a reason is sometimes classified as a new policy inquiry). Typed-card output improved schema reliability but did not remove that semantic error. Alternative relation-only prompting and role-preserving message experiments also failed to meet acceptance; neither was adopted. Raw contextual vectors did not provide sufficient evidence to justify overriding the confirmed goal automatically. Do not lower thresholds or insert phrase-specific business rules to conceal these failures.

Production remains on the verified previous release; no semantic-routing code has been pushed or deployed. The server inventory contains only `qwen2.5:0.5b` and `qwen2.5:1.5b`. The user has now explicitly approved provisioning/evaluating a stronger local intent model, keeping the existing answer generator, embeddings and business data. Quality requirements remain unchanged. Source changes and diagnostic records are preserved.

Final local checkpoint before model-provisioning decision: **653 AI-service tests passed**, **33 evaluation/hygiene tests passed**; `git diff --check` clean. These are software-contract regressions, not evidence that the actual 1.5B model passed semantic acceptance. Application source and diagnostics remain local/unreleased.

## Approved next phase: isolated stronger intent model
- Server recheck: Ollama 0.40.1; 4 CPUs, about 12.9 GiB available RAM, 28 GiB free disk; all nine production services healthy and source clean.
- Candidate `qwen2.5:7b` downloaded into a dedicated named volume and isolated evaluation container (7 GiB RAM / 2 CPU limit); no public port, no business-data mount, no production model replacement.
- Red/green endpoint tests verify classification and query rewriting use the optional intent provider while generation remains unchanged; native startup warmup targets each provider separately.
- Re-run actual semantic pipeline matrix with frozen examples/prompt and a stronger model before changing prompts or accepting a release.

## Stronger-model evaluation findings
- `qwen2.5:7b` did not meet the fixed 32-case acceptance set: one cold-start timeout and two eligibility questions misclassified. `qwen3:8b` with thinking disabled still misclassified an eligibility inquiry in the diagnostic smoke test. Neither candidate is released.
- Instruction-only `qwen3:4b-instruct` correctly classified all four diagnostic failures, without prompt/example changes, and passed the original 32 scenarios in the expanded run.
- Expanded 45-case run at the previously proposed 0.70 similarity threshold scored 44/45. The failure was an embedding false positive (generic missing-part complaint incorrectly treated as an already-established handling goal), not model output. Restore the conservative 0.78 absolute threshold; keep the 0.06 distinct-decision margin and abstention. Raising the threshold trades extra model calls for fewer unsafe assumptions; cosine scores are not calibrated probabilities.
- Dedicated-provider review found that one failed warmup could skip generation warmup. Red/green regressions cover HTTP failure and actual per-job timeout; independent bounded preload jobs now preserve generation warmup. Readiness also checks dedicated intent reachability and installed model.
- Fresh local verification after integration: 663 AI tests; 33 evaluation/hygiene tests. These remain software-contract evidence, separate from actual-model and HTTP checks.

## Qualified candidate checkpoint
The isolated `qwen3:4b-instruct` rerun at cosine 0.78 / margin 0.06 passed **45/45** real semantic/controller/tool-planning scenarios, with no changes to prompt or examples. Model ID `0edcdef34593`; 2.5 GB weights; about 3.59 GiB resident memory. Scenario times 0.06–19.53 s (median 3.82 s, includes prior-focus construction, not full HTTP). Production cutover and actual SSE checks remain required. See `docs/qa/2026-10-31-semantic-routing.md`.
