# After-Sales Service and Workbench Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a complete after-sales workflow linked to orders and customer-service conversations, with buyer, merchant, agent, and admin collaboration and simulated refunds.

**Architecture:** A new backend `aftersale` module owns authorization, transitions, amounts, records, attachments, and conversation links. Buyer, merchant, and workbench controllers are thin adapters; Vue pages share typed helpers for labels, actions, timeout ordering, and quick replies.

**Tech Stack:** Java 21, Spring Boot 3, Spring Security, MyBatis-Plus, Flyway, MySQL, MinIO, JUnit 5/Mockito, Vue 3, TypeScript, Vue Router, Element Plus, Vitest, Vite.

**Spec:** `docs/superpowers/specs/2026-08-24-after-sales-service-design.md`

## Global Constraints

- Keep `CUSTOMER`, `MERCHANT`, `AGENT`, and `ADMIN`; add no role.
- Simulate refunds in application data only; call no payment provider.
- Reuse `ObjectStorage`; accept JPG, PNG, WEBP, at most 5 MB each and 6 files per case.
- Keep transitions and authorization inside the backend `aftersale` module.
- Never use an order's main status for item-level after-sales state.
- Use `BigDecimal` for refund calculations.
- Add no workflow engine, scheduler, logistics integration, video upload, or configurable quick-reply table.
- Preserve unrelated changes by executing in an isolated worktree.

## File Map

**Persistence:** `V6__after_sale_workflow.sql`; entities `AfterSale`, `AfterSaleRecord`, `AfterSaleAttachment`, `ConversationAfterSale`; corresponding mappers.

**Backend module:** `AfterSaleTypes`, `AfterSaleRules`, `AfterSaleDtos`, `AfterSaleService`, `AfterSaleAttachmentService`, and customer/merchant/workbench controllers under `backend/src/main/java/com/aimall/backend/aftersale/`.

**Integrations:** `SecurityConfig`, `OrderController`, `WorkbenchController`, and `WorkbenchService`.

**Frontend shared:** `frontend/src/types/api.d.ts`, `frontend/src/api/index.ts`, `frontend/src/features/afterSale.ts`, routes, and client/merchant layouts.

**Frontend pages:** buyer apply/list/detail, merchant queue, workbench queue/detail, and the enhanced conversation view.

---

### Task 1: Persist the after-sales model

**Files:**
- Create: `backend/src/main/resources/db/migration/V6__after_sale_workflow.sql`
- Create: `backend/src/main/java/com/aimall/backend/entity/AfterSale.java`
- Create: `backend/src/main/java/com/aimall/backend/entity/AfterSaleRecord.java`
- Create: `backend/src/main/java/com/aimall/backend/entity/AfterSaleAttachment.java`
- Create: `backend/src/main/java/com/aimall/backend/entity/ConversationAfterSale.java`
- Create: `backend/src/main/java/com/aimall/backend/mapper/AfterSaleMapper.java`
- Create: `backend/src/main/java/com/aimall/backend/mapper/AfterSaleRecordMapper.java`
- Create: `backend/src/main/java/com/aimall/backend/mapper/AfterSaleAttachmentMapper.java`
- Create: `backend/src/main/java/com/aimall/backend/mapper/ConversationAfterSaleMapper.java`
- Test: `backend/src/test/java/com/aimall/backend/migration/AfterSaleMigrationContractTest.java`

**Interfaces:**
- Produces four MyBatis persistence models.
- Produces `AfterSaleMapper.updateState(id, expectedStatus, nextStatus, nextHandler, agentId, enteredAt, completedAt): int`.
- Produces `sumCommittedQuantity(orderItemId): Integer` and `sumCompletedRefund(orderItemId): BigDecimal`.

- [ ] **Step 1: Write the failing migration contract test**

```java
class AfterSaleMigrationContractTest {
    private final String sql = MigrationSql.read("db/migration/V6__after_sale_workflow.sql");

    @Test void createsAllTablesAndGuardsIdentity() {
        assertAll(
            () -> assertTrue(sql.contains("CREATE TABLE after_sale")),
            () -> assertTrue(sql.contains("CREATE TABLE after_sale_record")),
            () -> assertTrue(sql.contains("CREATE TABLE after_sale_attachment")),
            () -> assertTrue(sql.contains("CREATE TABLE conversation_after_sale")),
            () -> assertTrue(sql.contains("UNIQUE KEY uk_after_sale_no")),
            () -> assertTrue(sql.contains("UNIQUE KEY uk_conversation_after_sale")));
    }
}
```

- [ ] **Step 2: Run it and confirm failure**

Run: `cd backend; mvn -Dtest=AfterSaleMigrationContractTest test`

Expected: FAIL because the migration is absent.

- [ ] **Step 3: Add schema, entities, and guarded mapper methods**

