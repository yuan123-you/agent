# Live Agent Evaluation Design

**Date:** 2026-08-24

## Goal

Measure the deployed LangGraph Agent and its real tools/retrievers instead of treating offline rules as production quality evidence.

## Interface

The existing internal SSE endpoint accepts `options.include_eval_metadata=true`. For those explicitly marked internal requests only, tool-result events add sanitized retrieval metadata and the final `done` event adds the graph's classified intent. Normal backend-originated chat responses are unchanged.

The eval runner calls the SSE endpoint with a dedicated test user/conversation range and records actual intent, tool calls/arguments, ranked product or KB hits, final response, latency, and token usage. It writes `eval/results/live.json`; the deterministic offline baseline remains unchanged for CI.

## Metrics

- intent accuracy
- tool-name correctness and expected-argument accuracy
- product retrieval Recall@5 and MRR
- reply keyword coverage
- KB citation coverage
- P50/P95 latency and total token usage

Live execution requires a disposable evaluation identity because order and human-handoff cases can invoke real guarded backend callbacks.
