# Java AI deadline and retry ownership — 2026-11-01

## Contract

Java is **single attempt**, including chat SSE, native start/resume/recover, ingest mutation, vector deletion, and summary requests. There are no Java backoffs, SDK retry policies, HTTP response retries, or transport-timeout replays. Full Jitter and automatic model/tool retry ownership belong to the unified Python core; Java does not implement a second retry owner.

The configured AI `WebClient` explicitly installs `HttpClient.create().disableRetry(true)`. This disables Reactor Netty's connection-reset retry, which would otherwise bypass the absence of application `retry()` calls. There is no model SDK in this Java gateway.

`RequestBudget` captures a monotonic absolute deadline and an allowance of at most six Python retries. Outgoing calls send:

- `X-Request-Timeout-Ms`: remaining relative milliseconds, rounded down, after reserving 25 ms for header construction/dispatch. A nonpositive remainder means **no request is sent**.
- `X-Request-Retry-Budget`: the captured allowance, clamped to `0..6`; nested scopes cannot increase it. Zero allows an initial attempt, not a retry.

No outgoing deadline or permit allowance is read from public browser headers.

## Operation boundaries

- **Native coordination:** one fixed 30-second scope starts before the canonical snapshot/provenance operations. Registration (`start`) and subsequent `resume` or `recover` share that absolute deadline. Each `WebClient` response timeout and synchronous `block` wait is clipped to the remaining time. Timeout/error never calls a direct domain confirm/cancel fallback and never silently repeats registration or a buyer decision.
- **Chat:** `app.ai.chat-timeout` / `AI_CHAT_TIMEOUT`, default `180s`. Each SSE timeout signal is calculated from the same absolute operation deadline, rather than restarting a fixed idle interval on each event. Deadline expiry cancels the upstream body and emits a timeout error; no partial SSE stream is replayed.
- **Ingest:** `app.ai.ingest-timeout` / `AI_INGEST_TIMEOUT`, default `30s`, including headers and waiting for the response. An ambiguous write failure is surfaced without resubmitting the task.
- **Summary/vector cleanup:** 30-second local limit, clipped by a captured parent budget. Existing empty-summary/best-effort deletion degradation is retained without retries.
- Configurable durations have a hard upper limit of ten minutes; negative configured durations are rejected. Inherited deadlines may only shorten a local operation. The native 30-second limit is not configurable upwards.

All asynchronous gateway publishers capture the budget at **method entry**, before subscription. They do not install servlet thread-local state in Reactor worker threads.

## Trusted callback propagation

`InternalAuthFilter` first validates a nonempty configured internal token, and only for `/internal/**`. Only inside that successful branch does it import the two headers into a synchronous request scope. An authenticated callback is limited to 30 seconds and six permits; a nested native start further takes the minimum of its local deadline and the inherited callback deadline. After importing the authenticated budget, the filter calls `remainingTimeout()` **before** `chain.doFilter`. Zero timeout, or a positive timeout too small to cover the existing 25 ms dispatch reserve, returns JSON HTTP 503 / code 5002 without entering a controller or domain service, even for pure execute/cancel callbacks with no outgoing AI call. Zero retry permits remain zero and do not prohibit an otherwise admissible initial attempt. Missing, negative, malformed, or overflowing header numbers fall back to local limits, never values above them. Positive oversized values are clamped.

Public `/api/**` requests, even with forged budget headers or an internal-token header, do not import a budget. Failed internal-token validation does not invoke the controller or construct a native request. Scopes restore/remove the thread-local in `finally`, including exceptions.

**Limit:** this propagation covers the current synchronous validated callback -> preparation -> native-start path. The Java allowance is an immutable snapshot, not a distributed atomic counter: separate HTTP requests/processes do not share a mutable permit ledger. Arbitrary executors, newly spawned threads, and background jobs do not inherit the servlet scope. A gateway publisher explicitly created in a scope does retain its captured deadline after that scope closes. Background job budget ownership remains with Python. Local database calls are charged against the remaining deadline but are not forcibly cancelled by this HTTP deadline helper; existing transaction/JDBC bounds remain separate. Existing servlet/browser SSE lifetimes can also terminate a connection earlier than a configured gateway limit.

## Failures and safe writes

The native gateway classifies authorization, permanent HTTP, transient HTTP, transport, deadline, invalid response, and permanent client/protocol/configuration failures. Only `408/429/500/502/503/504` are classified transient HTTP. TLS/protocol and malformed JSON/invalid receipts are not classified as transient transport failures. **None of these classifications enables an automatic Java retry.** The existing `recoverable` response flag describes an explicit durable workflow recovery opportunity, not authorization to replay an HTTP request.

