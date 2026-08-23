# T10 RAG Retrieval Pipeline — Final Fix Report

Date: 2026-08-23 (Asia/Shanghai)  
Branch: `feature/t10-rag-retrieval`  
Implementation commit: `7dfbc020e9c0527363aad94fab405f9b115a8cad`

## Scope and approach

This wave addressed all six final-review findings against the binding T10 redesign spec and implementation plan. Each production change was preceded by a focused regression that failed for the reported reason. No dependencies, network services, second model calls, or new logging of document content, API keys, or retrieval exceptions were introduced.

## Per-finding changes and evidence

### IMPORTANT 1 — lazy vector-store acquisition

- Changed `get_retrieval_pipeline()` to install an async vector adapter that calls `get_vectorstore()` only when the vector leg is awaited inside `asyncio.gather`.
- A Milvus/vector-store constructor exception is therefore captured by the existing per-leg degradation path as `vector_unavailable`; it no longer prevents the BM25 coroutine from running.
- Regression: `test_cached_pipeline_degrades_when_vectorstore_initialization_fails` makes `get_vectorstore()` raise while BM25 returns a high-confidence hit. It proves an answerable result, the BM25 hit, and exactly `("vector_unavailable",)` degradation.

### IMPORTANT 2 — no rejected candidate body in tool payload

- `kb_search` now serializes citations, context, and hits only for answerable results.
- Unanswerable results return `context: ""`, `citations: []`, and `hits: []`; status/reason/degradation metadata remains available.
- Regression: `test_unanswerable_candidates_never_expose_body_content` supplies a low-score nonempty candidate with a unique sentinel body and proves both empty hits and absence of the sentinel from the entire JSON payload.

### IMPORTANT 3 — preamble-safe SSE structure

- Natural-language provider chunks are held server-side until the graph has established whether `kb_search` occurred.
- The first `kb_search` start/end event clears all provisional pre-tool natural language. Later RAG text remains buffered through deterministic citation and link validation and is emitted once; token concatenation therefore exactly equals `done.content`.
- Tool-call and tool-result events remain immediate. The graph is still invoked exactly once; citation failure remains deterministic and performs no retry/second generation.
- Genuine non-RAG answers retain the provider's token chunk boundaries when the link guard does not rewrite text, but those chunks are released only after graph classification/completion. If the link guard rewrites the aggregate, one guarded token is emitted so token concatenation still matches `done.content`.
- Regression: `test_preamble_before_kb_search_never_leaks_or_duplicates` emits a substantive preamble before `kb_search`, then a cited answer. It proves the preamble is absent from the full SSE payload, exactly one validated RAG token is emitted, and token concatenation equals `done.content`.
- Latency tradeoff: because SSE cannot retract bytes and a provider may reveal a tool call only after emitting arbitrary text, guaranteeing that a future `kb_search` cannot invalidate already-sent text requires delaying natural-language delivery until the graph's RAG decision is known. Non-RAG content and chunk semantics are preserved, but first-token latency now includes that decision/full graph completion. Tool process events are unaffected.

### IMPORTANT 4 — forged source-like marker rejection

- Citation scanning now captures every `[S<digits>]` marker first, then separately requires canonical `S[1-9][0-9]*` form and membership in the allowed map.
- Mixed valid plus forged markers cannot hide behind the canonical-only extractor.
- Regression: parameterized `test_mixed_valid_and_noncanonical_source_markers_fail` covers valid `[S1]` mixed with `[S0]` and `[S01]`; both deterministically produce `unknown_citation`, fallback content, and no citations.

### MINOR 1 — fixed top-20 RRF contract

- Added an absolute Pydantic field bound `rag_rrf_top_k <= 20`, independent of configurable recall-window sizes.
- Existing ordering validation (`final <= RRF <= recall windows`) remains intact.
- Regression: `test_rrf_top_k_stays_capped_when_both_recall_windows_are_raised` jointly raises both recall windows to 40 and proves `rag_rrf_top_k=21` is still invalid.

### MINOR 2 — single-candidate calibration semantics

- Calibration accepts JSON `top2: null`; a null second candidate satisfies the margin condition exactly like runtime `assess_answerability` does for a single candidate.
- `eval/README.md` documents the nullable schema, example, and semantics.
- Runtime defaults and application configuration were not changed.
- Regression: `test_single_candidate_null_top2_satisfies_margin` proves `top1=.45`, `top2=null` is accepted even with a `.15` minimum margin.

## TDD evidence

### RED

- Focused AI regressions: 6 failures in 2.28 s, one expected failure for each issue (citation case parameterization produced two failing cases).
- Calibration null regression: 1 failure in 0.43 s (`TypeError` subtracting `None`), matching the missing single-candidate representation.

### Focused GREEN

- `cd ai-service; python -m pytest tests/test_rag_pipeline.py tests/test_kb_search_tool.py tests/test_chat_rag_citations.py tests/test_rag_citations.py tests/test_rag_config.py -q`
  - 40 passed, 0 failed, 208 warnings, 0.81 s.
- `python -m pytest eval/tests/test_calibrate_answerability.py -q`
  - 5 passed, 0 failed, 1 warning, 0.26 s.

## Full verification

- `cd ai-service; python -m pytest -q`
  - 125 passed, 0 failed, 487 warnings, 1.56 s (command wall time 7.58 s).
- `cd backend; mvn test`
  - 36 run, 0 failures, 0 errors, 0 skipped; Maven test/build time 12.841 s (command wall time 14.87 s); `BUILD SUCCESS`.
- `python -m pytest eval/tests/test_calibrate_answerability.py -q`
  - 5 passed, 0 failed, 1 warning, 0.26 s.
- `python eval/scripts/calibrate_answerability.py --input eval/dataset/rag_answerability.jsonl --output eval/results/answerability-calibration.json`
  - Exit 0 in 0.156 s; 216 candidates.
  - Best: `min_score=0.30`, `high_score=0.60`, `min_margin=0.03`, precision/recall/F1 `1.0`, reject rate `0.5`.
  - Generated report was unchanged, confirming calibration remains report-only.
- `git diff --check`
  - Exit 0 after removing one test-file trailing blank line found during the pre-commit check.

## Compatibility and safety checks

- Stage 1 adapters and defaults are unchanged.
- Fixed T10 vector/BM25 recall, RRF, reranker fallback, answerability, and citation behaviors remain covered by the full suites.
- No dependency or service was added.
- No content, API key, or raw vector initialization exception is logged by these changes.
- Citation rejection remains deterministic and graph call-count assertions remain one; no second model call was added.

## Residual concerns

1. The structural SSE guarantee increases first-token latency for genuine non-RAG answers to graph decision/completion time. This is unavoidable without a trustworthy pre-generation signal that guarantees the graph will never call `kb_search`; emitting earlier would reintroduce irreversible leakage. Tool progress events still stream immediately.
2. The passing Python suite reports 487 existing `pytest-asyncio` deprecation warnings under Python 3.14. They do not affect this wave but should be handled before the corresponding APIs are removed in Python 3.16.
3. Maven reports the existing `compilerVersion` deprecation warning. It is unrelated to T10 behavior.