The main table includes order/item/customer/merchant IDs, fixed type/category, reason, description, quantity, requested/final refund amounts, priority, status, handler, assigned agent, return/exchange logistics, `status_entered_at`, and timestamps. Add queue indexes and unique relation key.

```java
@Update("""
 UPDATE after_sale SET status=#{nextStatus}, current_handler=#{nextHandler},
 assigned_agent_id=#{agentId}, status_entered_at=#{enteredAt},
 completed_at=#{completedAt}, updated_at=NOW()
 WHERE id=#{id} AND status=#{expectedStatus}
 """)
int updateState(Long id, String expectedStatus, String nextStatus, String nextHandler,
                Long agentId, LocalDateTime enteredAt, LocalDateTime completedAt);
```

Use `@TableName`, auto IDs, Lombok `@Data`, `LocalDateTime`, and `BigDecimal` as existing entities do.

- [ ] **Step 4: Verify persistence**

Run: `cd backend; mvn -Dtest=AfterSaleMigrationContractTest test; mvn test`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/main/resources/db/migration/V6__after_sale_workflow.sql backend/src/main/java/com/aimall/backend/entity/AfterSale*.java backend/src/main/java/com/aimall/backend/entity/ConversationAfterSale.java backend/src/main/java/com/aimall/backend/mapper/AfterSale*.java backend/src/main/java/com/aimall/backend/mapper/ConversationAfterSaleMapper.java backend/src/test/java/com/aimall/backend/migration/AfterSaleMigrationContractTest.java
git commit -m "feat(after-sale): add workflow persistence model"
```

### Task 2: Implement pure transition rules

**Files:**
- Create: `backend/src/main/java/com/aimall/backend/aftersale/AfterSaleTypes.java`
- Create: `backend/src/main/java/com/aimall/backend/aftersale/AfterSaleRules.java`
- Test: `backend/src/test/java/com/aimall/backend/aftersale/AfterSaleRulesTest.java`

**Interfaces:**
- Produces constants nested under `ServiceType`, `IssueCategory`, `Status`, `Handler`, `Priority`, and `Action`.
- Produces `initialRoute(issueCategory): Transition` and `decide(status, handler, actorRole, action, serviceType): Transition`.
- `Transition` is `(nextStatus, nextHandler, completed)`.
- Exact service types: `RETURN_REFUND`, `EXCHANGE`, `REFUND_ONLY`, `ISSUE_REPORT`; categories: `PERSONAL`, `QUALITY`, `MERCHANT`, `PLATFORM`.

- [ ] **Step 1: Write failing transition tests**

```java
@Test void routesPlatformAndQualityIssues() {
    assertEquals(new Transition("PENDING_PLATFORM", "PLATFORM", false), initialRoute("PLATFORM"));
    assertEquals(new Transition("PENDING_MERCHANT", "MERCHANT", false), initialRoute("QUALITY"));
}
@Test void rejectedBuyerCanRequestPlatform() {
    assertEquals(new Transition("PENDING_PLATFORM", "PLATFORM", false),
        decide("REJECTED", "CUSTOMER", "CUSTOMER", "REQUEST_PLATFORM", "RETURN_REFUND"));
}
@Test void merchantCannotSimulateRefund() {
    assertThrows(BizException.class, () ->
        decide("PENDING_REFUND", "PLATFORM", "MERCHANT", "SIMULATE_REFUND", "REFUND_ONLY"));
}
```

- [ ] **Step 2: Run and confirm failure**

Run: `cd backend; mvn -Dtest=AfterSaleRulesTest test`

Expected: compilation FAIL because rule types are absent.

- [ ] **Step 3: Implement the explicit state table**

Use direct branches for `APPROVE`, `REJECT`, `REQUEST_INFO`, `SUPPLY_INFO`, `SUBMIT_RETURN`, `CONFIRM_RETURN`, `SUBMIT_EXCHANGE_SHIPMENT`, `CONFIRM_EXCHANGE`, `REQUEST_PLATFORM`, `TAKE_OVER`, `SIMULATE_REFUND`, `CANCEL`, `COMPLETE`, and `TRANSFER`. Reject all unlisted tuples:

```java
throw new BizException(2001, "当前状态不允许该操作");
```

- [ ] **Step 4: Verify rules**

Run: `cd backend; mvn -Dtest=AfterSaleRulesTest test; mvn test`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/main/java/com/aimall/backend/aftersale/AfterSaleTypes.java backend/src/main/java/com/aimall/backend/aftersale/AfterSaleRules.java backend/src/test/java/com/aimall/backend/aftersale/AfterSaleRulesTest.java
git commit -m "feat(after-sale): define workflow transition rules"
```

### Task 3: Add customer creation, querying, and actions

