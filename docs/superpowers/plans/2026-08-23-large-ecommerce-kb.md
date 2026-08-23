# Large Ecommerce Knowledge Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build and automatically ingest a deterministic 300-document synthetic ecommerce corpus with 10k–20k chunks, configurable Chinese-aware splitting, and retrieval evaluation cases.

**Architecture:** A Python generator creates committed classpath resources plus a manifest and eval dataset. Spring Boot reads the manifest, idempotently registers/stores documents, and a bounded scheduler dispatches ingestion. FastAPI reads validated chunk settings and performs heading-aware recursive splitting.

**Tech Stack:** Python 3, pytest, FastAPI/Pydantic settings, LangChain text splitters, Java 17, Spring Boot 3, MyBatis-Plus, JUnit 5/Mockito, MinIO, MySQL, Milvus.

**Spec:** `docs/superpowers/specs/2026-08-23-large-ecommerce-kb-design.md`

## Global Constraints

- Generate exactly 300 synthetic test documents and target 10,000–20,000 chunks at defaults.
- Default splitting is 600 characters with 90-character overlap.
- Supported runtime document types remain exactly FAQ, INTRO, and POLICY.
- Supported runtime formats remain PDF, MD, and TXT.
- Dataset generation is deterministic and uses no network calls or copied marketplace prose.
- Bulk ingestion is bounded and resumable; startup must not dispatch all documents at once.
- Existing single platform policy seed remains supported.

---

### Task 1: Configurable Chinese-aware chunking

**Files:**
- Modify: `ai-service/app/config.py`
- Modify: `ai-service/app/rag/ingest.py`
- Modify: `ai-service/tests/test_rag_rrf_chunk.py`
- Modify: `docker-compose.yml`

**Interfaces:**
- Produces: `split_text(text: str, chunk_size: int | None = None, chunk_overlap: int | None = None) -> list[str]`
- Produces: settings `rag_chunk_size: int = 600`, `rag_chunk_overlap: int = 90`

- [x] Add failing tests for default maximum size, Chinese sentence boundaries, overlap preservation, heading context, and invalid settings.
- [x] Run focused pytest and confirm failures are caused by missing configurable behavior.
- [x] Implement validated settings and splitter construction with Chinese separators.
- [x] Pass settings explicitly from ingestion and expose Docker environment defaults.
- [x] Run focused and full AI-service tests.

### Task 2: Deterministic corpus generator and evaluation dataset

**Files:**
- Create: `backend/scripts/kb_dataset.py`
- Create: `backend/scripts/generate_kb_dataset.py`
- Create: `backend/scripts/tests/test_kb_dataset.py`
- Create generated: `backend/src/main/resources/kbseed/generated/manifest.json`
- Create generated: `backend/src/main/resources/kbseed/generated/docs/*`
- Create generated: `eval/dataset/kb_large_rag.jsonl`

**Interfaces:**
- Produces: `build_dataset(seed: int = 20260823) -> list[DocumentSpec]`
- Produces: manifest object `{version, generated_at, documents}` where each document has `key`, `title`, `docType`, `fileFormat`, `resource`, `topic`, and `evalTags`.

- [x] Add failing generator tests for exact count, deterministic hashes, type/format distribution, unique keys/titles, manifest validity, and 10k–20k estimated default chunks.
- [x] Run generator tests and confirm RED.
- [x] Implement focused templates and deterministic fact matrices across ecommerce domains.
- [x] Generate MD/TXT and a small valid PDF subset without network dependencies.
- [x] Emit evaluation rows covering direct, paraphrase, conditional, multi-hop, temporal/region, and hard-negative cases.
- [x] Run generator twice, compare hashes, and pass all generator tests.

### Task 3: Manifest model and idempotent bulk registration

**Files:**
- Create: `backend/src/main/java/com/aimall/backend/kb/KbSeedCatalog.java`
- Create: `backend/src/main/java/com/aimall/backend/kb/KbSeedDocument.java`
- Modify: `backend/src/main/java/com/aimall/backend/config/AppProperties.java`
- Modify: `backend/src/main/resources/application.yml`
- Modify: `backend/src/main/java/com/aimall/backend/kb/KbService.java`
- Create: `backend/src/test/java/com/aimall/backend/kb/KbBulkSeedServiceTest.java`

**Interfaces:**
- Produces: `KbSeedCatalog.load(Resource manifest)`
- Produces: `KbService.ensureBulkSeeds()` returning registration counts.

- [x] Add failing catalog tests using a real small test manifest.
- [x] Add failing service tests proving new docs are inserted/stored and existing titles are not duplicated.
- [x] Implement immutable manifest records and validation.
- [x] Add `app.seed.knowledge-base` properties: enabled, manifest, batch-size, max-concurrent, stuck-timeout-seconds.
- [x] Implement transactional idempotent registration without triggering ingestion.
- [x] Run focused backend tests.

### Task 4: Bounded resumable ingestion dispatcher

**Files:**
- Create: `backend/src/main/java/com/aimall/backend/kb/KbSeedIngestScheduler.java`
- Modify: `backend/src/main/java/com/aimall/backend/kb/KbSeedInitializer.java`
- Modify: `backend/src/main/java/com/aimall/backend/kb/KbService.java`
- Create: `backend/src/test/java/com/aimall/backend/kb/KbSeedIngestSchedulerTest.java`

**Interfaces:**
- Consumes: bulk seed title prefix/key metadata and configured limits.
- Produces: `dispatchNextBatch()` that never exceeds `maxConcurrent` PROCESSING seed documents and retries only stale/FAILED work.

- [x] Add failing tests for capacity calculation, batch limit, ACTIVE exclusion, failed/stale retry, and disabled mode.
- [x] Implement startup registration followed by bounded dispatch.
- [x] Replace the single-policy retry loop with generalized recovery while preserving original policy behavior.
- [x] Ensure individual dispatch errors mark only that document FAILED.
- [x] Run focused and full backend tests.

### Task 5: Documentation and end-to-end verification

**Files:**
- Modify: `README.md`
- Modify: `eval/README.md` if present
- Modify: `docs/superpowers/plans/2026-08-23-large-ecommerce-kb.md` (check off completed work)

**Interfaces:** None.

- [x] Document dataset scope, synthetic-data warning, generation command, seed switches, ingestion pacing, chunk variables, expected time/cost, and reset behavior.
- [x] Run the generator statistics command and record actual document/type/format/character/estimated-chunk totals.
- [x] Run all Python generator and AI-service tests.
- [x] Run all Maven backend tests.
- [x] Validate manifest resources are packaged in the backend artifact.
- [x] Inspect working-tree changes manually because this workspace has no Git metadata.

## Verification Record (2026-08-23)

- Generated: 300 documents, 6,186,020 source characters.
- Distribution: FAQ 120 / INTRO 100 / POLICY 80; MD 240 / TXT 50 / PDF 10.
- Actual default split result: 19,502 chunks; per-document range 37–73; maximum chunk length 600.
- Generator tests: 3 passed.
- AI-service tests: 34 passed (third-party pytest-asyncio deprecation warnings only).
- Backend Maven tests: passed.
- Backend package inspection: manifest plus exactly 300 generated documents present in the executable JAR.
- `docker compose config -q`: passed.
- Git commits omitted because the supplied workspace has no `.git` metadata.
