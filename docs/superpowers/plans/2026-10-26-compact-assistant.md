# Compact Assistant Implementation Plan

**Goal:** Reduce avoidable inference overhead and make assistant replies, tool feedback and the composer concise.
**Architecture:** Reuse the existing Vue/Element Plus design tokens. Keep tool previews collapsed in a native disclosure, remove AI-only bubble decoration, and autosize the composer from one to four lines. Bypass intent inference only for unambiguous explicit product recommendations; preserve contextual classification and all data/approval/link/citation safeguards.
**Spec:** User request and attached current-chat screenshot, 2026-10-26.
**Execution:** Local sequential TDD; preserve existing uncommitted changes; no dependency/provider changes or deployment.

## Tasks
- [x] Add and observe failing tests for single-line autosizing, concise placeholder, and collapsed one-line tool disclosures; implement compact component styles.
- [x] Add and observe failing tests for explicit shopping intent fast paths and prompt concision; retain model classification for mixed/contextual/action requests; implement narrowly scoped routing and prompt instructions.
- [x] Run all frontend tests, typecheck/build, Python tests and a mobile/desktop browser smoke check where available. Record limitations; do not claim provider latency gains without a real benchmark.


## Verification — 2026-10-26
- Observed RED before implementation: compact composer/tool disclosure assertions failed; new Python suite had 5 failures (missing fast paths and prompt contract).
- Final assistant frontend regression run: 6 files / 61 tests passed (`ChatView`, `AiMessage`, `ToolCallCard.performance`, chat stores and SSE).
- `npx tsc --noEmit`: passed. Final `npm run build`: passed (existing third-party PURE annotation warnings).
- AI routing, prompt, identity, request-understanding, citation and link-guard regressions: 111 passed.
- Whole frontend run: 213 passed / 17 failed, confined to ProductDetailView.spec.ts (not modified by this task).
- Whole AI-service run: 283 passed / 5 failed, confined to test_ingest_version_callbacks.py (not modified by this task; backend callbacks lack doc_version propagation).
- Browser smoke check used real components/stores with isolated simulated data, not a real provider. Mobile 390x844 / 390x680 and desktop 1366x900 had no horizontal overflow. Composer measured about 45px empty, about 117px with 6 lines (4 visible lines with scrolling). AI reply border/shadow were absent; tool disclosure was one 44px row, expanded on click. Ctrl+Enter sent the draft and restored the empty composer.
- Preview screenshot: `.workbuddy/tmp/assistant-compact-mobile.png`. Temporary preview HTML/TS files removed; existing local server left running; viewport override reset.
- No model/provider speed benchmark, production deployment, Git staging or commit performed. Existing concurrent workspace changes preserved.


## Follow-up — flexible answer depth, 2026-10-26
- User clarified that compact UI must not impose hard limits on model answers.
- Removed fixed sentence counts, recommendation caps, one-line-per-item formatting and fixed follow-up counts from the response prompts. Concision is a style preference; useful explanation/comparison can expand naturally without requiring an explicit request for detail.
- Preserved compact UI, latency fast paths, real-data/citation requirements and business confirmations. No new output-token cap was introduced.
- TDD: the three updated response-prompt cases failed before the change, then the assistant regression suite passed (114 tests).


## Production release — 2026-10-26
- All remaining assistant/chat/mobile-navigation changes were committed and pushed to `origin/dev` as `f422bad9887bd5855954251d661adbb93057ca60`.
- Fresh full checks: frontend 264 passed, AI-service 301 passed, deployment/credential hygiene 19 passed. TypeScript and the `/aimall/` production build passed. The earlier unrelated test failures recorded above have since been resolved in the preceding commerce release.
- Deployed only rebuilt `ai-service` and `frontend` images under the server deployment lock. Backend and all six data/model/infrastructure containers retained their original container IDs. No database schema/configuration changes or volume removal.
- Preserved old application images, previous Git revision and a fresh permission-restricted database backup, with automatic rollback on build/startup/smoke failures.
- Production smoke verification: 31 checks passed, including nine healthy services, deployed AI source hashes matching Git, no fixed response-length/count caps, six public JS/CSS artifact hashes matching container bytes, public catalog API, blocked internal/admin routes and actual authenticated AI SSE token/done responses.
- Specific live samples: identity fast path 0.09 seconds; model-backed greeting 12.39 seconds. These are single synthetic checks, not a broad latency/concurrency benchmark.
- Reused only the prior release's dedicated synthetic QA account, closed the test conversations and restored the account to DISABLED.
- Private server evidence: `/srv/aimall/releases/f422bad/` (`final-verification.json`, `ai-stream-verification.json`, build/verification logs and rollback artifacts). Public entry: https://aimall.novo.ccwu.cc/aimall/ .
