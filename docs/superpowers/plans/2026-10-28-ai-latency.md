# AI intent and search latency implementation plan

**Goal:** Reduce actual classifier/search-answer latency without replacing semantic classification or retrieval with date rules, and without bypassing business confirmations or evidence validation.
**Architecture:** Keep the classifier and real search. Bound classifier-only context/output; scope general-web tools; after real web evidence, use a compact tool-free terminal node and link-guarded streaming. Hedge slow search providers within one deadline. Preload the existing local Ollama model at service startup and retain it using explicit production settings.
**Execution:** Sequential TDD in this workspace; preserve all concurrent changes. No model/provider replacement, answer-length cap, deployment, Git commit or push.

## Baseline (production containers, read-only diagnostic requests)
- Same contextual classification: cold 9.553s; warm 0.944s; both PRODUCT_CONSULT.
- SearXNG 1.126s / 3 results; Bing 0.197s / no results; Sogou 3.286s / 3 results. Warm current cascade 0.304s / 3 SearXNG results. These are individual samples, not p95 claims.
- General web answer after actual search evidence: 9 bound tools; 4,187 message characters before tool schemas; first model text 52.788s; not complete at 60s. The baseline performed no business tool execution and no production source/configuration writes.

## Files
- `ai-service/app/agent/nodes.py`, `prompts.py`, `graph.py`, `app/api/chat.py`: compact classifier input, web-only tools, tool-free evidence-grounded terminal web answers and safe early token delivery.
- `ai-service/app/clients/llm.py`, `app/config.py`, `app/main.py`, `deploy/compose.production.yml`: classifier-only output bound, no automatic classifier retries, opt-in Ollama preload/retention.
- `ai-service/app/tools/web_search.py`: bounded provider hedging, preserve actual provider results and existing parsers.
- New focused tests for classification context, routing/tool safety, early tokens, provider deadlines and startup warmup; extend existing regression tests only for intentional contract changes.

## Steps
- [x] Observe failing tests for excess web tool scope, web evidence terminal routing/streaming, classifier input budget, search fallback serialization and startup warming.
- [x] Implement narrow changes, retaining product/RAG/business paths and every existing grounding/approval guard.
- [x] Run the actual existing model against the same synthetic cases, comparing old and optimized stages in a diagnostic process only; keep the production service unmodified.
- [x] Run all AI-service tests and deployment config checks. Record latency, correctness and any unverified conditions separately.


## Implemented changes
- Classification retains the actual LLM call. Only assistant-history prose is shortened; buyer requirements and the latest query remain intact. JSON classification is capped at 64 output tokens, not user-facing answers. The classifier can return a contextual `web_query` in the same call, removing a separate tool-selection inference; this field is cleared each turn and ignored for business intents.
- General-web planning binds only `web_search`, not the nine-tool commerce set. Completed web-only evidence routes to `web_answer`, which has a compact prompt and no bound tools. Product, order, policy/RAG and human-handoff paths remain on their guarded routes. Previous user topic and clarifying context are retained.
- Actual web answer text is streamed through the existing link guard. A normalized source label is attached only with substantive model output (never emitted early as fake speed). Split or model-supplied labels are not duplicated.
- Web providers use cancellable async HTTPX requests. The configured provider has a 0.5s preference window; slow/failing providers race fallbacks within a 5s total deadline. Losing HTTP bodies are cancelled and closed, including slow-trickling bodies. No provider thread pool remains. Search errors/empty evidence do not trigger another model call merely to explain the failure.
- Opt-in startup preloads existing local model weights and static classification/web prompt prefixes. Production configuration retains the existing 1.5B model in memory; no new model/provider or inference resource was deployed. Warming has a total deadline and generates only a single synthetic preload token per prefix, not a user-answer cap.

## Review and regression evidence
- Observed RED for excess bound tools, missing terminal routing, oversized classification history, delayed fallback, missing search deadline, unprimed startup, lack of early terminal streaming, duplicate/missing web labels, lost previous topic, contextual query planning, and wasting model inference on failed/empty searches.
- Review found that the initial thread-based hedge could exhaust workers with trickling HTTP bodies. Replaced it with async HTTP and added `test_trickling_losers_are_closed_and_cannot_starve_later_fast_searches`. Independent re-review reported no unresolved P1/P2 findings in search cancellation/cleanup; its 19 provider/deadline tests passed.
- Full AI-service regression: 418 tests passed (dependency deprecation warnings and an existing background-memory cleanup warning remain). Deployment/configuration checks: 11 passed. No frontend/backend commerce files were modified by this latency task.

## Actual latency and accuracy experiments (not mocks)
Diagnostics executed new sources only in an independent process inside the existing AI container, using actual model inference and real search HTTP. They used an in-memory checkpointer, synthetic user ID 0, disabled background product sync/tracing and no business actions. They did not update production sources/configuration or restart services.
- Original general-web response after real search evidence: first model text 52.788s, 9 tools bound, unfinished at the diagnostic 60s limit.
- Initial optimized whole pipeline: first user-visible model text 17.336s; complete at 31.453s. Intent and real search were included.
- Preloaded run on a repeated news question: first user text 14.118s on its initial request and 2.311s on the cache-warm repeat; complete at 25.563s / 16.621s respectively. The cache-warm repeat is NOT a general uncached guarantee.
- Final distinct-query checks, including semantic query generation and static-prefix startup warming: first real text 22.799s / 21.148s. Both had partial real output but did not complete within the diagnostic 60s limit. They involved no commerce tool bindings. This means stable fast responses have NOT been achieved on the current inference backend; do not advertise the 2.311s repeat as the general result.
- Tested the already-installed 0.5B model only in a diagnostic process: 2/6 contextual intent cases correct, versus 6/6 for the retained 1.5B model. Rejected the smaller model; no quality-for-speed model replacement was made. Six cases are a small regression sample, not a general accuracy estimate.
- Inspected runtime: four Neoverse-N1 CPU cores; production chat and classifier both use local `qwen2.5:1.5b`, with one parallel model request configured. Remaining first-token time is in inference/queueing, not the measured warm search request.
- The project has a configured cloud inference endpoint. One synthetic, 64-token-bounded authentication/latency probe against its allowlisted HTTPS host returned HTTP 401 in 0.511s. No real conversation was sent, no key was logged, and no cloud production cutover occurred. The existing cloud configuration must pass authentication before its latency can be evaluated or used.

## Outcome / handoff
The avoidable classification/tool-planning/search overhead is patched and regression-tested, but the user's requirement for consistently fast inference is not yet satisfied. A valid, authenticated faster inference backend or additional suitable inference resources is needed for the next measurement. Cloud credentials/configuration require user confirmation/update; do not paste keys into chat. No deployment, commit, push, schema migration, provider cutover, or real-user data transfer was performed.

Local diagnostic evidence: `.workbuddy/tmp/assistant-live-prewarmed-final.log`, `assistant-live-new-queries-final.log`, `assistant-cloud-probe.log`, `ai-latency-delivery-tests.log`, and `ai-latency-deploy-tests.log`.
