# Administrator Users and Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add agent creation, separate buyer/seller self-registration, role-tabbed user management, an admin operations dashboard, and remove admin product editing.

**Architecture:** Add focused Spring services for registration, admin users, and dashboard aggregation while preserving the current entities and `MERCHANT` role code. Add typed Vue API/view-model helpers so form, tab, and dashboard behavior is testable independently from Element Plus views.

**Tech Stack:** Java 17, Spring Boot 3.3.5, MyBatis-Plus 3.5.7, JUnit 5/Mockito, Vue 3.5, TypeScript 5, Pinia, Vue Router, Element Plus, Vitest, Vite 6.

**Spec:** `docs/superpowers/specs/2026-08-23-admin-users-dashboard-design.md`

## Global Constraints

- Keep internal role code `MERCHANT`; all visible role copy is “卖家”.
- Admins create only `AGENT`; buyers and sellers self-register separately.
- Admin lists exclude `ADMIN`; no admin API mutates roles.
- Admin products retain create/search/filter/status but not edit; seller product editing stays.
- Dashboard uses Asia/Shanghai today and inclusive trailing seven days; money uses `BigDecimal`; empty values are zero/arrays.
- Follow RED-GREEN-REFACTOR for every production change and never commit secrets, environments, logs, dependencies, or build output.

## File Map

- Registration: create `backend/.../auth/RegistrationService.java`; modify `AuthDtos.java`, `AuthController.java`, `AuthService.java`; add `RegistrationServiceTest.java`, `AuthControllerTest.java`.
- Admin users: create `backend/.../admin/AdminUserService.java`; modify `AdminUserController.java`; add service/controller tests.
- Dashboard: create `AdminDashboardService.java`, `AdminDashboardController.java`; extend user/product/order/conversation/message mappers; add dashboard tests.
- Frontend: modify API/types/auth store/login/router/layout/admin views; create pure helpers and specs for registration, user tabs, and dashboard.
- Documentation: update README, PRD, API, and frontend design docs after behavior passes.

---

### Task 1: Transactional Buyer and Seller Registration

**Files:**
- Create: `backend/src/main/java/com/aimall/backend/auth/RegistrationService.java`
- Modify: `backend/src/main/java/com/aimall/backend/auth/AuthDtos.java`
- Modify: `backend/src/main/java/com/aimall/backend/auth/AuthController.java`
- Modify: `backend/src/main/java/com/aimall/backend/auth/AuthService.java`
- Test: `backend/src/test/java/com/aimall/backend/auth/RegistrationServiceTest.java`
- Test: `backend/src/test/java/com/aimall/backend/auth/AuthControllerTest.java`

**Interfaces:**
- Consumes: `UserMapper`, `MerchantMapper`, `PasswordEncoder`.
- Produces: `registerCustomer(CustomerRegisterRequest): Long`, transactional `registerMerchant(MerchantRegisterRequest): Long`, and `/auth/register/customer|merchant`; legacy `/auth/register` remains a buyer alias.

- [ ] **Step 1: Write failing service tests**

```java
@Test void registersMerchantAndShopTogether() {
  when(userMapper.selectCount(any())).thenReturn(0L);
  when(userMapper.insert(any())).thenAnswer(i -> { i.<User>getArgument(0).setId(12L); return 1; });
  service.registerMerchant(merchantRequest("seller01", "源选店"));
  verify(userMapper).insert(argThat(u -> "MERCHANT".equals(u.getRole())));
  verify(merchantMapper).insert(argThat(m -> m.getUserId() == 12L && "源选店".equals(m.getShopName()) && "ACTIVE".equals(m.getStatus())));
}
@Test void rejectsDuplicateUsername() {
  when(userMapper.selectCount(any())).thenReturn(1L);
  assertThatThrownBy(() -> service.registerCustomer(customerRequest("buyer01")))
      .isInstanceOf(BizException.class).hasMessageContaining("用户名已存在");
  verify(userMapper, never()).insert(any());
}
```

Also assert buyer role/status are `CUSTOMER/ACTIVE`; annotate merchant registration `@Transactional` so a merchant insert exception rolls back the user insert in an integration transaction.

- [ ] **Step 2: Run RED**

Run: `cd backend; mvn -Dtest=RegistrationServiceTest test`
Expected: compile failure because service/request types do not exist.

- [ ] **Step 3: Implement minimum service and DTOs**

