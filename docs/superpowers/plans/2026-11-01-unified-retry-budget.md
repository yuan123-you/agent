# Unified bounded retry engineering — 2026-11-01

## Goal and baseline
Preserve the uncommitted native-action/RAG work on codex/native-agent-recovery. Implement classified retry, bounded Full Jitter, request deadline and retry permits, explicit replay safety, one retry owner, and reproducible failure evidence. Do not deploy, run financial operations, download models, or tune RAG labels/thresholds.

## Root causes found
- BackendClient retries all exceptions with fixed .3s sleeps, including unsafe POSTs without an idempotency key.
- ChatOpenAI has SDK max_retries=1 while intent differs; native graph uses additive LangGraph jitter without a deadline.
- Legacy reranker independently sleeps/retries; current embeddings/reranker lack a common budget.
- Python chat has an outer timeout but no shared retry permits; Java gateway timeouts are per call/stream-idle and do not propagate a remaining budget.

## Frozen interface / ownership
Parent owns ai-service/app/resilience.py, backend_client.py, action_workflow.py, clients/action_workflows.py, API/middleware/config, related tests/docs/evidence.
Model worker owns ONLY ai-service/app/clients/llm.py, clients/ollama.py, rag/reranker.py and NEW tests/test_model_resilience.py. Java worker owns backend/** only.

Shared Python interfaces (parent implements):
- budget_scope(timeout_s:float, retry_tokens:int=6): synchronous contextmanager; shares the permit ledger and takes min(parent deadline, local deadline). current_budget() -> RequestBudget|None.
- RequestBudget.remaining() -> seconds; header propagation via budget_headers() -> {X-Request-Timeout-Ms, X-Request-Retry-Budget}.
- async run(operation:str, call: Callable[[float],Awaitable[T]], *, replay_safe:bool, max_attempts:int=3, attempt_timeout_s:float=30, total_timeout_s:float|None=None, base_delay_s:float=.25, max_delay_s:float=2) -> T. The call receives its clipped attempt timeout; run owns retry. Nested runs get one attempt, not multiplied retries. Cancellation never retries.
- TransientFailure(message, *, retry_after_s:float|None=None, retryable:bool=True) is explicitly retryable; invalid model/schema/domain failures are NOT transient. DeadlineExceeded(TimeoutError), RetryBudgetExhausted(RuntimeError).
- ResilientAsyncTransport(operation:str, *, replay_safe:bool, timeout_s:float, transport:httpx.AsyncBaseTransport|None=None, max_attempts:int=3): use only as sole retry owner for SDK HTTP with SDK retries OFF. Buffers non-SSE responses inside attempt deadline; never replays SSE after response acceptance.

Policy: only transport/timeouts and HTTP408/429/500/502/503/504 are candidates; TLS/config/protocol/validation/auth/business failures are permanent. Full Jitter uniform(0,min(cap,base*2^n)). Valid Retry-After is a minimum; if above cap/deadline, stop rather than retry early. Shared remaining retry permits across parallel/nested tasks, per-operation max attempts. HTTP callbacks from native graph are single-attempt; native execute node alone runs shared policy. All writes single-shot unless explicit stable key/domain idempotency. Preparation with native key and native execution actionId are replay-safe; escalation/memory/ingest writes otherwise no automatic retry.

Cross-process: trusted internal X-Request-Timeout-Ms is remaining relative time, clipped to local max, never extend on forwarding; X-Request-Retry-Budget clipped to local max. Java/SSE/native gateway do NOT replay calls; Python owns model/tool automatic retries. No claim of a distributed global token counter; only one owner per operation and a shared Python request permit ledger. Background jobs get their own bounded job budget, not accidental foreground context inheritance.

## Verification sequence
1. Tests first for classification, exact jitter bounds, Retry-After, clipped call timeouts, deadline exhaustion, concurrent/nested permit bounds, cancellation, unsafe POST no replay, idempotent write lost-ack recovery, stream partial output no replay, SDK retries OFF.
2. Wire clients/ingress and Java remaining budget. Keep existing graceful-degradation contracts without turning validation failures into fake success.
3. Run full AI/Java/frontend/aux suites. Re-run native crash-window evidence because engine hashes change; retain historical live RAG evidence without claiming it tested new retry code.
4. Capture actual fault-injection call counts and effects; no fabricated live service availability/latency numbers. Independent review and explicit coverage/limits documentation.

## Execution evidence
Implemented the four constraints with tests-first failures and independent review fixes.
Final gates: AI787, Java868, frontend580, aux121 passed; tsc/build0; pinned/current Milvus boundary51each.
Actual loopback CLI recorded15 HTTP requests across8 fault cases; unsafe committed write remains unresolved at1request/1effect, keyed replay2requests/1effect. Native process recovery remains verified with current hashes.
Existing unrelated CartView simulated-payment-label gate remains1failed/11passed. No deployment or native-approval cutover. Full scope/limits: docs/qa/2026-11-01-unified-retry-budget.md.
