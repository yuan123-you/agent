# Admin AI execution trace implementation plan

> Execution: local, test-first; retain all current uncommitted AI-chain work.

**Goal:** Make each newly executed AI turn inspectable in the existing administrator console without exposing diagnostics to customers.
**Architecture:** Python collects bounded, redacted node/model/tool/RAG/guard/memory spans from existing events and narrow instrumentation. An internal-only SSE trace snapshot is consumed (not forwarded) by Java, which persists it in MySQL. Admin-only paginated APIs and a timeline/detail page read that data. Existing Langfuse remains optional; no new runtime dependency.
**Spec:** User asks to inspect AI-chain step data in the management backend.

## Constraints
- Keep existing business authorization, SSE recovery, Agent and RAG behavior unchanged.
- No hidden reasoning, credentials, unrestricted raw objects or unbounded prompts in traces.
- Trace identities and conversation/user ownership are assigned by Java, not the model.
- Trace failure must not break chat. Failed/timeout attempts are visible even if the AI service is offline.
- Real step durations from execution events; absent token usage is unknown, not zero-inferred.
- Existing history cannot be backfilled with invented step data.

## Tasks
- [x] Python recorder tests (timing, nesting, model usage, masking, bounds, isolation, failures); implement capture and SSE integration.
- [x] Instrument RAG parallel recall/filter/RRF/rerank/answerability and memory/guard phases without extra model calls.
- [x] V19 migration + trace persistence, internal snapshot handling, admin pagination/detail, strict access tests.
- [x] Existing admin navigation + AI trace page (filters, table, status, timeline, step data, loading/error/empty states); component tests.
- [x] Real local browser visual/interaction validation with clearly labeled fixture if backend unavailable.
- [x] Full Python/Java/frontend tests, frontend build, documentation and limitations.

## Verified results (2026-10-29)

- Python full suite: **516 passed** (existing asyncio/Python deprecation warnings remain).
- Java clean full suite: **787 tests**, 0 failures, 0 errors, 0 skipped; V19 executed in H2 MySQL mode.
- Frontend full suite: **54 files / 502 tests passed**. Final focused chat/new-page tests: 12 passed. Production Vite build passed.
- Real in-app browser: list/detail, LLM input/output, RRF candidate scores, type filtering; desktop and mobile screenshots saved locally. After fixing an absolutely positioned accessibility-label overflow, mobile document width equals viewport width while the table retains internal scrolling.
- Real Spring Security filter tests reject anonymous/customer/merchant/agent reads, allow ADMIN reads, and require internal token for snapshots.
- Internal trace SSE is persisted without forwarding/replaying to customers. Background snapshots use partial updates so they cannot overwrite terminal status or ownership.
- Additional failure tests: checkpoint initialization, tool error ToolMessage, clipped/hidden reasoning content, unknown token usage, asynchronous preference completion, parallel request isolation.
- `git diff --check`: passed.
- No production deployment, production database mutation, credentials changes or real model efficacy claims. Preview uses explicitly labeled synthetic fixtures.