**Files:**
- Create: `backend/src/main/java/com/aimall/backend/aftersale/AfterSaleDtos.java`
- Create: `backend/src/main/java/com/aimall/backend/aftersale/AfterSaleService.java`
- Create: `backend/src/main/java/com/aimall/backend/aftersale/CustomerAfterSaleController.java`
- Test: `backend/src/test/java/com/aimall/backend/aftersale/AfterSaleServiceTest.java`
- Test: `backend/src/test/java/com/aimall/backend/aftersale/CustomerAfterSaleControllerTest.java`
- Modify: `backend/src/main/java/com/aimall/backend/config/SecurityConfig.java`

**Interfaces:**
- Produces `create(customerId, CreateRequest): DetailVO`, `customerPage(customerId, Query): Page<SummaryVO>`, `customerDetail(customerId, id): DetailVO`, and `act(Actor, id, ActionRequest): DetailVO`.
- `Actor` contains server-derived `userId` and `role`.

- [ ] **Step 1: Write failing amount and identity tests**

```java
@Test void rejectsQuantityAboveRemainingQuantity() {
    when(orderService.requireOwned(7L, 20L)).thenReturn(deliveredOrder(20L));
    when(orderItemMapper.selectById(30L)).thenReturn(item(30L, 20L, 2, "49.90"));
    when(afterSaleMapper.sumCommittedQuantity(30L)).thenReturn(2);
    assertThrows(BizException.class, () -> service.create(7L,
        request(20L, 30L, 1, new BigDecimal("49.90"))));
}
@Test void controllerUsesAuthenticatedCustomer() {
    controller.create(7L, request);
    verify(service).create(7L, request);
}
```

- [ ] **Step 2: Run and confirm failure**

Run: `cd backend; mvn -Dtest=AfterSaleServiceTest,CustomerAfterSaleControllerTest test`

Expected: compilation FAIL.

- [ ] **Step 3: Implement validated DTOs and transactional use cases**

```java
public record CreateRequest(@NotNull Long orderId, @NotNull Long orderItemId,
 @NotBlank String serviceType, @NotBlank String issueCategory,
 @NotBlank @Size(max=100) String reason, @NotBlank @Size(max=2000) String description,
 @NotNull @Min(1) Integer quantity,
 @NotNull @DecimalMin("0.00") BigDecimal requestedRefundAmount,
Long conversationId) {}

public record ActionRequest(@NotBlank String action, @Size(max=2000) String content,
 String logisticsCompany, String trackingNo, BigDecimal finalRefundAmount,
 Long targetAgentId) {}
```

Verify ownership, order-item relation, status in `PAID/SHIPPED/DELIVERED`, remaining quantity, and refund ceiling. Insert case, initial record, and optional link in one transaction. Buyer actions: `SUPPLY_INFO`, `SUBMIT_RETURN`, `CONFIRM_EXCHANGE`, `REQUEST_PLATFORM`, `CANCEL`.

Expose `POST/GET /api/v1/after-sales`, `GET /api/v1/after-sales/{id}`, and `POST /api/v1/after-sales/{id}/actions`. Add the `CUSTOMER`/`ADMIN` security matcher.

- [ ] **Step 4: Verify customer workflow**

Run: `cd backend; mvn -Dtest=AfterSaleServiceTest,CustomerAfterSaleControllerTest test; mvn test`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/main/java/com/aimall/backend/aftersale backend/src/main/java/com/aimall/backend/config/SecurityConfig.java backend/src/test/java/com/aimall/backend/aftersale
git commit -m "feat(after-sale): add customer workflow endpoints"
```

### Task 4: Add evidence storage and conversation links

**Files:**
- Create: `backend/src/main/java/com/aimall/backend/aftersale/AfterSaleAttachmentService.java`
- Test: `backend/src/test/java/com/aimall/backend/aftersale/AfterSaleAttachmentServiceTest.java`
- Modify: `AfterSaleService.java`, `CustomerAfterSaleController.java`, `AfterSaleDtos.java`

**Interfaces:**
- Produces `upload(Actor, afterSaleId, recordId, MultipartFile): AttachmentVO`.
- Produces `download(Actor, attachmentId): StoredFile`.
- Produces `linkConversation(Actor, afterSaleId, conversationId): void`.

- [ ] **Step 1: Write failing upload and ownership tests**

```java
@Test void rejectsSeventhAttachment() {
    when(attachmentMapper.countByAfterSaleId(90L)).thenReturn(6L);
    var image = new MockMultipartFile("file", "damage.png", "image/png", new byte[]{1});
    assertThrows(BizException.class, () -> attachments.upload(customer(7L), 90L, null, image));
}
@Test void rejectsAnotherBuyersConversation() {
    when(conversationMapper.selectById(44L)).thenReturn(conversation(44L, 8L));
    assertThrows(BizException.class, () -> service.linkConversation(customer(7L), 90L, 44L));
}
```

- [ ] **Step 2: Run and confirm failure**

Run: `cd backend; mvn -Dtest=AfterSaleAttachmentServiceTest,AfterSaleServiceTest test`

Expected: FAIL because upload/link methods are absent.

- [ ] **Step 3: Implement validated storage and linking**

```java
private static final Set<String> IMAGE_TYPES = Set.of("image/jpeg", "image/png", "image/webp");
private static final long MAX_BYTES = 5L * 1024 * 1024;
private static final long MAX_FILES = 6L;
```

Use keys `after-sales/{caseId}/{uuid}.{extension}`. Store metadata only after `ObjectStorage.put` succeeds. Authorize download through the same case visibility check as detail queries. Verify that conversation and case share the buyer; rely on the relation unique key for idempotency.

Expose attachment upload/download and `POST /api/v1/after-sales/{id}/conversations/{conversationId}`.

- [ ] **Step 4: Verify**

Run: `cd backend; mvn -Dtest=AfterSaleAttachmentServiceTest,AfterSaleServiceTest test; mvn test`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/main/java/com/aimall/backend/aftersale backend/src/test/java/com/aimall/backend/aftersale
git commit -m "feat(after-sale): add evidence and conversation links"
```