Existing action/preparation keys, canonical ownership reads, native provenance, saved buyer approval, transactional/idempotent domain execution, and receipt validation are unchanged. Recovery remains an explicit operation on the same action ID. Ingest writes do not acquire a speculative idempotency key or automatic replay. No schema changes were made for deadline/retry integration.

## Verification

Fault injection uses in-memory `WebClient.ExchangeFunction` responses, hanging publishers, HTTP error responses, malformed JSON, partial SSE output, and a monotonic fake clock for deterministic native deadline exhaustion. The connector test inspects the actual configured Reactor Netty client. No fault tests open sockets, invoke models, require paid services, or perform production operations. Maven runs use offline mode.

Test-first failure evidence is recorded in the ignored local logs `backend/retry-budget-behavior-red.log`, `backend/retry-budget-deadlines-red.log`, and `backend/retry-budget-additional-red.log`. The SSE test distinguishes the upstream total-deadline error from its own blocking test guard and verifies upstream cancellation. Test coverage includes start/resume and start/recover decreasing budgets; expiry before any gateway call and after registration; zero decision calls on expiry; ambiguous decision timeout with exactly one registration and one decision attempt; permanent/transient HTTP, TLS/protocol/invalid JSON classification; partial stream errors; unsafe ingest no replay; authenticated clipping and public header forgery; and existing native approval/idempotency/authorization regressions.

This is local fault-injection evidence, not a live-service availability, latency, distributed-counter, or wire-level connection-reset claim.

### Initial integration verified results (2026-11-01, Asia/Shanghai)

| Run | Result | Local log |
| --- | --- | --- |
| Expanded focused regressions + budget tests | 120 tests; 0 failures, 0 errors, 0 skipped | `backend/retry-budget-focused.log` |
| Entire backend suite | 859 tests; 0 failures, 0 errors, 0 skipped | `backend/retry-budget-full.log` |
| `git diff --check -- backend` | clean | terminal output |

Commands executed from the shared repository root, without dependency downloads:

```powershell
mvn -o -f backend/pom.xml '-Dtest=RequestBudgetTest,RequestBudgetIntegrationTest,InternalBudgetSecurityTest,AiClientBudgetTest,WebClientSingleAttemptTest,ActionWorkflowClientTest,ActionWorkflowCoordinatorTest,ActionWorkflowControllerTest,NativePreparationResponseTest,AgentOrderActionTransactionTest,JwtAuthFilterSecurityTest,ChatGatewayBoundaryTest,ChatServiceRecoveryTest,ChatStreamRecoveryTest' test
mvn -o -f backend/pom.xml test
git diff --check -- backend
```

No commit, deployment, production/paid-service operation, schema modification, or changes outside `backend/**` were made by this Java integration work. The pre-existing uncommitted native-action schema and business changes were retained and exercised by the full suite. Python Full Jitter, shared retry accounting, retry-after policy, and model SDK retry settings remain the parent's/model worker's responsibility and were not verified by the Java-only suites.


### Upfront internal admission correction — 2026-11-01

The admission check is deliberately inside the validated-token branch and the imported budget scope, but its `DeadlineExceeded` catch surrounds only `remainingTimeout()`, not the controller chain. Authentication is checked before reading budget headers. An early rejection restores/removes the previous budget scope in `finally`. Already-admitted controller/JDBC work is not cancelled, intercepted, or retried by this check. No schema or protocol fields were added.

The reproducing tests ran before the filter change: six real MVC execute/cancel cases with `0`, `1`, and `25` ms budgets incorrectly returned HTTP 200; a rejected-admission scope case also returned 200; the old zero-budget preparation path entered the chain and failed downstream instead of rejecting admission. These failures are recorded in `backend/retry-budget-admission-red.log`.

The updated tests assert JSON 503/code 5002 with no controller/domain interactions, parent-scope restoration, sufficient-budget execute/cancel admission even with zero retry permits, bad-token 401 without reading either budget header, and ignored public zero/tiny/oversized budget headers. The old test expecting a downstream gateway exception for a zero timeout now requires filter-level no-admission.


Final admission verification (offline Maven, 2026-11-01 Asia/Shanghai):

| Run | Result | Local log |
| --- | --- | --- |
| Expanded focused regressions including admission | 129 tests; 0 failures, 0 errors, 0 skipped | `backend/retry-budget-admission-focused.log` |
| Entire backend suite after the admission correction | 868 tests; 0 failures, 0 errors, 0 skipped | `backend/retry-budget-admission-full.log` |
| `git diff --check -- backend` | clean | terminal output |

The focused selection is the same command listed above; the full backend run used `mvn -o -f backend/pom.xml test` after focused success. The admission follow-up changed only the filter, its two affected test files, and these backend notes, preserving prior uncommitted work without commits or changes outside `backend/**`.
