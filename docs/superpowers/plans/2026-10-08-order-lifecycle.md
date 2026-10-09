# Order lifecycle atomic transition implementation plan

> Implement locally using test-driven-development and verification-before-completion. Read-only review follows requesting-code-review; no commit/push/deployment.

**Goal:** Ensure competing order commands cannot overwrite each other's states, restore inventory twice or announce rolled-back results.
**Architecture:** One finite set of existing transitions plus database compare-and-set UPDATE WHERE id AND expected status. Inventory restoration executes only after a winning cancellation. SSE notification is scheduled after successful transaction commit, with detached event values and best-effort failure isolation.
**Tech Stack:** Java 17, Spring/MyBatis-Plus/MySQL, JUnit/Mockito, isolated H2 mapper/transaction tests.
**Spec:** Existing OrderService behavior and user's continued backend/database/AI remediation request, frontend unchanged.

## Constraints
- Preserve existing PENDING_PAYMENT -> PAID/CANCELLED, PAID -> SHIPPED, SHIPPED -> DELIVERED rules and BizException codes. Repeated commands remain errors, not a new idempotent-success policy.
- Preserve ownership validation and existing stock optimistic-lock safeguards. No new states, payment gateway, scheduler or schema migration.
- No unrelated edits or existing work reset; other AI Mall frontend/model-provider changes are user work.

### Task 1: Reproduce losing transitions and transaction notifications
Files: backend/src/test/java/com/aimall/backend/order/OrderLifecycleTest.java; OrderLifecycleTransactionTest.java; backend/pom.xml (test-only H2).
- [x] Test all losing transition writes (zero affected rows) through pay/cancel/ship/deliver; no inventory or notification effects on losers.
- [x] Test notification timing, rollback suppression and detached values.
- [x] Use isolated real MyBatis mappers and transaction proxy for concurrent pay/cancel and duplicate cancellation; verify one stock restoration and committed state.
- [x] Observe original failures before implementation.

### Task 2: Atomic lifecycle module and post-commit events
Files: backend/src/main/java/com/aimall/backend/order/OrderTransition.java; OrderService.java; mapper/OrderInfoMapper.java.
- [x] Define only the four existing transitions and their validation messages.
- [x] Execute guarded SQL updates and check affected rows before continuing; never retry by overwriting another transition.
- [x] Keep cancellation inventory adjustment in the same transaction; schedule all create/checkout/transition notifications after commit.
- [x] Run new tests and full backend suite. Document MySQL and real SSE testing limits.

## Acceptance limits
- [ ] Target MySQL integration, real provider/SSE compatibility and end-to-end acceptance remain required before deployment.
- [ ] Remaining historical-data / general lifecycle issues are not declared solved by this scoped implementation.

## Final execution evidence
- Initial unit regressions: 15 tests / 8 failures; initial isolated mapper/transaction regressions: 6 tests / 4 failures. Then 27 focused tests passed; supplemental checkout/outer cancellation tests added.
- Final full backend: 133 tests passed, 0 failures, 0 errors (24 new tests).
- Read-only reviewer found no important issue in the bounded order changes; H2/MySQL/SSE production validation limits remain documented.
