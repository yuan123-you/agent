# Live Agent Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in, real Agent evaluation runner with measurable intent, tool, retrieval, response, latency, and token metrics.

**Architecture:** Extend the internal SSE contract only for explicitly marked evaluation requests, then use a standard-library client in `eval` to replay existing datasets. Keep offline CI evaluation unchanged.

**Tech Stack:** FastAPI/LangGraph SSE, Python standard library, pytest.

**Spec:** `docs/superpowers/specs/2026-08-24-live-agent-eval-design.md`

## Global Constraints
- No new dependency.
- Normal chat SSE payloads remain unchanged.
- Live results write to `live.json`, never overwrite `baseline.json`.
- A dedicated disposable user/conversation range is required for side-effecting cases.

### Task 1: Opt-in evaluation metadata
- [ ] Add failing AI tests for sanitized tool metadata and intent in final payload support.
- [ ] Implement metadata helpers and opt-in SSE fields.
- [ ] Run AI tests.

### Task 2: Live SSE client and metrics
- [ ] Add failing eval tests using a fake replay client.
- [ ] Implement SSE parsing, replay, metric aggregation, and CLI configuration.
- [ ] Run eval tests and offline baseline regression test.

### Task 3: Documentation and verification
- [ ] Document live invocation and safety requirements.
- [ ] Run AI, eval, backend, frontend typecheck/tests, and diff checks.
