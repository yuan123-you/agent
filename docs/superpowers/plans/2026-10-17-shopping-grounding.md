# Shopping grounding bug-fix plan

Goal: Keep explicit shopping categories authoritative and return usable product links backed by tool results.

1. Add failing agent/tool tests for a phone request after computer history, and mandatory first product lookup.
2. Add failing SSE tests for placeholder/missing links and empty product results.
3. Implement minimal category grounding and first-lookup enforcement in agent/tools; reinforce prompts.
4. Repair missing recommendation links at the SSE boundary using only current product-search results; preserve link whitelist.
5. Run focused tests, AI-service suite, and existing frontend link tests. Preserve unrelated working-tree changes.

## Verification
- Reproduced original bugs: 5 failing, 2 passing regression cases before implementation.
- Reproduced two additional edge cases before fixing: budget refresh and order confirmation preservation.
- AI-service suite after changes: 189 passed (dependency deprecation warnings remain).
- Existing frontend link and stream-buffer tests: 13 passed using bundled Node 24; system Node cannot initialize current jsdom/undici.
- Python compileall and git diff --check passed.
- No live model/backend deployment or service restart performed.
- Full frontend suite using bundled Node 24: 23 test files, 152 tests passed.

## Follow-up: request understanding and handoff safety (2026-10-17)

- Added a separate regression suite for incorrect high-confidence classifications, checkpoint-only history, explicit/negated handoff phrasing, and real graph routing without backend handoff.
- Identity/capability questions override wrong model classifications. Human transfer requires explicit buyer wording at both router and tool boundaries; failed transfers no longer mark the session escalated.
- Generic category shopping requests are selection, not immediate order creation. Greetings no longer hide business requests in the fallback router.
- Explicit numeric budgets are remembered and enforced in both hybrid and SQL product lookup. A new category clears the previous category's budget. Around-N budgets use N as a conservative maximum.
- Reject cross-category search keywords even when the model supplies them. Empty searches clear stale recommendations.
- Tests use isolated model/backend fixtures; these results do not claim live-provider end-to-end validation. No services restarted or production configuration changed.

### Verification

- AI service: `python -m pytest -q --disable-warnings` — 231 passed (dependency deprecation warnings remain).
- Frontend: Vitest — 23 files, 152 tests passed; Vite production build passed. Used installed Node 24.19.0 because default Node 20.20.2 cannot run the existing jsdom/undici dependencies (package engine requires >=22.22.2). Build reports existing dependency annotation warnings.
- Backend: `mvn -q -Dtest=ChatServiceHandoffTest test` — 4 passed, no failures/errors/skips.
- `git diff --check` passed; Windows line-ending notices only.
