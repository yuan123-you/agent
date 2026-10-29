# AI Chain Simplification Implementation Plan

> **For agentic workers:** Use executing-plans to implement task-by-task. Execution stays local; no delegation or new infrastructure is required.

**Goal:** Preserve the existing Agent + hybrid RAG capabilities while eliminating duplicated request routing, identity merging, and final-output validation.

**Architecture:** Java remains the authenticated business gateway and transaction owner. Python owns one request-routing policy, one conversation-profile resolver, and one evidence-aware output policy. Retain the existing LangGraph tool loop and RetrievalPipeline rather than introduce another orchestration framework.

**Tech Stack:** Existing FastAPI, LangGraph, LangChain, Milvus, BM25/RRF/reranker, Spring Boot, SSE; no new dependencies.

**Spec:** User request in this chat: simplify the entire AI chain to a maintainable, high-standard Agent + RAG architecture. No fabricated performance claims.

## Global Constraints
- Preserve existing uncommitted naming fixes; refine them in place without resetting unrelated files.
- Keep business writes behind authenticated Java tools and explicit user confirmation.
- Preserve mixed shopping/policy routing, contextual web queries, citation gating and link guards.
- No artificial reply delay and no extra LLM merely to display “thinking”.
- SQLite remains a single-instance learning/development deployment choice, not a claimed horizontally scalable store.
- Regression tests must use fake model/backend adapters, never a running model or production database.

### Task 1: Conversation identity seam
Files: app/agent/identity.py (new), app/agent/memory.py, app/api/chat.py, backend ChatService.java, corresponding Python/Java tests.
- [x] Add failing tests for stale profiles, checkpoint loss/history reconstruction, explicit renaming and inferred identity pollution.
- [x] Extract naming parsing and profile resolution; precedence: backend profile < checkpoint identity < trusted USER history < current explicit naming. Regeneration rebuilds identity from backend + supplied valid history, not the failed turn checkpoint.
- [x] Java sends account nickname separately; Python alone interprets conversational identity.
- [x] Verify targeted tests with stubbed models.

### Task 2: Single request routing policy
Files: app/agent/routing.py (new), app/agent/nodes.py, app/agent/state.py, routing tests.
- [x] Add tests for route selection and model-call counts, including human requests mixed with complaints.
- [x] Centralize fast intent rules and destination selection; router stores its decision, graph dispatch consumes it.
- [x] Preserve model fallback for ambiguous/contextual requests and tool iteration limits.
- [x] Verify routing and existing grounding/latency tests.

### Task 3: Output policy and memory completion
Files: app/agent/output.py (new), app/api/chat.py, app/agent/memory.py, output/SSE tests.
- [x] Add tests for policy citation gating vs web results, clarification and invalid links, identity persistence ordering.
- [x] Move final evidence/link validation behind a pure output interface; leave SSE as transport/event handling.
- [x] Persist explicit identity before done; use response-owned background tasks for optional preference extraction rather than unowned create_task.
- [x] Verify streamed prefix/final answer consistency with existing SSE tests.

### Task 4: Acceptance and architecture record
Files: docs/architecture/ai-chain.md, regression suites.
- [x] Run Python full suite, Java affected tests and frontend SSE/store regression tests.
- [x] Record real routes, call budgets, memory ownership, RAG pipeline, limitations and commands.
- [x] Inspect diff; report only measured outcomes. No deployment, commit or database migration without a separate request.

## Acceptance results (2026-10-29)

- Python full suite: **502 passed**, no failed tests. Existing Python/pytest asyncio deprecation warnings remain; no destroyed pending memory-task messages in the final run.
- Java: `mvn clean test -q` exit 0; fresh Surefire reports: **774 tests, 0 failures, 0 errors, 0 skipped**. Confirmed deleted FaqService bytecode is absent after clean.
- Frontend full suite: **53 files / 497 tests passed**.
- `git diff --check`: clean.
- Added call-budget/admission tests: ordinary policy/order/news/identity queries do not invoke memory extraction; contextual web search uses one classifier without a separate rewrite model.
- Additional regression cases discovered in review: colloquial name questions must not rename the participants; disconnect must not emit success or write completion-side memory; model failure must not become template success.
- Removed the obsolete Java FAQ null stub/shortcut, replacing its null-only unit tests with gateway transport tests while retaining current-evidence FAQ integration coverage.
- Added a failing gateway invocation-count test and consolidated duplicate profile/DTO reads into one memory snapshot per turn.
- No deployment, database change, commit, new dependency, or production model/latency benchmark was performed.