Create validated common fields (username 4–32 word chars, password 6–32, nickname max 32, optional phone) and merchant `@NotBlank @Size(max=64) shopName`. Centralize duplicate check and user insertion; trim text, hash password, fix role/status. Merchant flow inserts `Merchant(userId, shopName, ACTIVE)` in one transaction.

- [ ] **Step 4: Verify GREEN**

Run: `cd backend; mvn -Dtest=RegistrationServiceTest test`
Expected: PASS.

- [ ] **Step 5: Write controller RED tests**

```java
mockMvc.perform(post("/api/v1/auth/register/merchant").contentType(APPLICATION_JSON)
 .content("""{"username":"seller01","password":"123456","nickname":"店主","shopName":"源选店"}"""))
 .andExpect(status().isOk()).andExpect(jsonPath("$.data.user.role").value("MERCHANT"));
```

Also test empty `shopName` is 400 and customer/legacy routes return `CUSTOMER`.

- [ ] **Step 6: Add endpoints, rerun, commit**

Run: `cd backend; mvn -Dtest=RegistrationServiceTest,AuthControllerTest test`
Expected: PASS.

```powershell
git add backend/src/main/java/com/aimall/backend/auth backend/src/test/java/com/aimall/backend/auth
git commit -m "feat: add buyer and seller registration"
```

---

### Task 2: Agent-Only Admin User Management API

**Files:**
- Create: `backend/src/main/java/com/aimall/backend/admin/AdminUserService.java`
- Modify: `backend/src/main/java/com/aimall/backend/admin/AdminUserController.java`
- Test: `backend/src/test/java/com/aimall/backend/admin/AdminUserServiceTest.java`
- Test: `backend/src/test/java/com/aimall/backend/admin/AdminUserControllerTest.java`

**Interfaces:**
- Produces: `createAgent(CreateAgentRequest): Long`, `list(role, keyword, page, size)`, `updateStatus(operatorId,targetId,status)`; routes `POST /admin/users/agents`, `PUT /admin/users/{id}/status`.

- [ ] **Step 1: Write service RED tests**

```java
service.createAgent(agentRequest("agent02"));
verify(userMapper).insert(argThat(u -> "AGENT".equals(u.getRole()) && "ACTIVE".equals(u.getStatus())));
assertThatThrownBy(() -> service.list("ADMIN", null, 1, 20)).isInstanceOf(BizException.class);
service.updateStatus(1L, 22L, "DISABLED");
verify(userMapper).updateById(argThat(u -> u.getId() == 22L && u.getRole() == null));
```

Also test query always excludes `ADMIN`, accepts only CUSTOMER/MERCHANT/AGENT, rejects admin/self targets and invalid statuses.

- [ ] **Step 2: Run RED**

Run: `cd backend; mvn -Dtest=AdminUserServiceTest test`
Expected: missing-service compile failure.

- [ ] **Step 3: Implement service**

Use a role filter allowlist, query wrapper `ne(User::getRole,"ADMIN")`, existing masked user VO shape, fixed AGENT insertion, and status-only update entity. Throw `BizException` rather than silently ignoring illegal input.

- [ ] **Step 4: Verify service GREEN and add HTTP tests**

Test agent POST and status PUT JSON contracts; test that old role-only PUT can no longer mutate a role. Run the HTTP tests once for RED, then make the controller thin and remove role from update DTO.

Run: `cd backend; mvn -Dtest=AdminUserServiceTest,AdminUserControllerTest test`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/src/main/java/com/aimall/backend/admin/AdminUser* backend/src/test/java/com/aimall/backend/admin/AdminUser*
git commit -m "feat: restrict admin user management to agents"
```

---

### Task 3: Separate Buyer and Seller Registration UI

**Files:**
- Modify: `frontend/src/api/index.ts`, `frontend/src/types/api.d.ts`, `frontend/src/stores/auth.ts`, `frontend/src/views/LoginView.vue`
- Create: `frontend/src/views/auth/registration.ts`
- Test: `frontend/src/views/auth/registration.spec.ts`

**Interfaces:**
- Produces: `registerCustomer`, `registerMerchant`, `RegistrationKind`, validation/payload helpers.

- [ ] **Step 1: Write helper RED tests**

```ts
expect(validateRegistration('CUSTOMER', baseForm())).toEqual([])
expect(validateRegistration('MERCHANT', baseForm())).toContain('请输入店铺名称')
expect(buildRegistrationPayload('MERCHANT', {...baseForm(), shopName:' 源选店 '}))
  .toMatchObject({shopName:'源选店'})
