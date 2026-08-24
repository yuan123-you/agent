# Large Business Knowledge Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand AI Mall's 15 seed documents to more than ten times their current per-document size and persist their embeddings in Milvus.

**Architecture:** Keep the deterministic Python corpus builder as the single source of truth. Add reusable business-document rendering primitives plus topic-specific operational profiles, regenerate Markdown/manifest/evaluation fixtures, then use the existing backend → AI service → Milvus ingestion path.

**Tech Stack:** Python 3, pytest, Markdown, Spring Boot, MySQL, FastAPI, LangChain text splitters, Qwen/OpenAI-compatible embeddings, Milvus 2.4.

**Spec:** `docs/superpowers/plans/2026-08-24-large-business-kb-design.md`

## Global Constraints

- Keep all 15 existing document keys and all three supported document types.
- Every document must be at least 10 times its recorded old character count and at least 11,000 characters.
- Text only; do not add images, audio, video, OCR, or other multimodal assets.
- Do not add runtime dependencies.
- Generated output must remain deterministic and reproducible.
- Do not disturb unrelated uncommitted workspace changes.

---

### Task 1: Encode corpus acceptance tests

**Files:**
- Modify: `backend/scripts/tests/test_kb_dataset.py`

- [ ] Record the old per-document character counts as a regression baseline.
- [ ] Add failing assertions for 15 documents, 10x per-document size, 11,000-character floor, three doc types, required business sections, and sufficient heading depth.
- [ ] Run the focused pytest file and confirm the new assertions fail against the old corpus.

### Task 2: Build expanded deterministic documents

**Files:**
- Modify: `backend/scripts/kb_dataset.py`

- [ ] Add focused topic profiles for operational terminology, actors, states, exceptions, evidence, service levels, and case families.
- [ ] Add rendering helpers for document control, glossary, responsibility matrix, lifecycle SOP, exception playbook, evidence checklist, service scripts, controls, metrics, cases, FAQ, and revision guidance.
- [ ] Preserve existing grounded rules and evaluation fragments.
- [ ] Run focused tests until green without weakening thresholds.

### Task 3: Regenerate checked-in corpus and evaluations

**Files:**
- Modify: `backend/src/main/resources/kbseed/generated/docs/*.md`
- Modify: `backend/src/main/resources/kbseed/generated/manifest.json`
- Modify: `eval/datasets/kb_retrieval.jsonl`

- [ ] Run the repository dataset command.
- [ ] Verify file count, per-file counts, manifest counts, and estimated chunk counts.
- [ ] Confirm deterministic regeneration has no second-run diff.

### Task 4: Validate ingestion compatibility

**Files:**
- Test only unless a defect is exposed.

- [ ] Run Python dataset and RAG splitting tests.
- [ ] Run backend seed catalog and bulk seed tests.
- [ ] Inspect generated chunks for heading preservation and configured size limits.

### Task 5: Persist and verify embeddings

**Files:**
- Runtime state only: MySQL, object storage, and Milvus.

- [ ] Start or reuse MySQL, MinIO, Milvus, backend, and AI service.
- [ ] Trigger bulk seed ingestion using the existing application path.
- [ ] Wait for all 15 documents to reach ACTIVE without fallback-only embedding failures.
- [ ] Compare MySQL chunk IDs/counts with Milvus entities.
- [ ] Execute representative retrieval queries and record top results.

### Task 6: Final evidence

- [ ] Run the complete relevant verification suite afresh.
- [ ] Review `git diff --stat` and generated statistics.
- [ ] Report document count, total characters, min/max per document, chunk count, Milvus vector count, embedding model, and retrieval observations.
