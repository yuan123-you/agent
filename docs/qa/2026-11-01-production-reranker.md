# Production RAG reranker activation — 2026-11-01

Status: isolated real-model tests complete; production cutover pending verification.

## Scope

This branch starts from verified production323b1ac, not the blocked semantic/generation
upgrade ondev405698e. Chat and intent remainqwen2.5:1.5b; embeddings remain
shaw/dmeta-embedding-zh/768 and collections stay unchanged. No AI/backend/frontend
source files change. Only a dedicated cross-encoder service and production configuration
are added. No Ollama JSON-scoring or product reranking is enabled.

Model: BAAI/bge-reranker-v2-m3, onnx-community INT8 export revision
6f5ff65298512715a1e669753bc754d2bc8f367b. Model SHA256:
912fc1215c2dbff6499700534bd8d31253af01573861abbfc43afd1fab6cce5d.
All files are independently verified and mounted read-only; no paid-provider migration.

## Actual ARM64 hybrid test

Existing dense20/BM2520 → metadata filter → RRF10 → model scores → final4.
Three CPU threads; ten query/document pairs per request; unchanged confidence thresholds.

| Query class | Coarse top4 IDs | Fine top4 IDs | Rerank seconds | Answerability |
| --- | --- | --- | --- | --- |
| In-warranty repair postage |226,223,209,235|226,223,242,209|8.897|Conservative refusal: top score0.303 below0.45 |
| Return postage |224,243,216,242|242,223,225,224|9.734|Answerable |
| Return deadline |248,224,209,244|242,224,209,244|7.158|Answerable |
| General opening principle |216,224,227,248|224,242,227,216|9.834|Answerable |
| Fresh-food quality |244,216,225,231|216,244,227,225|8.473|Answerable |
| No automatic approval/refund |229,228,209,244|209,229,228,233|8.145|Answerable |
| Cross-SKU exchange |230,225,209,247|209,247,225,230|9.507|Answerable |
| Unknown invoice rules |211,236,248,247|235,209,248,236|6.443|Unanswerable |
| Unrelated astronomy |232,224,225,223|225,224,209,232|6.399|Unanswerable |

All9 requests had real finite rerank scores with no fallback. Relevant expected chunks
were in final4 for7/7 policy cases; negative rejection2/2. The combined positive-answerability
check is8/9, explicitly not9/9. No thresholds were lowered. This gate qualifies the ranking
stage's activation, not universal factual correctness of generated answers.

Two independent review findings (cancelled caller releasing a live worker's permit,
and unbounded timed queue admission) were reproduced red and fixed. The inference task
now owns its permit and survives caller cancellation; busy requests reject immediately,
with ingress concurrency limits. Follow-up review and final tests are recorded below.


## Engineering and failure-path verification before cutover

- AI baseline regression:579 passed (production-base branch; the unqualified generation branch is deliberately excluded).
- Dedicated reranker service/config tests:18 passed, including checksum publication, bounded busy admission and cancelled-call worker ownership.
- Independent concurrency re-review: both reproduced issues fixed; no further actionable concurrency finding.
- Real service503 overload: original RRF order restored in2.024s, all rerank scores unset, explicit reranker_unavailable degradation.
- Forced HTTP client timeout: original RRF order restored in0.271s with the same explicit degradation. These synthetic fault tests are not model-accuracy cases.
- Model/embedding/index values and all application/business source files remain unchanged.

Auxiliary evaluation/credential hygiene plus reranker tests:50 passed. Existing deployment static baseline:11 passed,1 unchanged CartView simulated-payment-text failure.

Production cutover and final HTTP/runtime evidence will be appended only after actual verification.
