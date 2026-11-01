# Production RAG reranker activation — 2026-11-01

Status: production VERIFIED. Deployed code:2dbf495ba7aa77a098d8dd10d1d6180af6b102dd. First failed rollout remains recorded below.

## Scope

This branch starts from verified production323b1ac, not the blocked semantic/generation
upgrade ondev405698e. Chat and intent remainqwen2.5:1.5b; embeddings remain
shaw/dmeta-embedding-zh/768 and collections stay unchanged. The initial attempt changed no application source. The measured integration follow-up
changes only evidence-message ordering plus a bounded native embedding batch configuration;
intent/ownership/confirmation/backend/frontend logic stays unchanged. A dedicated
cross-encoder service and production configuration are added. No Ollama JSON-scoring or product reranking is enabled.

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


## First HTTP cutover blocked and rolled back

Thee73ad2f activation successfully enabled real production rerank scores, preserved all
original eight dependencies and the original AI image, and passed the direct KB positive/
negative checks. However the dedicated QA HTTP question about review timeout produced the
false statement that timeout automatically approves. Verification rejected it and restored
production323b1ac. The QA actor was disabled. This failure is not counted as a successful
release and the original diagnostic record is retained privately.

The actual trace attributed57.434s to query encoding,9.680s to reranking and26.764s to
answer generation. Ranked source209 scored0.979642; source233 scored0.716902. Both expressly
require human handling and deny automatic approval. Thus the false claim was not supported
by the cited source; the ranker had found the relevant negative evidence.

## Controlled follow-up, without new model weights

Same original question, same four complete approved sources and same1.5B model:
- Original question-first data layout reproduced the false affirmative answer.
- Evidence-first/original-question-last layout produced a correctly negative answer.

The source data stays in the Human message, the system message is not interpolated with
user text, and all source/citation/dump guards remain. No business-keyword scoring, forced
citation, approval exemption, model/embedding switch or confidence-threshold reduction is
introduced. This is a small input-layout integration correction, not a general proof of
factual entailment.

Native replay with actual hybrid retrieval and the corrected layout:
- Exact failed question:9.41s total,7.34s retrieval; correctly denied automatic approval.
- Cross-product/SKU exchange:27.88s total,9.22s retrieval; correctly denied cross-SKU exchange.
- Deadline question:32.92s total; retrieval succeeded but generation failed formatting and
  returned the safe existing failure response. This remains a generator limitation, not a
  successful answer or fabricated business clarification.
- Unknown invoice:6.62s, explicitly insufficient evidence, no invented citation.

The native document batch cap now defaults to16 for backwards compatibility and is2 in
production; keepalive is24h instead of2m. Encoder/model/dimension and both collection names
remain unchanged. A read-only shared-weight isolated encoder was used for the batch test,
not a new model download:6 document encodings under a two-text batch cap yielded a5.26s
interactive query and768-dimensional outputs, with no index writes. Its cgroup recorded
no memory-limit or OOM events during that test. This is not a universal latency guarantee.

Follow-up engineering verification:582 AI tests passed;51 dedicated/auxiliary/hygiene tests passed. The product-scope fake-provider reader was adapted to the new Human data envelope without relaxing any product/citation assertions. Independent review found no actionable regression in these three scoped app changes.


## Final production verification — passed

- Published and deployed production-base code2dbf495; all deployed AI Python source hashes
  and reranker source hashes match that commit. Only the three measured RAG integration
  files changed in the application; original eight dependencies retained container IDs,
  images and restart counts. No business/ownership/confirmation source changed.
- Running AI hasRAG_RERANKER_ENABLED=true, modelBAAI/bge-reranker-v2-m3, internal URL
  http://reranker:8001 and20s timeout. Dense20/BM2520/RRF10/final4 verified in runtime.
- Real production factory/KB tool produced finite ordered scores
  [0.986772,0.979239,0.929615,0.894951] for chunks[209,242,229,228]; the unknown invoice
  query was unanswerable without a fake citation.
- Actual backend/proxy HTTP SSE, exact previously failed question:17.37s, correctly denied
  automatic timeout approval and retained a valid source233 reference. No transaction or
  human-transfer tool was executed. This is a single measured case, not a latency SLA.
- Actual unknown-invoice SSE:12.93s, evidence-insufficient response with no citations.
- All32 runtime/source/read-only-chat/cleanup gates passed. All10 services healthy and
  public product API healthy. Dedicated QA conversations closed and actorDISABLED.
- Chat/intent remainsqwen2.5:1.5b; encoder remainsshaw/dmeta-embedding-zh/768. Both Milvus
  collection names remain unchanged; the existing periodic product-index synchronization
  remains enabled, using the smaller batches. No vector-space migration was performed.
- Reranker measured memory1.112 GiB under its3 GiB limit. Shared model directory occupies
  574048 KiB (about561 MiB). Owned evaluation containers and their temporary image tags
  were removed; no shared/production model volume was deleted or duplicated.

Known limits remain explicit: the unchanged confidence gate conservatively rejects the
repair-postage wording in the sample, and the unchanged1.5B generator still has a safely
rejected deadline-formatting case. This release enables and validates the coarse→fine
retrieval path and fixes the reproduced input-layout inversion; it is not a claim that
all generation, inference conditions or all conversational paraphrases are solved.
