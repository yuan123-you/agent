# Phase 1 Correctness and CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore KB version consistency, TypeScript CI, timeout UX, and dependency documentation.

**Architecture:** Keep Spring Boot as the KB source of truth and validate Milvus candidates through the existing internal backend seam. Make the remaining fixes locally without introducing new dependencies or abstractions.

**Tech Stack:** Java 17/Spring Boot/MyBatis-Plus, Python/FastAPI/LangGraph/pymilvus, Vue 3/TypeScript/Vitest.

**Spec:** `docs/superpowers/specs/2026-08-24-phase1-correctness-ci-design.md`

## Global Constraints

- No new runtime dependencies.
- Backend remains the only business and knowledge metadata writer.
- Existing API behavior remains compatible except for the new internal chunk-validation endpoint.
- Every behavior change follows red-green-refactor.

---

### Task 1: Enforce current knowledge versions

**Files:**
- Modify: `backend/src/main/java/com/aimall/backend/internal/InternalKbController.java`
- Modify: `ai-service/app/clients/backend_client.py`
- Modify: `ai-service/app/rag/vectorstore.py`
- Test: `backend/src/test/java/com/aimall/backend/internal/InternalKbControllerVersionTest.java`
- Test: `ai-service/tests/test_vectorstore_current_chunks.py`

- [ ] Write backend tests proving current-version validation rejects inactive, old, and missing chunks and ACTIVE ingestion prunes superseded chunks.
- [ ] Run the focused backend tests and confirm failure.
- [ ] Add the current-version keyword predicate, current-chunk validation endpoint, and post-success old-chunk cleanup.
- [ ] Run the focused backend tests and confirm success.
- [ ] Write an AI test proving stale Milvus candidates are removed before returning hits.
- [ ] Run it and confirm failure.
- [ ] Add the backend client method and vectorstore filtering/source mapping.
- [ ] Run focused and full AI tests.

### Task 2: Restore frontend type checking

**Files:**
- Modify: `frontend/src/views/admin/dashboard.ts`
- Modify: `frontend/src/views/auth/registration.ts`

- [ ] Use the existing failing `npx tsc --noEmit` result as the red test.
- [ ] Add explicit nested DTO partial types and simplify the registration payload signature.
- [ ] Run `npx tsc --noEmit` and Vitest.

### Task 3: Return a timeout fallback

**Files:**
- Modify: `ai-service/app/api/chat.py`
- Test: `ai-service/tests/test_chat_tool_preview.py`

- [ ] Add tests proving non-empty output is preserved and empty timed-out output receives a fixed fallback.
- [ ] Run focused tests and confirm failure.
- [ ] Add the minimal pure fallback helper and use it before link guarding.
- [ ] Run focused and full AI tests.

### Task 4: Align documentation

**Files:**
- Modify: `README.md`

- [ ] Replace Milvus/pymilvus 2.5 claims with server 2.4.9/client 2.4.15.
- [ ] Verify version claims with ripgrep against README, Compose, and requirements.

### Task 5: Full verification

- [ ] Run backend `mvn test` and count Surefire results.
- [ ] Run AI and eval pytest suites.
- [ ] Run frontend Vitest, TypeScript check, and production build.
- [ ] Run `docker compose config --quiet`.
- [ ] Review `git diff --check`, status, and final diff.