### Task 5: Add merchant queue and actions

**Files:**
- Create: `backend/src/main/java/com/aimall/backend/aftersale/MerchantAfterSaleController.java`
- Test: `backend/src/test/java/com/aimall/backend/aftersale/MerchantAfterSaleControllerTest.java`
- Modify: `AfterSaleService.java`, `SecurityConfig.java`, `AfterSaleServiceTest.java`

**Interfaces:**
- Produces `merchantPage(userId, Query): Page<SummaryVO>` and `merchantDetail(userId, id): DetailVO` without internal records.
- Consumes the shared `act(Actor, id, ActionRequest)` transition seam.

- [ ] **Step 1: Write failing scope and privacy tests**

```java
@Test void merchantCannotReadAnotherStoreCase() {
    when(merchantMapper.selectByUserId(21L)).thenReturn(merchant(101L, 21L));
    when(afterSaleMapper.selectById(90L)).thenReturn(caseForMerchant(202L));
    assertThrows(BizException.class, () -> service.merchantDetail(21L, 90L));
}
@Test void merchantTimelineOmitsInternalRecords() {
    var detail = service.merchantDetail(21L, 90L);
    assertTrue(detail.records().stream().noneMatch(RecordVO::internalOnly));
}
```

- [ ] **Step 2: Run and confirm failure**

Run: `cd backend; mvn -Dtest=MerchantAfterSaleControllerTest,AfterSaleServiceTest test`

Expected: FAIL because merchant operations are absent.

- [ ] **Step 3: Implement merchant-scoped queries and actions**

Resolve the current merchant using the existing merchant lookup pattern. Add `merchant_id = currentMerchant.id` to every query. Expose list/detail/actions under `/api/v1/merchant/after-sales` and secure for `MERCHANT`/`ADMIN`.

Allow `APPROVE`, `REJECT`, `REQUEST_INFO`, `CONFIRM_RETURN`, `SUBMIT_EXCHANGE_SHIPMENT`, and `REQUEST_PLATFORM`. Require rejection content and both exchange logistics fields. Filter `internal_only = true` records from all merchant responses.

- [ ] **Step 4: Verify**

Run: `cd backend; mvn -Dtest=MerchantAfterSaleControllerTest,AfterSaleServiceTest test; mvn test`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/main/java/com/aimall/backend/aftersale backend/src/main/java/com/aimall/backend/config/SecurityConfig.java backend/src/test/java/com/aimall/backend/aftersale
git commit -m "feat(after-sale): add merchant handling queue"
```

### Task 6: Add workbench intervention, notes, refund, transfer, and stats

**Files:**
- Create: `backend/src/main/java/com/aimall/backend/aftersale/WorkbenchAfterSaleController.java`
- Test: `backend/src/test/java/com/aimall/backend/aftersale/WorkbenchAfterSaleControllerTest.java`
- Modify: `AfterSaleService.java`, `WorkbenchController.java`, `WorkbenchService.java`, `SecurityConfig.java`, `AfterSaleServiceTest.java`

**Interfaces:**
- Produces `workbenchPage(Query): Page<SummaryVO>`, `addInternalNote(Actor,id,content): RecordVO`, `enabledAgents(): List<AgentVO>`, and `stats(): AfterSaleStatsVO`.
- Consumes agent actions `TAKE_OVER`, `SIMULATE_REFUND`, `TRANSFER`, `COMPLETE`, and shared actions.

- [ ] **Step 1: Write failing idempotency and transfer tests**

```java
@Test void simulatedRefundCompletesOnlyOnce() {
    when(afterSaleMapper.updateState(eq(90L), eq("PENDING_REFUND"), eq("COMPLETED"),
        eq("PLATFORM"), eq(5L), any(), any())).thenReturn(1, 0);
    service.act(agent(5L), 90L, refund("49.90"));
    assertThrows(BizException.class, () -> service.act(agent(5L), 90L, refund("49.90")));
}
@Test void transferRejectsDisabledAgent() {
    when(userMapper.selectById(6L)).thenReturn(agentUser(6L, false));
    assertThrows(BizException.class, () -> service.act(agent(5L), 90L,
        transferTo(6L, "交由夜班继续处理")));
}
```

- [ ] **Step 2: Run and confirm failure**

Run: `cd backend; mvn -Dtest=WorkbenchAfterSaleControllerTest,AfterSaleServiceTest test`

Expected: FAIL because workbench operations are absent.

- [ ] **Step 3: Implement workbench use cases**

Expose list/stats/enabled-agents/detail/actions/internal-notes/conversation-link endpoints under `/api/v1/workbench/after-sales` for `AGENT`/`ADMIN`.

`SIMULATE_REFUND` validates `0 < final <= remaining`, saves amount and record, then performs guarded `PENDING_REFUND -> COMPLETED`; zero updated rows means conflict. `TRANSFER` requires reason and an enabled `AGENT`, updates assignment, adds an internal record and linked-conversation system message, and makes the old assignee read-only.

Compute timeout dynamically:

```java
long hours = "HIGH".equals(row.getPriority()) ? 2 : 24;
boolean timedOut = !Set.of("COMPLETED", "CANCELLED").contains(row.getStatus())
    && row.getStatusEnteredAt().plusHours(hours).isBefore(now);
