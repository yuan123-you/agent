# Agent Human-in-the-loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a durable buyer approval/rejection flow with an editable delivery form for Agent-prepared orders.

**Architecture:** Keep LangGraph responsible for routing and tool selection while treating the MySQL `agent_action` PENDING record as the durable human interrupt. The frontend sends the authenticated buyer's decision and approved form values to Spring, which performs the guarded transition and order creation.

**Tech Stack:** LangGraph/LangChain Python service, Spring Boot 3/Java 17/MyBatis Plus, Vue 3/Pinia/Element Plus/TypeScript, JUnit 5/Mockito, Vitest.

**Spec:** `docs/superpowers/plans/2026-08-24-agent-hitl-design.md`

## Global Constraints

- Do not overwrite unrelated working-tree changes.
- Never trust a user ID supplied by the browser or model.
- A cancellation must be persisted by the backend.
- Confirmation must revalidate ownership, status, expiry, product availability, and current price.
- Product and quantity cannot be changed by the approval form.

---

### Task 1: Backend approval contract

**Files:**
- Modify: `backend/src/main/java/com/aimall/backend/mapper/AgentActionMapper.java`
- Modify: `backend/src/main/java/com/aimall/backend/internal/AgentOrderActionService.java`
- Modify: `backend/src/main/java/com/aimall/backend/order/OrderActionController.java`
- Test: `backend/src/test/java/com/aimall/backend/internal/AgentOrderActionServiceTest.java`
- Test: `backend/src/test/java/com/aimall/backend/order/OrderActionControllerTest.java`

**Interfaces:**
- Produces: `confirm(userId, actionId, ApprovalRequest)` and `cancel(userId, actionId)`.
- Approval fields: `receiverName`, `receiverPhone`, `receiverAddress`.

- [x] Write failing service tests for edited delivery data and persisted cancellation.
- [x] Write failing controller tests proving authenticated identity and request forwarding.
- [x] Run focused Maven tests and confirm failure.
- [x] Implement minimal mapper/service/controller changes.
- [x] Run focused Maven tests and confirm pass.

### Task 2: Frontend HITL state and API

**Files:**
- Modify: `frontend/src/types/api.d.ts`
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/src/stores/chat.ts`
- Test: `frontend/src/stores/chat.spec.ts`

**Interfaces:**
- Consumes: backend confirm/cancel endpoints.
- Produces: `confirmOrderAction(actionId, form)` and async `cancelOrderAction(actionId)`.

- [x] Write failing store tests for approval form forwarding and backend cancellation.
- [x] Run focused Vitest and confirm failure.
- [x] Implement the API and store state transitions.
- [x] Run focused Vitest and confirm pass.

### Task 3: Approval dialog

**Files:**
- Modify: `frontend/src/components/chat/ToolCallCard.vue`
- Modify: `frontend/src/components/chat/AiMessage.vue`

**Interfaces:**
- Emits the action ID plus editable receiver fields on confirm.
- Emits the action ID on cancel.

- [x] Replace immediate confirmation with an Element Plus review dialog.
- [x] Prefill receiver fields from the prepared action.
- [x] Add required-field and mobile layout behavior.
- [x] Verify TypeScript production build.

### Task 4: End-to-end verification

**Files:**
- No production files expected.

- [x] Run AI-service tests to ensure Agent action emission still works.
- [x] Run backend focused tests, then backend test suite.
- [x] Run frontend tests and production build.
- [x] Review the final diff for unrelated edits and security regressions.
