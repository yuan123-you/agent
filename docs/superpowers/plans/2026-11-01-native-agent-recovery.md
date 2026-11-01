# Native action interruption/recovery and quality evidence

**Goal:** Put pending AI order/create/cancel/after-sale actions behind real LangGraph interrupt()/Command(resume=...) execution, and add reproducible retrieval/Agent evidence. This is not SSE reconnection rebranded as durable execution.

**Baseline:** production-base branch with verified reranking; active models, vector dimensions/collections and financial confirmation invariants stay unchanged. Work branch codex/native-agent-recovery. Feature flags default OFF; no production financial confirmations or cutover in this implementation task.

## Architecture and trust boundaries

- Each prepared action has an independent native workflow thread bound to(userId,conversationId,actionId,type,immutable snapshot fingerprint). Pending approvals must not freeze unrelated chat turns.
- Backend prepares the existing canonical action first, commits its transaction, then registers an approval workflow through a new authenticated AI HTTP request. Never call AI while holding a business DB transaction.
- Graph: START → review(interrupt with non-sensitive action metadata) → execute_decision → END. Review has no side effects before interrupt; execution calls the existing backend validation/idempotency domain service, never a model-directed confirm tool.
- Public confirm/cancel endpoints authenticate the user, resolve the canonical action and submit a trusted decision to native resume. Recover/status never turn waiting into approval. The native stored decision must exist before recovery may replay execution.
- Durable AsyncSqliteSaver in a separate persistent DB, single-instance boundary explicitly documented. No MemorySaver fallback for approvals. Process restart and crash-after-business-commit/before-checkpoint must be tested.
- Preparation gains a stable injected tool-call key and database idempotency binding. Replays must return the original pending action rather than create new ones; changed payload under the same key must be rejected.
- Existing owner, conversation, expiry, price, quantity, stock, action-type and after-sale checks remain authoritative. The existing domain confirmation remains idempotent on actionId. No real payment/refund is introduced.

## Frozen HTTP contract

Python AI endpoints (X-Internal-Token, feature enabled):
POST /v1/action-workflows/{actionId}/start or /status or /recover:
  {userId:int, conversationId:int}
POST /v1/action-workflows/{actionId}/resume:
  {userId:int, conversationId:int, decision:"approve"|"reject", approval?:{receiverName,receiverPhone,receiverAddress}}
Response:
  {actionId,workflowStatus:"WAITING_APPROVAL"|"EXECUTING"|"COMPLETED"|"CANCELLED"|"FAILED"|"EXPIRED",nativeInterrupt:true,interrupted:bool,recoverable:bool,result?:legacy-confirm-map,error?:{code,message}}
Transient/exhausted retry returns HTTP503 with no false terminal success. Resume conflicts/bad bindings are4xx. Status/recover before a saved approval must not execute anything.

Backend internal endpoints (existing X-Internal-Token protection):
POST /internal/tools/action-workflows/snapshot {userId,actionId}
  → ApiResponse data {actionId,userId,conversationId,type,status,expiresAt,fingerprint}
POST /internal/tools/action-workflows/execute {userId,actionId,approval?}
  → ApiResponse data existing legacy public-confirm result map
POST /internal/tools/action-workflows/cancel {userId,actionId}
  → ApiResponse data {type,actionStatus:"CANCELLED"}
Before resume/recover the backend explicitly calls idempotent start, so lost registration can be recreated without approving anything. Python resume/recover themselves never implicitly create missing threads.
Snapshot fingerprint must remain stable through domain confirmation; never include mutable status/result IDs. Canonical snapshot is backend-owned and resolved again before resume/recovery. Approval values stay out of LLM prompts and diagnostic logs.

Backend uses app.ai.action-workflows-enabled=false by default. Python uses ACTION_WORKFLOWS_ENABLED=false and durable checkpoint path. With flags OFF legacy API behavior is retained for legacy actions; native-provenance actions fail closed and can never downgrade to direct confirmation. With flag ON the legacy internal direct-confirm route must not bypass the native workflow. Public legacy confirmation result shape remains compatible, with optional workflow metadata. Add buyer-owned POST /order-actions/{actionId}/recover and optional workflow status metadata without trusting frontend-provided results.

## Tasks / write ownership

- [x] Python(native engine, typed backend client, protected router/lifespan, injected preparation key): native tests first, real SQLite checkpoints, bounded classified RetryPolicy on execution only, no retry multiplication. Parent owns ai-service/**.
- [x] Java(canonical/idempotent preparation, coordinator/client, public/internal endpoints, feature config, migration/tests): preserve domain validators, new requests bind to the authenticated owner. Backend worker owns backend/** only.
- [x] Independent RAG quality dataset and four-arm ablation evaluator: source validation, Recall@4/MRR@4/nDCG@4, negative-query answerability, timings/model/source provenance, raw records. Evaluator worker owns eval/rag_quality.py, eval/dataset/rag_quality_v1.jsonl, eval/tests/test_rag_quality.py and dataset-card documentation only.
- [x] Frontend optional native-pending/recover rendering and recovery actions; parent owns frontend changes after protocol integration.
- [x] Run full suites; real subprocess restart and commit-window replay evidence; benchmark uses only published knowledge/read-only model calls. No mock scores described as accuracy, no fabricated SLA, no tuned-on-test thresholds, no paid provider or new model download.
- [x] Independent review, record limitations and failing metrics honestly. No production approval-flow deployment without a separate release gate.
