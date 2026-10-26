# Commerce Consistency Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Reproduce and fix reviewed-order navigation, and audit API boundaries, authorization, idempotency and database consistency.
**Architecture:** Preserve Vue/Spring/MyBatis and the existing one-review-per-user/product rule. Use surgical fixes with regressions first; SQL tests for persistence claims, not mocks alone.
**Tech Stack:** Vue 3, Vitest/jsdom, Java 17, Spring Boot, MyBatis Plus, Maven/JUnit, H2.
**Spec:** User incident and audit request in this chat, 2026-10-26.

## Global Constraints
- No production writes/deployments, secret disclosure or destructive cleanup.
- No speculative refactoring or silent changes to ambiguous business rules.
- Reproduce each bug in a failing test before implementation; verify after.
- Distinguish verified defects from possible risks; H2 is not production MySQL proof.

### Task 1: Review/navigation (main worker)
**Files:** frontend/src/views/{MyOrdersView,OrderDetailView}.vue; frontend/src/api/index.ts; frontend/src/types/api.d.ts; backend/src/main/java/com/aimall/backend/{product/ReviewController,order/OrderController}.java; corresponding tests.
**Interfaces:** Backward-compatible per-item reviewed/canReview metadata; retain per-user/product uniqueness, add purchase evidence.
- [x] Reproduce query replay, failure-as-success, repeat submit and asynchronous refresh races in Vitest.
- [x] Test review ownership/eligibility, duplicate writes and pagination boundaries.
- [x] Minimally fix persisted review state, one-shot navigation intent, honest errors and request lifecycle.
- [x] Run targeted frontend/backend tests and frontend build.

### Task 2: Order/inventory (parallel worker)
**Files:** order service/mappers, internal order action and related tests; exclude OrderController.java.
- [x] Trace ownership, transitions, inventory and commit-time notifications.
- [x] Regression-first fixes for confirmed defects, rollback/concurrency tests where practical.

### Task 3: Cart/address/promotion (parallel worker)
**Files:** these modules, their dedicated mappers and tests.
- [x] Check quantity boundaries, authorization, duplicate checkout/claims and default-address invariants.
- [x] Regression-first minimal fixes for confirmed failures.

### Task 4: Remaining breadth audit (read-only parallel worker)
**Files:** auth/config/admin/merchant/chat/workbench/internal non-order, ai-service and corresponding pages.
- [x] Inspect authorization, contracts, resource bounds, sensitive outputs.
- [x] Report exact paths, trigger conditions and existing protections; label unverified risks.

### Task 5: Integrate and hand off
**Files:** docs/audits/2026-10-26-commerce-consistency.md.
- [x] Review diffs and run complete relevant tests/build.
- [x] Document evidence, coverage, fixed problems, results, production limits and unresolved business questions.
- [x] Summarize in Chinese without claiming production repair or exhaustive correctness.

## Execution notes

- Breadth audit produced confirmed P1 auth/workbench issues and KB version races. These were fixed regression-first in bounded disjoint write sets.
- Integration review found five additional review/confirmation timing omissions; all received failing component tests before fixes.
- Final original-project verification: backend 664 passed; frontend 252 passed; AI 298 passed; credential hygiene 8 passed; TypeScript/build/diff checks succeeded.
- Production verification and unresolved business decisions remain explicitly listed in docs/audits/2026-10-26-commerce-consistency.md; they are not claimed complete.