```

Order queue results by timed-out first, then priority, then waiting time. Extend workbench SLA with pending and timed-out after-sales counts.

- [ ] **Step 4: Verify**

Run: `cd backend; mvn -Dtest=WorkbenchAfterSaleControllerTest,AfterSaleServiceTest test; mvn test`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/main/java/com/aimall/backend/aftersale backend/src/main/java/com/aimall/backend/workbench backend/src/main/java/com/aimall/backend/config/SecurityConfig.java backend/src/test/java/com/aimall/backend/aftersale
git commit -m "feat(after-sale): add workbench handling tools"
```

### Task 7: Add order summaries and frontend shared contracts

**Files:**
- Modify: `backend/src/main/java/com/aimall/backend/order/OrderController.java`
- Test: `backend/src/test/java/com/aimall/backend/order/OrderAfterSaleSummaryTest.java`
- Modify: `frontend/src/types/api.d.ts`
- Modify: `frontend/src/api/index.ts`
- Create: `frontend/src/features/afterSale.ts`
- Test: `frontend/src/features/afterSale.spec.ts`

**Interfaces:**
- Produces order-item fields `afterSaleStatus`, `afterSaleId`, `remainingAfterSaleQuantity`, `refundedAmount` without altering order status.
- Produces frontend types `AfterSaleSummaryVO`, `AfterSaleDetailVO`, `AfterSaleRecordVO`, `AfterSaleAttachmentVO`, `AfterSaleStatsVO`, `AfterSaleQuery`, `AfterSaleCreateRequest`, and `AfterSaleActionRequest`.
- Produces `statusText`, `serviceTypeText`, `categoryText`, `availableActions`, `isTimedOut`, `sortWorkbenchCases`, and `QUICK_REPLIES`.

- [ ] **Step 1: Write failing summary/helper tests**

```java
@Test void itemSummaryDoesNotOverwriteOrderStatus() {
    var result = summaryService.attach(List.of(order("SHIPPED")), customerId);
    assertEquals("SHIPPED", result.getFirst().status());
    assertEquals("PENDING_MERCHANT", result.getFirst().items().getFirst().afterSaleStatus());
}
```

```ts
it('orders timed-out urgent cases first', () => {
  const sorted = sortWorkbenchCases([normalCase, urgentCase], new Date('2026-08-24T12:00:00'))
  expect(sorted[0].id).toBe(urgentCase.id)
})
it('limits a rejected buyer to intervention or cancellation', () => {
  expect(availableActions('CUSTOMER', rejectedCase)).toEqual(['REQUEST_PLATFORM', 'CANCEL'])
})
```

- [ ] **Step 2: Run and confirm failure**

Run: `cd backend; mvn -Dtest=OrderAfterSaleSummaryTest test`

Run: `cd frontend; npm test -- src/features/afterSale.spec.ts`

Expected: both FAIL.

- [ ] **Step 3: Implement summaries, types, calls, and helpers**

Add buyer calls named `apiCreateAfterSale`, `apiMyAfterSales`, `apiAfterSaleDetail`, `apiAfterSaleAction`, `apiUploadAfterSaleAttachment`, and `apiLinkAfterSaleConversation`. Add equivalent merchant and workbench list/detail/action calls plus stats, enabled agents, and internal note calls.

