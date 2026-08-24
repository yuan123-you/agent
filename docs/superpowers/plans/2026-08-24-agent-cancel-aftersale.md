# Agent Cancel and After-Sale Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add durable buyer confirmation for Agent-prepared cancellation and after-sale requests.

**Architecture:** Extend the existing `agent_action` state machine and confirmation endpoint; create one minimal after-sale aggregate on confirmation.

**Tech Stack:** Spring Boot/MyBatis/Flyway, FastAPI/LangChain tools, Vue/Pinia/Vitest.

**Spec:** `docs/superpowers/specs/2026-08-24-agent-cancel-aftersale-design.md`

## Global Constraints
- Agent tools never directly cancel an order or create an after-sale case.
- Authenticated buyer identity overrides all model input.
- Confirmation revalidates mutable business state under an action row lock.
- Existing order-create confirmation remains compatible.

### Task 1: Persistence and backend state machine
- [ ] Add failing migration and service tests.
- [ ] Add `target_order_id`, `after_sale`, entity/mapper, prepare and confirm methods.
- [ ] Generalize action status/rejection and confirmation response.
- [ ] Run focused and full backend tests.

### Task 2: Agent tools
- [ ] Add failing Python tests for prepare-only callbacks and action events.
- [ ] Add backend client methods, LangChain tools, previews, and prompt guidance.
- [ ] Run focused and full AI tests.

### Task 3: Buyer confirmation UI
- [ ] Add failing frontend contract/store tests for all action types.
- [ ] Add action unions, generic API response handling, and type-specific cards.
- [ ] Run Vitest, TypeScript, and production build.

### Task 4: Full verification
- [ ] Run backend, AI, eval, frontend, Compose, and diff checks.
