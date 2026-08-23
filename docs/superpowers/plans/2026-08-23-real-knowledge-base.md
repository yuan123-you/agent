# AI Mall Real Knowledge Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace repetitive synthetic RAG seed documents with a curated, production-style AI Mall service knowledge corpus and natural-language retrieval evaluations.

**Architecture:** Keep the existing Python dataset entry points and Java seed ingestion contract. Define a fixed set of focused Markdown documents in the generator, validate their metadata/content, remove stale generated files before writing, and derive a manifest plus one grounded evaluation row per document.

**Tech Stack:** Python 3 standard library, pytest, Markdown, JSON/JSONL, existing Spring Boot seed loader.

**Spec:** `docs/superpowers/specs/2026-08-23-real-knowledge-base-design.md`

## Global Constraints

- Keep `DocumentSpec`, `build_dataset()` and `write_dataset()` compatible with existing callers.
- Do not change vector storage, chunking, admin APIs, upload UI or chat prompts.
- Add no dependencies.
- Use `platform-policies.md` as the factual baseline.
- Do not use synthetic titles, fake KB codes, random regional rules or repeated filler.
- Generated seed documents use UTF-8 Markdown.

---

### Task 1: Define corpus quality contract

**Files:**
- Modify: `backend/scripts/tests/test_kb_dataset.py`
- Test: `backend/scripts/tests/test_kb_dataset.py`

**Interfaces:**
- Consumes: existing `build_dataset()` and `write_dataset()`.
- Produces: executable requirements for 15 formal documents, valid manifests and grounded evaluations.

- [ ] Replace synthetic scale assertions with formal title, topic, Markdown and forbidden-marker assertions.
- [ ] Add assertions that all expected service domains are covered and each document has useful structural sections.
- [ ] Add stale-output cleanup coverage.
- [ ] Run `python -m pytest backend/scripts/tests/test_kb_dataset.py -q` and confirm failure against the synthetic implementation.

### Task 2: Implement curated corpus generator

**Files:**
- Modify: `backend/scripts/kb_dataset.py`
- Test: `backend/scripts/tests/test_kb_dataset.py`

**Interfaces:**
- Consumes: no external services; existing `platform-policies.md` concepts.
- Produces: `build_dataset(seed: int = SEED) -> list[DocumentSpec]` and `write_dataset(output_root: Path, eval_path: Path, seed: int = SEED) -> dict`.

- [ ] Replace random template expansion and PDF construction with fixed formal document definitions.
- [ ] Add small validation for duplicate/empty/forbidden corpus data.
- [ ] Generate grounded natural-language evaluation rows.
- [ ] Remove stale files from the generated docs directory before writing.
- [ ] Run the focused tests until green.

### Task 3: Regenerate tracked corpus and evaluations

**Files:**
- Replace: `backend/src/main/resources/kbseed/generated/docs/*`
- Modify: `backend/src/main/resources/kbseed/generated/manifest.json`
- Modify: `eval/dataset/kb_large_rag.jsonl`

**Interfaces:**
- Consumes: `write_dataset()`.
- Produces: classpath resources consumed by `KbSeedCatalog` and retrieval evaluation tooling.

- [ ] Run the dataset generator using the repository paths.
- [ ] Inspect titles, resource paths, character counts and evaluation rows.
- [ ] Confirm no stale `synthetic-kb-*` files remain.

### Task 4: Verify compatibility and quality

**Files:**
- Test: `backend/scripts/tests/test_kb_dataset.py`
- Test: relevant backend knowledge-base tests discovered in the repository.

**Interfaces:**
- Consumes: regenerated manifest and documents.
- Produces: verification evidence.

- [ ] Run Python dataset tests.
- [ ] Run static corpus scans for forbidden synthetic markers and missing resources.
- [ ] Run relevant backend tests or report an exact environmental blocker.
- [ ] Review `git diff` to ensure only intended corpus/generator/test/design/plan changes were introduced by this task.