```ts
export const apiCreateAfterSale = (body: AfterSaleCreateRequest) =>
  post<AfterSaleDetailVO>('/after-sales', body)
export const apiWorkbenchAfterSales = (params: AfterSaleQuery) =>
  get<PageResult<AfterSaleSummaryVO>>('/workbench/after-sales', { params })
```

Keep helpers pure; accept `now` for timeout functions. Add the six approved Chinese quick-reply strings as a readonly array.

- [ ] **Step 4: Verify contracts**

Run: `cd backend; mvn -Dtest=OrderAfterSaleSummaryTest test`

Run: `cd frontend; npm test -- src/features/afterSale.spec.ts; npm test; npm run build`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/main/java/com/aimall/backend/order backend/src/test/java/com/aimall/backend/order/OrderAfterSaleSummaryTest.java frontend/src/types/api.d.ts frontend/src/api/index.ts frontend/src/features
git commit -m "feat(after-sale): expose order and frontend contracts"
```

### Task 8: Build buyer pages and order entry points

**Files:**
- Create: `frontend/src/views/afterSale/AfterSaleApplyView.vue`
- Create: `frontend/src/views/afterSale/MyAfterSalesView.vue`
- Create: `frontend/src/views/afterSale/AfterSaleDetailView.vue`
- Test: `frontend/src/views/afterSale/buyerAfterSale.spec.ts`
- Modify: `frontend/src/views/MyOrdersView.vue`
- Modify: `frontend/src/views/OrderDetailView.vue`
- Modify: `frontend/src/layouts/ClientLayout.vue`
- Modify: `frontend/src/router/index.ts`

**Interfaces:**
- Consumes Task 7 buyer types/helpers/calls.
- Produces `/after-sales`, `/after-sales/apply`, and `/after-sales/:id`, all with `meta.customer=true`.

- [ ] **Step 1: Write failing route and view tests**

```ts
it('registers buyer after-sales routes', () => {
  expect(router.getRoutes().map(r => r.path)).toEqual(expect.arrayContaining([
    '/after-sales', '/after-sales/apply', '/after-sales/:id',
  ]))
})
it('application contains approved fields', () => {
  for (const field of ['serviceType', 'issueCategory', 'requestedRefundAmount']) {
    expect(applySource).toContain(field)
  }
  expect(applySource).toContain('同时创建客服会话')
})
```

- [ ] **Step 2: Run and confirm failure**

Run: `cd frontend; npm test -- src/views/afterSale/buyerAfterSale.spec.ts`

Expected: FAIL because routes/views are absent.

- [ ] **Step 3: Implement buyer forms, lists, detail, and entries**

The apply page reads `orderId`/`orderItemId`, displays the item, validates quantity/refund, creates the case, uploads evidence, and optionally creates/links a conversation. The list filters status/type and searches case number, order number, or product. The detail renders public history and only actions returned by `availableActions('CUSTOMER', detail)`.

```ts
const params = computed(() => ({
  ...(filters.status ? { status: filters.status } : {}),
  ...(filters.serviceType ? { serviceType: filters.serviceType } : {}),
  ...(filters.keyword.trim() ? { keyword: filters.keyword.trim() } : {}),
  page: page.value, size: 10,
}))
```

Add “申请售后” when remaining quantity is positive, otherwise “查看售后” when an ID exists. Add “我的售后” to buyer navigation.

- [ ] **Step 4: Verify buyer UI**

Run: `cd frontend; npm test -- src/views/afterSale/buyerAfterSale.spec.ts src/features/afterSale.spec.ts; npm test; npm run build`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/afterSale frontend/src/views/MyOrdersView.vue frontend/src/views/OrderDetailView.vue frontend/src/layouts/ClientLayout.vue frontend/src/router/index.ts
git commit -m "feat(after-sale): add buyer application and tracking pages"
```

### Task 9: Build the merchant after-sales queue

**Files:**
- Create: `frontend/src/views/merchant/MerchantAfterSalesView.vue`
- Test: `frontend/src/views/merchant/merchantAfterSales.spec.ts`
- Modify: `frontend/src/layouts/MerchantLayout.vue`
- Modify: `frontend/src/router/index.ts`

**Interfaces:**
- Consumes merchant calls and `availableActions('MERCHANT', row)`.
- Produces `/merchant/after-sales`.

- [ ] **Step 1: Write failing route/action tests**

```ts
it('adds merchant route and menu', () => {
  expect(router.getRoutes().some(r => r.path === '/merchant/after-sales')).toBe(true)
  expect(layoutSource).toContain('售后管理')
})
it('offers merchant actions but no simulated refund', () => {
  expect(viewSource).toMatch(/APPROVE|REJECT|CONFIRM_RETURN/)
  expect(viewSource).not.toMatch(/SIMULATE_REFUND/)
})
```

- [ ] **Step 2: Run and confirm failure**

