# Phase 1 Correctness and CI Design

**Date:** 2026-08-24

## Goal

Make the existing Agent + RAG platform internally consistent and restore the repository's CI contract without changing product behavior or adding new framework layers.

## Scope

1. Knowledge-base retrieval must expose only chunks whose `doc_version` equals the owning document's current version and whose document is `ACTIVE`.
2. Successful ingestion must prune superseded MySQL chunks. Vector hits must be validated against backend current-version metadata so stale Milvus rows cannot leak after an outage or partial rebuild.
3. Frontend Vitest behavior stays unchanged while `tsc --noEmit` becomes clean.
4. A timed-out Agent request must return a non-empty degraded response.
5. README Milvus and pymilvus versions must match Compose and Python requirements.

## Design

### Knowledge-base consistency

The Spring backend remains the source of truth. Keyword retrieval adds a current-version predicate. The ingestion result callback prunes superseded relational chunks only after the new ingestion reports `ACTIVE`. A small internal endpoint accepts candidate chunk IDs and returns titles only for chunks belonging to active documents at their current version. AI vector search uses that response both to discard stale Milvus hits and label valid sources. This keeps correctness at the existing backend seam and avoids a new index registry.

### Frontend typing

Use explicit partial nested DTO types when normalizing optional dashboard data. Replace registration overloads with one union-returning signature because callers already pass the role union. Runtime behavior remains unchanged.

### Timeout behavior

Extract a tiny pure helper that returns the existing text when present and a fixed retry/transfer message only when a timeout produced no content. The SSE event remains `done` with `timedOut=true`.

### Documentation

README reports Milvus server 2.4.9 and pymilvus 2.4.15, matching deployable artifacts.

## Testing

- Backend unit tests cover current-version hit filtering and superseded-chunk cleanup.
- AI tests cover stale vector-hit removal and timeout fallback.
- Existing frontend tests plus `tsc --noEmit` cover the type-only fixes.
- Final gate runs AI pytest, backend Maven tests, eval pytest, frontend Vitest/typecheck/build, and Compose config validation.
