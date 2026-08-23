# Two-Stage AI Ordering and Saved Addresses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make AI ordering prepare-only until explicit confirmation, emit structured action SSE events, and let customers save a reusable default province/city/district delivery address from the profile page.

**Architecture:** The Spring backend remains the owner of saved addresses and pending order actions. The Python AI tool requests `/internal/tool/order/prepare`, captures the returned action in request context, and the chat stream emits it as a dedicated SSE event. Vue renders the action card and confirms through a customer-authenticated backend endpoint; address UI is extracted into a reusable component and stores structured regions while retaining a composed legacy address string.

**Tech Stack:** Java 17, Spring Boot 3, MyBatis-Plus, Flyway, Python/FastAPI/LangChain, Vue 3/TypeScript, Element Plus, Vitest, JUnit 5, pytest.

**Spec:** User-approved design in the Codex task dated 2026-08-23.

## Global Constraints

- An order-intent turn may create only a pending action; it must not create an order.
- The AI model must never invoke order confirmation.
- The chat stream must carry confirmation data in a standalone `action` SSE event.
- Missing explicit delivery data must resolve from the authenticated user's default saved address.
- No default address must produce an actionable error instead of an incomplete pending action.
- Location failure must not prevent manual address entry.
- Existing combined `receiverAddress` consumers remain compatible.

---

### Task 1: Saved-address domain and default resolution

**Files:**
- Create: `backend/src/main/resources/db/migration/V6__structured_user_address.sql`
- Modify: `backend/src/main/java/com/aimall/backend/entity/Address.java`
- Modify: `backend/src/main/java/com/aimall/backend/address/AddressDtos.java`
- Modify: `backend/src/main/java/com/aimall/backend/address/AddressController.java`
- Modify: `backend/src/main/java/com/aimall/backend/address/AddressService.java`
- Test: `backend/src/test/java/com/aimall/backend/address/AddressServiceTest.java`
- Test: `backend/src/test/java/com/aimall/backend/migration/FlywayMigrationContractTest.java`

**Interfaces:**
- Produces `AddressService.defaultFor(Long userId)` and structured address response fields.
- Persists province, city, district, and detail address while composing `receiverAddress`.

- [ ] Write failing service tests for first/default selection, structured composition, and missing default.
- [ ] Run the focused Maven tests and verify expected failures.
- [ ] Add the migration, entity/DTO fields, service behavior, and response fields.
- [ ] Re-run focused Maven tests and verify they pass.

### Task 2: Prepare-only AI order tool with default-address fallback

**Files:**
- Modify: `backend/src/main/java/com/aimall/backend/internal/AgentOrderActionService.java`
- Modify: `backend/src/test/java/com/aimall/backend/internal/AgentOrderActionServiceTest.java`
- Modify: `ai-service/app/clients/backend_client.py`
- Modify: `ai-service/app/tools/tools.py`
- Test: `ai-service/tests/test_order_action.py`

**Interfaces:**
- `BackendClient.order_prepare(...) -> dict` posts to `/internal/tool/order/prepare`.
- `order_create(...)` retains the LLM-facing name but returns a pending action summary and records it in tool context.

- [ ] Write failing Java tests for default-address fallback and no-default rejection.
- [ ] Write failing Python tests proving `order_create` calls prepare and never confirm/create.
- [ ] Run focused tests and verify expected failures.
- [ ] Implement minimal fallback and prepare client/tool behavior.
- [ ] Re-run focused tests and verify they pass.

### Task 3: Prompt and standalone action SSE

**Files:**
- Modify: `ai-service/app/agent/prompts.py`
- Modify: `ai-service/app/api/chat.py`
- Modify: `ai-service/app/sse.py`
- Test: `ai-service/tests/test_order_action.py`

**Interfaces:**
- Emits `event: action` with `{type, actionId, productName, quantity, amount, receiverName, receiverPhone, receiverAddress, expiresAt}`.

- [ ] Add failing stream/helper tests for standalone action events and action extraction.
- [ ] Run focused pytest and verify expected failures.
- [ ] Capture prepared actions in request tool context and emit each as an `action` event before `done`.
- [ ] Update the shopping prompt to request confirmation-card output and prohibit autonomous confirm.
- [ ] Re-run focused pytest and verify it passes.

### Task 4: Explicit confirmation API and frontend action card

**Files:**
- Create: `backend/src/main/java/com/aimall/backend/order/OrderActionController.java`
- Create: `backend/src/test/java/com/aimall/backend/order/OrderActionControllerTest.java`
- Create: `frontend/src/components/chat/OrderActionCard.vue`
- Modify: `frontend/src/types/api.d.ts`
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/src/composables/useSseChat.ts`
- Modify: `frontend/src/views/ChatView.vue`
- Test: `frontend/src/composables/useSseChat.spec.ts`

**Interfaces:**
- `POST /api/v1/order-actions/{actionId}/confirm` uses the authenticated principal.
- `SseHandlers.onAction(action)` receives typed pending action data.

- [ ] Add failing backend controller and frontend SSE parser tests.
- [ ] Run focused tests and verify expected failures.
- [ ] Add authenticated confirmation endpoint and typed action handler.
- [ ] Render a confirmation card whose button calls the explicit endpoint exactly once.
- [ ] Re-run focused tests and verify they pass.

### Task 5: Reusable profile address component

**Files:**
- Create: `frontend/src/components/address/AddressBook.vue`
- Create: `frontend/src/components/address/addressForm.ts`
- Create: `frontend/src/components/address/addressForm.spec.ts`
- Modify: `frontend/src/views/AddressesView.vue`
- Modify: `frontend/src/views/ProfileView.vue`
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/src/types/api.d.ts`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`

**Interfaces:**
- Reusable `AddressBook` manages list/add/edit/delete/default.
- Pure helpers compose structured region + detail address and normalize reverse-geocode results.

- [ ] Add failing helper tests for address composition and location normalization.
- [ ] Run Vitest and verify expected failures.
- [ ] Add China region data dependency and implement the compact address-book component.
- [ ] Embed it in Profile and make the existing address route reuse it.
- [ ] Re-run Vitest and verify it passes.

### Task 6: Full verification

**Files:**
- Verify all files above.

- [ ] Run all backend Maven tests.
- [ ] Run all AI pytest tests.
- [ ] Run all frontend Vitest tests.
- [ ] Run the frontend production build.
- [ ] Review output for errors/warnings and inspect the final diff/file list.
