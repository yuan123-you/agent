# Chat failure feedback and recovery

**Goal:** Clear accessible failure feedback, real retry controls, and recoverable interrupted SSE requests without replaying business tools.
**Execution:** Sequential TDD in the current workspace; preserve unrelated concurrent changes. No deployment, commits, dependency changes or schema migration.

## Files and boundaries
- `frontend/src/components/chat/AiMessage.vue` and its tests: compact neutral status panel, distinct recovery actions, no duplicate error prose.
- `frontend/src/components/chat/replyFeedback.ts`: normalized user-facing failure categories; never expose raw server exceptions.
- `frontend/src/stores/chat.ts`, `frontend/src/types/api.d.ts`, `frontend/src/composables/useSseChat.ts` and tests: stable request identity, session-scoped recovery descriptor, restore/retry, existing stream guards.
- `backend/.../chat/ChatStreamRecovery.java` and tests: Redis-backed same-request event replay, bounded retention/deadlines, no repeated AI invocation on reconnect.
- `backend/.../chat/ChatDtos.java`, `ChatService.java`, `SseEmitterManager.java` and tests: validate failed-reply regeneration, reuse original user message, persist interruptions/timeouts as failures.
- AI request state tests and `ai-service/app/api/chat.py`: explicitly regenerated turns rebuild message history rather than duplicate the failed turn.
- `ai-service/app/agent/nodes.py` and date tests: cover relative date queries from the preceding reported failure.

## Steps
- [x] Add failing UI/store/SSE/backend tests for duplicated feedback, disabled recovery actions, replay, ownership, retry and timeout status.
- [x] Implement bounded event replay and terminal persistence; validate regeneration before accepting a new run.
- [x] Implement normalized UI feedback and session recovery; retain partial text until replacement output arrives.
- [x] Fix narrow relative-date fast path with timezone-aware tests.
- [x] Run focused and full regression tests, TypeScript/build, and mobile/desktop visual verification where available.

## Recovery contract
- Transport interruption reuses the request ID and replays saved events; it is not a second generation and cannot repeat tools.
- Explicit regeneration is allowed only for the latest persisted failed AI reply in an ACTIVE owned conversation; the original USER record is reused.
- Session recovery persists only a bounded descriptor in sessionStorage (account-scoped), not an unbounded transcript. Server replay has a finite retention window and reports expiration clearly.
- A stopped client can recover the original server run; stopping does not claim server-side cancellation.


## Verification — 2026-10-28
- RED observed: original feedback/SSE tests had 4 failures; recovery store initially had 4 failures. Additional reproductions caught stale stream completion, stale recovery descriptors, duplicate pending hydration, missing same-conversation exclusion, and old-emitter heartbeat cleanup.
- Backend review follow-up: six failing tests reproduced missing-identity lock bypass, durable-event loss, orphaned event retention, initialization failure after USER insertion, and socket lifecycle cleanup. All are now covered by passing regressions.
- Final standard backend command: `mvn -q -Dtest=ChatStreamRecoveryTest,ChatServiceRecoveryTest,ChatServiceHandoffTest,SseEmitterManagerRecoveryTest test -f backend/pom.xml`: 24 tests passed. A temporary isolated compiler harness was used while unrelated concurrent after-sale classes were incomplete; the standard project command subsequently passed, and the temporary compiler harness was removed.
- Frontend full suite: `npm test -- --maxWorkers=2`: 44 files / 424 tests passed. A default-worker run previously hit an unrelated router test's five-second timeout; the same router test passed in focused verification and the bounded-worker full run.
- AI-service full suite: 398 passed. Existing dependency deprecation warnings and a background-memory task cleanup warning were observed; no claim of warning-free execution.
- Final frontend production build passed. Global TypeScript checking remains blocked by an existing/concurrent `src/api/request.ts:93` interceptor return-type error; this task did not modify that file.
- Visual/interaction QA used the real ChatView, AI component and Pinia store with isolated synthetic HTTP/SSE responses. Verified actual regenerate/recover clicks, partial output, paused reception, expiry and inactive-conversation copy. Mobile 390px, narrow 320px and desktop 1366px showed no horizontal overflow. Screenshots saved under `.workbuddy/tmp/chat-recovery-*-mobile.png` and `chat-recovery-partial-desktop.png`; temporary preview HTML/TS files removed and viewport override reset.
- Redis replay tests use deterministic mocked Redis operations, not a live Redis/provider benchmark. No production deployment, Git staging/commit/push, dependency/provider changes, or schema migrations were performed by this task. Unrelated concurrent changes were preserved.

## Final recovery semantics
- A transport reconnect/manual recovery reuses the original request identity and cannot execute its model/tools again. Event retention is 24 hours after activity; recovery of an unfinished run has a five-minute deadline. No promise of continuing model computation after a server crash.
- Pausing means stopping local reception, not claiming to cancel already-running server tools. UI copy and the control now say pause, and the same request can be recovered.
- A persisted terminal failure may be explicitly regenerated only when it is the latest failed turn and has no business operation tool/card. The USER record is reused and graph messages are rebuilt from the validated preceding history.
- Recovery records are per-tab and account-scoped; late completion from an old account cannot write a descriptor under a new account. Storage failure does not break a live reply.
- Durable event writes are not swallowed as harmless socket errors. A recording failure stops the upstream stream, persists failed state when possible, and closes the client connection with normalized feedback. Metadata outlives event retention; orphaned event lists cannot be reused as a new run.
