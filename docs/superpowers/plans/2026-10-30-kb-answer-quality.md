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