Run: `cd frontend; npm test -- src/views/merchant/merchantAfterSales.spec.ts`

Expected: FAIL.

- [ ] **Step 3: Implement queue, filters, detail drawer, and action forms**

Add tabs for pending, waiting customer, returning, exchanging, and completed; keyword/type/category/status/priority filters; item, evidence, and public timeline in the drawer. Require rejection content and exchange company/tracking number.

```ts
if (action === 'REJECT' && !form.content.trim()) return ElMessage.warning('请填写拒绝原因')
if (action === 'SUBMIT_EXCHANGE_SHIPMENT' && (!form.logisticsCompany.trim() || !form.trackingNo.trim()))
  return ElMessage.warning('请填写换货物流公司和单号')
```

Reload drawer and active queue after each action.

- [ ] **Step 4: Verify merchant UI**

Run: `cd frontend; npm test -- src/views/merchant/merchantAfterSales.spec.ts src/features/afterSale.spec.ts; npm test; npm run build`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/merchant/MerchantAfterSalesView.vue frontend/src/views/merchant/merchantAfterSales.spec.ts frontend/src/layouts/MerchantLayout.vue frontend/src/router/index.ts
git commit -m "feat(after-sale): add merchant handling interface"
```

### Task 10: Enhance the workbench queue and add case detail

**Files:**
- Modify: `frontend/src/views/workbench/WorkbenchView.vue`
- Create: `frontend/src/views/workbench/WorkbenchAfterSaleView.vue`
- Test: `frontend/src/views/workbench/workbenchAfterSales.spec.ts`
- Modify: `frontend/src/router/index.ts`

**Interfaces:**
- Consumes workbench list/stats/detail/action/note/agent APIs.
- Produces `/workbench/after-sales/:id` for `AGENT`/`ADMIN`.

- [ ] **Step 1: Write failing queue/tool tests**

```ts
it('shows after-sales stats and filters', () => {
  for (const text of ['待处理售后', '超时售后', '问题分类', '优先级']) {
    expect(workbenchSource).toContain(text)
  }
})
it('case detail exposes all agent tools', () => {
  for (const text of ['平台介入', '内部备注', '模拟退款', '转交客服', '修改优先级']) {
    expect(detailSource).toContain(text)
  }
})
```

- [ ] **Step 2: Run and confirm failure**

Run: `cd frontend; npm test -- src/views/workbench/workbenchAfterSales.spec.ts`

Expected: FAIL.

- [ ] **Step 3: Implement queue and standalone detail**

Add a “售后队列” tab, search, status/category/priority/handler/timeout filters, new SLA cards, timeout badges, and stable fallback sorting. The detail renders evidence, public/internal timeline, assignee, linked conversations, priority selector, internal note, intervention/status forms, refund dialog, and transfer dialog.

Only enable refund in `PENDING_REFUND`; require transfer reason and prevent selecting the current agent.

- [ ] **Step 4: Verify workbench UI**

Run: `cd frontend; npm test -- src/views/workbench/workbenchAfterSales.spec.ts src/features/afterSale.spec.ts; npm test; npm run build`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/workbench/WorkbenchView.vue frontend/src/views/workbench/WorkbenchAfterSaleView.vue frontend/src/views/workbench/workbenchAfterSales.spec.ts frontend/src/router/index.ts
git commit -m "feat(after-sale): add workbench queue and case tools"
```

### Task 11: Add conversation context, side panel, and quick replies

**Files:**
- Modify: `backend/src/main/java/com/aimall/backend/workbench/WorkbenchController.java`
- Modify: `backend/src/main/java/com/aimall/backend/workbench/WorkbenchService.java`
- Test: `backend/src/test/java/com/aimall/backend/workbench/WorkbenchContextTest.java`
- Modify: `frontend/src/views/workbench/WorkbenchConvView.vue`
- Test: `frontend/src/views/workbench/workbenchConversationTools.spec.ts`

**Interfaces:**
- Produces `GET /api/v1/workbench/conversations/{id}/context` with buyer, five recent orders, linked cases, and assignment.
- Consumes quick replies, case link/create/action, agent list, and internal note calls.

- [ ] **Step 1: Write failing context and UI tests**

```java
@Test void contextContainsOnlyConversationBuyersOrders() {
    var context = service.context(agentId, conversationId);
    assertEquals(conversationBuyerId, context.buyer().id());
    assertTrue(context.recentOrders().stream()
        .allMatch(order -> order.userId().equals(conversationBuyerId)));
}
```

```ts
it('renders chat tools and context panel', () => {
  for (const text of ['快捷回复', '买家信息', '最近订单', '关联售后', '内部备注', '转交客服']) {
    expect(source).toContain(text)
  }
})
```

- [ ] **Step 2: Run and confirm failure**

Run: `cd backend; mvn -Dtest=WorkbenchContextTest test`

