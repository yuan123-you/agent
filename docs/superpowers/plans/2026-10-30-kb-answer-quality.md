# Knowledge-answer quality implementation plan

**Goal:** Answer customer questions from verified knowledge without dumping documents, bypassing citations, or restoring CPU timeouts.

**Architecture:** Keep retrieval/scope/answerability thresholds unchanged. Replace the extractive bypass with one bounded, tool-free synthesis using only approved, complete source chunks. Program-owned clarification/failure messages remain separate from grounded facts. Enforce document-dump rejection at the shared output boundary, including mixed shopping/finalization paths.

**Constraints:** No model/provider changes, infrastructure operations, new dependencies, unrelated refactors, or automatic human escalation. Accept legacy `extractive` configuration for migration, but never expose raw documents. No live deployment without a separate deployment action.

### 1. Reproduce before implementation
- [x] Add regression coverage for legacy mode, approved-only prompt evidence, full source-condition preservation, tool-free synthesis, malformed/insufficient evidence, timeout/failure/empty/model document dumps, and SSE publication.
- [x] Cover dissatisfaction clarification versus explicit returns, quality issues and human requests.
- [x] Run new tests and confirm failures match the reported behavior.

### 2. Fix the answer boundary
- [x] Replace `build_extractive_answer` with bounded source-verified generation in a focused agent module.
- [x] Reject copied document bodies at citation validation, without rejecting short factual quotations.
- [x] Keep program-controlled failure reasons distinct from retrieval failure and insufficient evidence.
- [x] Clarify vague post-purchase dissatisfaction before evidence lookup; preserve scoped-policy and explicit-action behavior.
- [x] Update production configuration and migration documentation; do not change historical QA evidence.

### 3. Verify
- [x] Run focused regressions, full AI suite and deployment configuration/secret-hygiene checks.
- [x] Inspect the diff and run whitespace validation.
- [x] Report measured checks and explicitly distinguish local verification from live production behavior.

## Verification evidence (2026-10-30, local only)

- Red: the initial 20 new behavior cases failed, including the exact raw-document prefix and headings in legacy mode.
- Red: mixed-turn duplicate evidence regression failed before prompt projection; separate-budget and inline-citation bypass regressions failed before their fixes.
- Green: from `ai-service`, `python -m pytest -q --tb=short -W ignore::DeprecationWarning`: **553 passed**.
- Green: from repository root, `python -m pytest eval/tests tests/test_secret_hygiene.py -q --tb=short -W ignore::DeprecationWarning`: **32 passed** (24 evaluation-tool tests, 8 hygiene tests).
- Production Compose YAML parsed and generation mode / timeout ordering checked; scoped `git diff --check` clean.
- Full LangGraph → kb_search → synthesis → output validation → SSE regressions cover successful answers, copied documents, timeout, and clarification. These use deterministic fake retrieval/model providers, not a live inference benchmark.
- Independent review found and tests reproduced two edge cases: dropping a separate exception under the input budget, and copied paragraphs interleaved with citations. Both fixed and included above.
- No live service deployment, provider change, database operation, or model download was performed. Real CPU latency and production semantic quality still require post-deployment verification.
- Concurrent cart-related workspace changes are outside this fix and were not modified.

## Deployment follow-up: actual legacy runtime

- Candidate deployment was stopped before switching the production AI container because real generation exceeded 30 seconds or omitted citations. Production remained healthy on its previous image.
- Confirmed on the SDK transport: langchain-openai 1.6.0 rewrites `max_tokens` into `max_completion_tokens`; the existing legacy Ollama runtime ignored the latter and generated over 1,200 tokens. New opt-in `KB_LEGACY_MAX_TOKENS` supplies a wire-level legacy `max_tokens` via `extra_body`, without changing normal providers or general chat limits.
- Model output now contains structured points and source IDs. The application validates all IDs and attaches per-point citations; raw-document detection and the output citation gate still apply.
- Unforced structured-output probe on the actual model completed generation in 7.46 seconds, preserving the policy's conditional scope. Forced JSON grammar was rejected after a 100-second failed diagnostic; it is not used in production code.
- Generation timeout adjusted to 60 seconds, still below the 180-second request deadline. Input completeness and truncation rejection are unchanged.

- Runtime follow-up regression: **567 AI tests passed**, plus **32 evaluation/hygiene tests**. New cases inspect the actual OpenAI-compatible HTTP request body, structured sources, malformed JSON, and both legacy/normal provider behavior. Independent review found no further actionable issues.

- Further candidate evidence: verbose structured output could exhaust the real cap and leave incomplete JSON; tightened to the simpler two-scenario tested prompt. A real opened-product probe also exposed a small-model reversal of the source's explicit exception. Added a conservative shared output guard for that known contradiction: request product details instead of issuing a blanket refusal. This is not a general semantic-entailment guarantee.

- Final runtime follow-up regression: **570 AI tests passed**, **32 evaluation/hygiene tests passed**; scoped diff check clean.
