# Buyer Address and Checkout Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make browser location populate the saved-address form and make every buyer checkout path automatically use a saved/default address without repeated manual entry.

**Architecture:** Keep reverse-geocode normalization and checkout-address selection in small frontend helpers used by both buyer checkout pages. Pass a selected `addressId` to Spring and resolve/validate the owned saved address centrally in `OrderService`, while retaining complete legacy receiver fields for backward compatibility.

**Tech Stack:** Vue 3, TypeScript, Vitest, Spring Boot 3, Java 17, JUnit 5, Mockito.

**Spec:** User-approved design in the Codex task dated 2026-08-23.

## Global Constraints

- Location failure must preserve manual entry.
- A selected address must belong to the authenticated buyer.
- Missing checkout delivery fields must fall back to the buyer's default address.
- Existing clients that send all three receiver fields remain compatible.
- Do not modify unrelated AI/RAG or knowledge-base work already present in the workspace.

---

### Task 1: Location normalization and form population

**Files:**
- Modify: `frontend/src/components/address/addressForm.ts`
- Modify: `frontend/src/components/address/addressForm.spec.ts`
- Modify: `frontend/src/components/address/AddressBook.vue`

- [ ] Add failing tests for municipality/locality hierarchy and detail-address extraction.
- [ ] Run the focused Vitest test and confirm the expected failure.
- [ ] Implement minimal normalization and populate every usable form field.
- [ ] Re-run the focused test.

### Task 2: Shared checkout address selection

**Files:**
- Create: `frontend/src/components/address/checkoutAddress.ts`
- Create: `frontend/src/components/address/checkoutAddress.spec.ts`
- Modify: `frontend/src/views/ProductDetailView.vue`
- Modify: `frontend/src/views/CartView.vue`
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/src/types/api.d.ts`

- [ ] Test default/first-address selection and payload construction.
- [ ] Add saved-address selectors to both checkout dialogs.
- [ ] Remove repeated manual receiver fields when saved addresses exist and provide an add-address action when empty.
- [ ] Pass `addressId` in both checkout APIs and validate phone input only for legacy/manual fallback.

### Task 3: Server-side saved/default address resolution

**Files:**
- Modify: `backend/src/main/java/com/aimall/backend/address/AddressService.java`
- Modify: `backend/src/main/java/com/aimall/backend/order/OrderDtos.java`
- Modify: `backend/src/main/java/com/aimall/backend/order/OrderService.java`
- Modify: `backend/src/main/java/com/aimall/backend/cart/CartController.java`
- Test: `backend/src/test/java/com/aimall/backend/order/OrderServiceTest.java`
- Test: `backend/src/test/java/com/aimall/backend/address/AddressServiceTest.java`

- [ ] Add failing tests for selected-address ownership, default fallback, and legacy compatibility.
- [ ] Resolve delivery information before stock mutation.
- [ ] Use the resolved address in single-product and cart checkout orders.
- [ ] Run focused Maven tests.

### Task 4: Regression verification

- [ ] Run all frontend tests.
- [ ] Run the frontend production build.
- [ ] Run all backend tests.
- [ ] Inspect the final diff and confirm unrelated dirty files were not changed.
