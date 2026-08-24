# Product Retrieval Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make BM25 independently available and stop duplicate Agent tool execution.

**Architecture:** Separate the in-memory corpus lifecycle from Milvus, degrade each retrieval leg independently, and reuse the existing finalizer for duplicate calls.

**Tech Stack:** Python, LangGraph, Milvus, rank_bm25, pytest.

**Spec:** `docs/superpowers/specs/2026-08-24-product-retrieval-resilience-design.md`

## Global Constraints
- No new dependencies.
- SQL remains the final fallback only when the in-memory corpus is unavailable.
- Existing tool and API signatures remain compatible.
- No query-rewrite LLM call in this phase.

### Task 1: Independent product corpus
- [ ] Add failing tests for BM25 use when Milvus fails and corpus rebuild before embedding failure.
- [ ] Add a process-wide corpus getter and move rebuild before vector work.
- [ ] Catch vector-leg errors without discarding BM25.
- [ ] Run focused and full AI tests.

### Task 2: Duplicate tool-call convergence
- [ ] Add failing tests for repeated and changed tool signatures.
- [ ] Route repeated calls to the existing finalizer.
- [ ] Run focused and full AI tests.

### Task 3: Live measurement and verification
- [ ] Run safe live smoke against the updated service.
- [ ] Record the comparison without committing environment-specific results.
- [ ] Run all repository verification gates and review the diff.
