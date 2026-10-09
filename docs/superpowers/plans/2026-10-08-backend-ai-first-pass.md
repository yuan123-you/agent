# AI Mall backend and AI remediation — first-pass implementation plan

> Execute locally task-by-task with test-driven-development and verification-before-completion. No delegation is authorized for this request.

**Goal:** Establish a repeatable backend baseline and repair the confirmed first-pass issue without changing frontend code.

**Architecture:** Preserve existing service interfaces and database contracts. Write a failing regression test before a minimal fix; broaden investigation separately rather than replacing the application.

**Tech Stack:** Python / FastAPI / Spring Boot / MySQL

**Spec:** User request on 2026-10-08: cover backend, database business logic and AI business; do not modify frontend.

## Global constraints
- Preserve all pre-existing uncommitted changes; no reset, overwrite, commit, push or deployment.
- No production database writes or migrations in this pass.
- Business-rule ambiguities must be confirmed with the user before implementing.
- Mock external services for regression tests; do not spend AI tokens or call production endpoints.
- Passing existing unit tests is not evidence that end-to-end business is correct.

### Task 1: Isolate internal authentication from external document downloads
Files: ai-service/app/clients/backend_client.py; ai-service/tests/test_backend_client_download.py.
Contract: download_file must retain X-Internal-Token only for the configured backend origin (scheme, host, port); object storage / external origins must never receive it. Relative backend URLs continue to work; external presigned URL query parameters remain unchanged.
- [x] Add deterministic httpx.MockTransport tests for internal, external, downgraded-scheme and changed-port URLs.
- [x] Run python -m pytest tests/test_backend_client_download.py -q and record the existing failure.
- [x] Build the download request, remove internal authentication for different origins, then send it without changing URL or shared client headers.
- [x] Run all ai-service tests and backend Maven tests.

### Follow-up investigation (not yet diagnosed or implemented)
Trace Agent identity isolation, action preparation/confirmation and idempotency, order/stock transactions, ingestion callback errors, retrieval evidence, streaming cancellation and human handoff. Reproduce each issue before choosing a fix. Any RAG/domain-rule changes require consulting the existing PRD and AI design docs.

## Execution evidence
- New download regression: before fix 3 failed / 2 passed; after fix 5 passed.
- Full ai-service: 155 passed (568 deprecation warnings).
- Full backend: 109 passed; Maven BUILD SUCCESS.
- No real external downloads, provider requests or database writes were performed.