Run: `cd frontend; npm test -- src/views/workbench/workbenchConversationTools.spec.ts`

Expected: both FAIL.

- [ ] **Step 3: Implement context and responsive two-column view**

Resolve the conversation first, then query only that buyer's five recent orders and linked cases. Return assignment so transferred conversations become read-only for the old agent.

```css
.conv-body { display:grid; grid-template-columns:minmax(0,1fr) 340px; min-height:0; flex:1; }
@media (max-width:900px) { .conv-body { grid-template-columns:1fr; } .context-panel { max-height:42vh; } }
```

Quick replies insert but do not send. The panel creates a case from an order item, links an existing buyer-owned case, adds internal notes, opens case detail, and transfers with reason. Preserve 3-second message/status polling; refresh context only after panel mutations.

- [ ] **Step 4: Verify conversation tools**

Run: `cd backend; mvn -Dtest=WorkbenchContextTest test; mvn test`

Run: `cd frontend; npm test -- src/views/workbench/workbenchConversationTools.spec.ts src/features/afterSale.spec.ts; npm test; npm run build`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/main/java/com/aimall/backend/workbench backend/src/test/java/com/aimall/backend/workbench/WorkbenchContextTest.java frontend/src/views/workbench/WorkbenchConvView.vue frontend/src/views/workbench/workbenchConversationTools.spec.ts
git commit -m "feat(workbench): link conversations and after-sales cases"
```

### Task 12: Verify complete workflows and document them

**Files:**
- Create: `backend/src/test/java/com/aimall/backend/aftersale/AfterSaleWorkflowIntegrationTest.java`
- Modify: `README.md`

**Interfaces:**
- Consumes all prior slices.
- Produces one repeatable integration test for return/refund and rejected-case intervention.

- [ ] **Step 1: Write the failing integration workflow**

```java
@Test void refundAndInterventionDoNotChangeOrderStatus() {
    long id = fixtures.customerCreatesQualityReturn();
    fixtures.merchantApproves(id);
    fixtures.customerSubmitsReturn(id, "顺丰", "SF10001");
    fixtures.merchantConfirmsReturn(id);
    fixtures.agentSimulatesRefund(id, new BigDecimal("49.90"));
    assertEquals("COMPLETED", fixtures.caseDetail(id).status());
    assertEquals(new BigDecimal("49.90"), fixtures.caseDetail(id).finalRefundAmount());
    assertEquals("SHIPPED", fixtures.orderDetail().status());

    long rejected = fixtures.customerCreatesMerchantComplaint();
    fixtures.merchantRejects(rejected, "现有凭证无法确认问题");
    fixtures.customerRequestsPlatform(rejected);
    assertEquals("PENDING_PLATFORM", fixtures.caseDetail(rejected).status());
}
```

Keep fixture methods private to the test class and follow the repository's existing Spring/database test pattern.

- [ ] **Step 2: Run and correct only cross-slice contract defects**

Run: `cd backend; mvn -Dtest=AfterSaleWorkflowIntegrationTest test`

Expected initially: FAIL at any mismatched interface. Correct the owning module with the smallest change and rerun after each correction.

- [ ] **Step 3: Document the workflow**

Add:

```markdown
## 售后服务

- 买家可从订单商品发起退货退款、换货、仅退款或问题反馈。
- 个人、质量和卖家问题默认由卖家处理，平台问题及争议由客服处理。
- 客服工作台可关联会话与售后单、添加内部备注、转交、介入并执行模拟退款。
- 模拟退款只更新业务状态，不连接真实支付渠道。
```

Extend the README verification checklist with both integration paths.

- [ ] **Step 4: Run final verification**

Run: `cd backend; mvn test`

Run: `cd frontend; npm test; npm run build`

Run: `git diff --check`

Expected: all tests/build PASS and no whitespace errors.

- [ ] **Step 5: Commit**

```bash
git add backend/src/test/java/com/aimall/backend/aftersale/AfterSaleWorkflowIntegrationTest.java README.md
git commit -m "test(after-sale): verify complete service workflow"
```

## Final Acceptance Checklist

- [ ] No role beyond the existing four was added.
- [ ] Buyer can create, search, inspect, supplement, cancel, return, intervene, and contact support.
- [ ] Merchant sees only its store and can approve, reject, request information, confirm returns, ship replacements, reply, and request platform help.
- [ ] Agent can filter/prioritize, inspect context, use quick replies, add private notes, link/create cases, intervene, transfer, simulate refunds, and finish work.
- [ ] Internal notes never appear in buyer or merchant responses.
- [ ] Refund amount and quantity limits hold across multiple cases.
- [ ] Concurrent state changes and repeated simulated refunds fail safely.
- [ ] Order status remains independent from item-level after-sales state.
- [ ] Evidence limits and authorized downloads are server-enforced.
- [ ] Backend tests, frontend tests, frontend build, and `git diff --check` pass.
