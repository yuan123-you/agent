# Final Fix Report — Admin Users Dashboard

- Date: 2026-08-23 (Asia/Shanghai)
- Fix base: `f55859866e86c09b39ea7cea86ee041070d6579e`
- Fix head: the single commit containing this report (exact SHA recorded in the final task response)
- Branch: `feature/admin-users-dashboard`
- Scope: final-review fixes only; no subagents used

## Decisions and implementation

1. **Password preservation**
   - Removed password trimming from `RegistrationService` and `AdminUserService`.
   - Usernames, nicknames, phone numbers, and merchant shop names retain their existing normalization; passwords alone are encoded exactly as submitted.
   - Added regression tests with a password containing both leading and trailing spaces.

2. **Asia/Shanghai write/query alignment**
   - Audited all relevant paths: the dashboard derives day windows from the existing Shanghai `Clock`; MyBatis-Plus previously used JVM-default `LocalDateTime.now()`; schema `created_at`/`updated_at` defaults use MySQL `CURRENT_TIMESTAMP`; JDBC and Jackson already declare `Asia/Shanghai`.
   - Injected the existing `Clock` into the MyBatis `MetaObjectHandler` and use it for insert/update fill. Insert fill takes one clock reading for both timestamps.
   - Added a fixed-clock automatic-fill test.
   - Added `TZ: Asia/Shanghai` to the backend container and explicitly set MySQL `--default-time-zone=+08:00`. This is the smallest explicit Compose change that aligns JVM writes, DB defaults, and dashboard windows without rewriting existing timestamps.

3. **Duplicate username race handling**
   - Retained the pre-check for normal feedback, then catch `DuplicateKeyException` from the authoritative `userMapper.insert` and convert it to `BizException(2005, "用户名已存在")`.
   - Direct mapper-exception tests cover buyer, seller, and agent creation.
   - Seller registration remains `@Transactional`; shop creation is not attempted on a duplicate user insert and unchecked `BizException` preserves rollback behavior.

4. **Dashboard indexes**
   - Audited V1/V3/V4 before adding the next migration; none already defines the three requested indexes.
   - Added `V5__dashboard_query_indexes.sql` with:
     - `order_info(created_at)`
     - `conversation(created_at, deleted)`
     - `product(status, deleted)`
   - Added a migration source-contract test. Live `EXPLAIN` was intentionally not required under the ledger ruling.

5. **Registration phone**
   - Added an optional phone field to `LoginView` and initialized `regForm.phone`.
   - Existing payload construction now receives the field; tests verify trimmed phone payloads for both buyer and seller routes.

6. **Agent phone reset**
   - Added `prop="phone"` to the agent phone form item, so Element Plus `resetFields()` clears it on dialog close, including the successful-create close path.
   - Added a source contract test.

7. **Documentation**
   - Updated README registration/timezone behavior.
   - Updated the database design with the Shanghai time policy and V5 indexes.

## TDD evidence

### RED

- Backend targeted run failed at test compilation because the new fixed-clock test called the not-yet-existing `metaObjectHandler(Clock)` interface.
- Frontend targeted run: 2 new failures, 10 existing/new assertions passing. The failures were exactly the missing `regForm.phone` field and missing agent phone `prop="phone"`.

### GREEN

- Backend targeted tests: `RegistrationServiceTest`, `AdminUserServiceTest`, `MybatisPlusConfigTest`, and `DashboardIndexMigrationContractTest` passed.
- Frontend targeted tests: 2 files, 12/12 tests passed.

## Full verification

| Command | Result |
|---|---|
| `cd backend; mvn test` | PASS — 61 tests, 0 failures/errors/skips; BUILD SUCCESS |
| `cd frontend; npm test` | PASS — 11 files, 52 tests |
| `cd frontend; npm run build` | PASS — Vite production build completed |
| `cd ai-service; python -m pytest` | PASS — 34 tests; 37 upstream asyncio deprecation warnings |
| `git diff --check` | PASS — no output |
| forbidden-path `rg` | PASS — no admin product edit path, role mutation path, or password trimming in the two services |
| security/disabled-path `rg` | PASS — `/api/v1/admin/**` remains ADMIN-only; status allowlist remains ACTIVE/DISABLED; admin users remain excluded from listing |
| intended-path `rg` | PASS — timezone, indexes, and both phone form bindings found |
| ignored-artifact audit | PASS — only ignored runtime/build artifacts; none staged |

The visible-role audit only matched historical specification/plan text describing the prohibition and negative test assertions; it found no production UI mismatch. `docker compose config --quiet` parsed the Compose file but could not complete because the intentionally ignored `ai-service/.env` is absent in this worktree; this was an additional check, not one of the required verification gates.

## Files changed

- `README.md`
- `docker-compose.yml`
- `docs/03-数据库设计文档.md`
- `backend/src/main/java/com/aimall/backend/admin/AdminUserService.java`
- `backend/src/main/java/com/aimall/backend/auth/RegistrationService.java`
- `backend/src/main/java/com/aimall/backend/config/MybatisPlusConfig.java`
- `backend/src/main/resources/db/migration/V5__dashboard_query_indexes.sql`
- `backend/src/test/java/com/aimall/backend/admin/AdminUserServiceTest.java`
- `backend/src/test/java/com/aimall/backend/auth/RegistrationServiceTest.java`
- `backend/src/test/java/com/aimall/backend/config/MybatisPlusConfigTest.java`
- `backend/src/test/java/com/aimall/backend/migration/DashboardIndexMigrationContractTest.java`
- `frontend/src/views/LoginView.vue`
- `frontend/src/views/admin/UserManageView.vue`
- `frontend/src/views/admin/adminViewContracts.spec.ts`
- `frontend/src/views/auth/registration.spec.ts`
- `.superpowers/sdd/2026-08-23-admin-users-dashboard/final-fix-report.md`

## Residual risks

- V5 creates indexes with ordinary MySQL DDL; on a large live database, migration duration/locking should be observed during deployment. No live `EXPLAIN` was run, per ruling.
- The timezone configuration makes future application and DB-default writes consistent; it deliberately does not reinterpret or rewrite historical timestamps.
- Full Compose interpolation still requires the local, ignored `ai-service/.env`; deployment environments must provide it as before.
- Existing Vite large-chunk/PURE-comment warnings and Python asyncio deprecation warnings remain unchanged and non-failing.