```

Run: `cd frontend; npm test -- src/views/auth/registration.spec.ts`
Expected: module-not-found RED.

- [ ] **Step 2: Implement helpers and typed APIs/store actions**

Define `CustomerRegistration` and `MerchantRegistration extends CustomerRegistration { shopName: string }`; add POST functions for both endpoints and Pinia actions.

- [ ] **Step 3: Verify GREEN and update view**

Run helper/store specs. Add buyer/seller sub-tabs under registration; render shop name only for seller, dispatch matching action, reset to login after success, and show demo role as “卖家”.

- [ ] **Step 4: Build and commit**

Run: `cd frontend; npm test -- src/views/auth/registration.spec.ts src/stores/auth.spec.ts; npm run build`
Expected: PASS/build success.

```powershell
git add frontend/src/api frontend/src/types frontend/src/stores frontend/src/views/auth frontend/src/views/LoginView.vue
git commit -m "feat: separate buyer and seller registration"
```

---

### Task 4: Tabbed Admin User Management UI

**Files:**
- Create: `frontend/src/views/admin/userManagement.ts`
- Test: `frontend/src/views/admin/userManagement.spec.ts`
- Modify: `frontend/src/views/admin/UserManageView.vue`, `frontend/src/api/index.ts`

**Interfaces:**
- Consumes: role-filtered list, agent creation, status-only APIs.
- Produces: `USER_TABS`, `roleText`, `canCreateAgent`, role-isolated infinite lists.

- [ ] **Step 1: Write helper RED tests**

```ts
expect(USER_TABS.map(t => t.role)).toEqual(['CUSTOMER','MERCHANT','AGENT'])
expect(roleText('MERCHANT')).toBe('卖家')
expect(canCreateAgent('AGENT')).toBe(true)
expect(canCreateAgent('CUSTOMER')).toBe(false)
```

Run: `cd frontend; npm test -- src/views/admin/userManagement.spec.ts`
Expected: module-not-found RED.

- [ ] **Step 2: Implement helper and APIs**

Add `apiAdminAgentCreate(payload)` and `apiAdminUserStatus(id,'ACTIVE'|'DISABLED')`; remove `apiAdminUserUpdate` after callers are migrated.

- [ ] **Step 3: Verify GREEN and refactor view**

Add Element Plus tabs; always send active role, clear/reload on switch, remove role select and `changeRole`, retain status toggle. Show validated create-agent dialog only in AGENT tab; close/reset/reload after success.

- [ ] **Step 4: Test/build/commit**

Run: `cd frontend; npm test -- src/views/admin/userManagement.spec.ts; npm run build`
Expected: PASS/build success.

```powershell
git add frontend/src/api/index.ts frontend/src/views/admin/UserManageView.vue frontend/src/views/admin/userManagement.*
git commit -m "feat: split admin users into role tabs"
```

---

### Task 5: Admin Dashboard Aggregation API

**Files:**
- Create: `backend/src/main/java/com/aimall/backend/admin/AdminDashboardService.java`
- Create: `backend/src/main/java/com/aimall/backend/admin/AdminDashboardController.java`
- Modify: `backend/src/main/java/com/aimall/backend/mapper/UserMapper.java`, `ProductMapper.java`, `OrderInfoMapper.java`, `ConversationMapper.java`, `MessageMapper.java`
- Modify: `backend/src/main/java/com/aimall/backend/admin/StatsController.java`
- Test: `backend/src/test/java/com/aimall/backend/admin/AdminDashboardServiceTest.java`
- Test: `backend/src/test/java/com/aimall/backend/admin/AdminDashboardControllerTest.java`

**Interfaces:**
- Produces: `DashboardVO dashboard()` with summary, 7-day trend, statuses, operations, AI quality, top questions, tool calls; `GET /api/v1/admin/dashboard`.

- [ ] **Step 1: Write service RED tests with a fixed clock**

```java
DashboardVO result = service.dashboard();
assertThat(result.summary().todayGmv()).isEqualByComparingTo("2999.00");
assertThat(result.orderTrend()).hasSize(7);
assertThat(result.orderTrend().get(0).date()).isEqualTo(LocalDate.of(2026,8,17));
assertThat(result.orderTrend().get(1).orderCount()).isZero();
assertThat(result.aiQuality().totalTokens()).isEqualTo(1234L);
```

Mock clock at `2026-08-23T12:00+08:00`. Add empty-data assertions for complete zero/non-null response.

Run: `cd backend; mvn -Dtest=AdminDashboardServiceTest test`
Expected: missing-class RED.

- [ ] **Step 2: Add exact mapper queries**

```java
@Select("SELECT COUNT(*) FROM sys_user WHERE deleted=0 AND role<>'ADMIN'") long countPlatformUsers();
@Select("SELECT COUNT(*) FROM sys_user WHERE deleted=0 AND role='MERCHANT'") long countMerchants();
@Select("SELECT COUNT(*) FROM product WHERE deleted=0 AND status='ON_SALE'") long countOnSale();
```

Order queries use `[start,end)`. GMV sums `total_amount` only for `PAID,SHIPPED,DELIVERED,COMPLETED`, excluding pending/cancelled/closed. Add grouped day/order_count/gmv and status/cnt queries. Reuse conversation `countByStatus("PENDING_HUMAN")`.

- [ ] **Step 3: Implement immutable dashboard records and assembly**

Use nested records `SummaryVO`, `OrderTrendPoint`, `StatusCount`, `OperationsVO`, `AiQualityVO`, `RankItem`, `DashboardVO`. Inject a `Clock` configured for `Asia/Shanghai`; fill exactly seven ascending dates and overlay query rows. Reuse package-level pure StatsController aggregators for status, token, tools and trend inputs without altering existing endpoints.

- [ ] **Step 4: Verify service and existing stats GREEN**

Run: `cd backend; mvn -Dtest=AdminDashboardServiceTest,StatsControllerTest test`
Expected: PASS.

- [ ] **Step 5: Write controller RED then implement thin endpoint**

```java
mockMvc.perform(get("/api/v1/admin/dashboard"))
 .andExpect(status().isOk())
 .andExpect(jsonPath("$.data.summary.userCount").value(10))
 .andExpect(jsonPath("$.data.orderTrend").isArray())
 .andExpect(jsonPath("$.data.operations.waitingHumanConversationCount").value(2));
