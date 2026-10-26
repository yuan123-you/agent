# AI Assistant Performance Implementation Plan

> **For agentic workers:** Execute inline using executing-plans; do not delegate or commit without user authorization.

**Goal:** Address slow conversation loading, mismatched/flashing content, delayed safe output, and uninformative waiting feedback.

**Architecture:** Keep the existing Vue/Pinia + fetch SSE + LangGraph architecture. Load conversation detail and messages concurrently and commit them atomically, guard stale requests, and retain the current view during reload. Coalesce token-driven reactive updates, preserve link buffering, and stream only terminal model nodes where post-validation cannot invalidate earlier text. Keep all RAG citations and tool-enabled agent answers buffered for existing safety checks.

**Tech Stack:** Vue 3, Pinia, Vitest/jsdom, FastAPI, LangGraph, pytest.

**Spec:** User request in this chat on 2026-10-26: optimize assistant loading, flicker, response latency, and waiting feedback.

## Global Constraints
- Preserve citation validation, product-link validation, and order approvals.
- Preserve background generation and human-service handoff behavior.
- Do not change model/provider settings or unrelated files, including CartView.vue.
- Every behavioral fix requires an observed failing regression test before production changes.
- Do not claim external-provider speed improvements without real latency measurements.

### Task 1: Conversation loading and race safety
**Files:** frontend/src/stores/chat.ts, frontend/src/stores/chat.spec.ts, frontend/src/views/ChatView.vue, frontend/src/views/ChatView.spec.ts
- [ ] Add tests asserting parallel detail/message requests, atomic commits, latest-selection wins, in-flight deduplication, and nonblocking action-status refresh.
- [ ] Run `npm test -- src/stores/chat.spec.ts src/views/ChatView.spec.ts` and observe failures.
- [ ] Add loading flags and guarded atomic state updates. Render loading placeholders instead of transient empty states; avoid refetching an already displayed conversation on remount.
- [ ] Rerun tests, including existing background-stream and handoff tests.

### Task 2: Stable streamed rendering and lifecycle
**Files:** frontend/src/stores/chat.ts, frontend/src/composables/useSseChat.ts, corresponding spec files, frontend/src/views/ChatView.vue
- [ ] Add tests for coalesced tokens with immediate final flush, partial output preservation on stop/error, interrupted EOF, trailing SSE frames, and scroll following content growth.
- [ ] Run targeted tests and confirm each new regression fails for the intended reason.
- [ ] Batch rendering on a short timer; flush/cancel it on every terminal path. Treat EOF without done/error as interruption, and release/cancel stream readers after terminal events. Watch content growth without overriding manual upward scrolling.
- [ ] Rerun all frontend tests.

### Task 3: Reduce avoidable inference latency safely
**Files:** ai-service/app/api/chat.py, ai-service/app/agent/nodes.py, ai-service/app/agent/link_guard.py, ai-service/tests/test_chat_rag_citations.py, ai-service/tests/test_assistant_optimization.py
- [ ] Add tests that safe terminal nodes yield a token before graph completion; split unknown links never leak; ordinary/RAG tool-enabled answers retain validation; explicit human/identity and exact greeting requests avoid unnecessary classification.
- [ ] Run targeted pytest tests and observe failures.
- [ ] Add incremental link-safe buffering only for known terminal nodes, avoid replaying emitted tokens, and enable streaming for forced finalization. Add narrowly deterministic routing fast paths; retain the classifier for contextual or mixed requests.
- [ ] Rerun existing citation, request-understanding, intent, link-guard and agent tests.

### Task 4: Waiting experience and verification
**Files:** frontend/src/components/chat/AiMessage.vue, frontend/src/components/chat/AiMessage.spec.ts, frontend/src/views/ChatView.vue
- [ ] Add component tests for real tool-dependent waiting labels, elapsed time/slow-request hint, stable Markdown container, terminal failure/stopped state and delegated link navigation during streaming.
- [ ] Run component tests and observe failures.
- [ ] Implement stage-aware accessible waiting feedback, elapsed time, reduced-motion styling, stable delegated link handling, and loading retry controls.
- [ ] Run complete frontend tests, production build, Python suite, and browser smoke checks if the local app is available. Review diff for scope and retained safety invariants.

## Verification commands
```powershell
cd frontend; npm test; npm run build
cd ../ai-service; python -m pytest -q
```