```

Run before controller for 404 RED, add controller, then run:
`cd backend; mvn -Dtest=AdminDashboardControllerTest test`
Expected: PASS.

- [ ] **Step 6: Full backend test and commit**

Run: `cd backend; mvn test`
Expected: zero failures/errors.

```powershell
git add backend/src/main/java/com/aimall/backend/admin backend/src/main/java/com/aimall/backend/mapper backend/src/test/java/com/aimall/backend/admin
git commit -m "feat: add administrator dashboard API"
```

---

### Task 6: Admin Dashboard View and Default Route

**Files:**
- Modify: `frontend/src/api/index.ts`, `frontend/src/types/api.d.ts`, `frontend/src/router/index.ts`, `frontend/src/layouts/ConsoleLayout.vue`, `frontend/src/stores/auth.ts`
- Create: `frontend/src/views/admin/dashboard.ts`, `DashboardView.vue`
- Test: `frontend/src/views/admin/dashboard.spec.ts`

**Interfaces:**
- Consumes: `AdminDashboardVO` from `/admin/dashboard`.
- Produces: `/admin/dashboard` default route, navigation entry, zero-safe localized view.

- [ ] **Step 1: Write formatter RED tests**

```ts
expect(formatMoney(undefined)).toBe('¥0.00')
expect(orderStatusText('PAID')).toBe('已支付')
expect(normalizeDashboard({summary:{}} as Partial<AdminDashboardVO>).orderTrend).toEqual([])
```

Run: `cd frontend; npm test -- src/views/admin/dashboard.spec.ts`
Expected: module-not-found RED.

- [ ] **Step 2: Implement exact response types/API/helpers**

Type all summary, trend, distribution, operations, quality, question and tool fields. Add money/percent/status formatters and full zero-safe normalization.

- [ ] **Step 3: Verify GREEN and build DashboardView**

Render six cards, responsive 7-day order/GMV table or CSS bars (no chart dependency), order status tags, waiting-human count, four AI metrics, top questions and tool ranking. Use Element Plus and responsive CSS grids.

- [ ] **Step 4: Route/navigation integration**

Add child route `dashboard`, redirect `/admin` there, update admin `homeRoute()`, put “数据看板” first in admin menu, retain “使用统计”.

- [ ] **Step 5: Test/build/commit**

Run: `cd frontend; npm test -- src/views/admin/dashboard.spec.ts src/stores/auth.spec.ts; npm run build`
Expected: PASS/build success.

```powershell
git add frontend/src/api frontend/src/types frontend/src/views/admin/dashboard* frontend/src/views/admin/DashboardView.vue frontend/src/router frontend/src/layouts frontend/src/stores/auth.ts
git commit -m "feat: add administrator data dashboard"
```

---

### Task 7: Remove Admin Product Edit and Normalize Seller Copy

**Files:**
- Modify: `frontend/src/views/admin/ProductManageView.vue`, `frontend/src/views/ProfileView.vue`, `frontend/src/views/LoginView.vue`
- Test: `frontend/src/views/admin/adminViewContracts.spec.ts`

**Interfaces:**
- Produces: create-only admin product dialog and visible “卖家” role copy.

- [ ] **Step 1: Write source-contract RED tests**

```ts
it('removes admin product editing', () => {
  const source = readView('ProductManageView.vue')
  expect(source).not.toContain('openEdit')
  expect(source).not.toContain('apiAdminProductUpdate')
  expect(source).not.toContain('编辑商品')
})
it('uses seller for visible merchant roles', () => {
  expect(profileSource).not.toMatch(/MERCHANT.*['"]商家['"]/) 
  expect(loginSource).not.toContain('merchant01 商家')
})
```

Do not ban business phrases such as “商家回复”; this requirement concerns role labels only.

Run: `cd frontend; npm test -- src/views/admin/adminViewContracts.spec.ts`
Expected: failures naming current edit and copy occurrences.

- [ ] **Step 2: Remove edit-only paths**

Remove edit button, `openEdit`, update import/call, ID edit state, update branch, and conditional title. Keep create validation/API and status toggle. Change visible role mappings/demo copy to “卖家”; do not rename `MerchantLayout`, `/merchant`, classes, API routes, or database values.

- [ ] **Step 3: Verify and commit**

Run: `cd frontend; npm test -- src/views/admin/adminViewContracts.spec.ts; npm run build`
Expected: PASS/build success.

```powershell
git add frontend/src/views/admin/ProductManageView.vue frontend/src/views/admin/adminViewContracts.spec.ts frontend/src/views/ProfileView.vue frontend/src/views/LoginView.vue
git commit -m "refactor: remove administrator product editing"
```

---

### Task 8: Documentation, Full Verification, and Repository Snapshot

**Files:**
- Modify: `README.md`, `docs/01-产品需求文档-PRD.md`, `docs/04-API接口设计文档.md`, `docs/06-前端设计文档.md`
- Track: intended project sources/configuration currently untracked because Git was just initialized.

**Interfaces:**
- Produces: accurate docs and a clean, reproducible Git snapshot.

- [ ] **Step 1: Update docs**

Document buyer/seller registration, admin agent creation, role tabs, dashboard route/metrics, status-only user API, and admin product edit removal. Write visible roles as “卖家” while preserving literal `MERCHANT` in technical contracts.

- [ ] **Step 2: Run all verification**

```powershell
cd backend; mvn test
cd ../frontend; npm test; npm run build
cd ../ai-service; python -m pytest
```

Expected: every suite passes and frontend production build succeeds.

- [ ] **Step 3: Audit forbidden paths/copy**

```powershell
rg -n 'merchant01 商家|MERCHANT.*商家|商家.*MERCHANT' frontend/src README.md docs
rg -n 'openEdit|apiAdminProductUpdate|编辑商品' frontend/src/views/admin/ProductManageView.vue
rg -n 'changeRole|role\?: string' frontend/src/views/admin/UserManageView.vue frontend/src/api/index.ts
```

Expected: no visible-role mismatch, admin edit path, or admin role mutation. “商家回复” may remain.

- [ ] **Step 4: Audit sensitive/unwanted files before baseline add**

```powershell
git status --short
git status --ignored --short | Select-String -Pattern '\.env|\.log|node_modules|dist|target|__pycache__'
```

Inspect root legacy scripts before staging; include only intentional, credential-free project artifacts. Never force-add ignored files.

- [ ] **Step 5: Stage intended baseline and check it**

Stage `.gitignore`, README, source/test trees, docs, Compose/Docker and intentional scripts. Then run:

```powershell
git diff --cached --stat
git diff --cached --check
git status --short
```

Expected: no secrets, runtime/build files, or whitespace errors.

- [ ] **Step 6: Final commit and clean-state check**

```powershell
git commit -m "feat: complete admin operations enhancements"
git status --short
```

Expected: clean output, except any explicitly reported local-only artifact intentionally left untracked.
