# T10 RAG Retrieval Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace knowledge-base search with normalized dual retrieval, strict chunk-id RRF, optional Qwen3 reranking, calibrated answerability, structured source context, and deterministic citation validation.

**Architecture:** The AI service gains a typed retrieval pipeline under `app/rag`; `kb_search` becomes a thin adapter. The backend replaces LIKE-count ranking with exact Okapi BM25 over ACTIVE chunks. RAG answer text is buffered after `kb_search` and released only after citation validation.

**Tech Stack:** Python 3.11+, FastAPI, LangChain/LangGraph, httpx, Pydantic Settings, pytest; Java 17, Spring Boot, MyBatis-Plus, JUnit 5, Mockito; MySQL and Milvus adapters.

**Spec:** `docs/superpowers/specs/2026-08-23-t10-rag-retrieval-redesign.md`

## Global Constraints

- Preserve every pre-existing uncommitted Stage 1 change; stage only files explicitly listed per task.
- Fixed order: normalized query → vector top-20 plus BM25 top-20 → metadata filter → chunk-id RRF top-10 → optional reranker top-4.
- ACTIVE is a storage-validity filter; `doc_type` and `product_id` are applied after both ranked lists return.
- Discard candidates missing `chunk_id`; never deduplicate production candidates by content.
- BM25 presence is never required for answerability.
- Reranker defaults off and is configured for local `Qwen/Qwen3-Reranker-4B`; failure degrades to RRF top-4.
- Citation failure returns deterministic insufficient-evidence text and never makes a second LLM call.
- Add no Elasticsearch/OpenSearch or new Python HTTP dependency; use existing `httpx`.
- Never expose API keys, full source text in ordinary logs, or internal titles such as `知识库文档#4`.

---

## File Responsibility Map

- `ai-service/app/rag/retrieval.py`: types, normalization, filtering, RRF, score normalization, answerability, source construction, orchestration.
- `ai-service/app/rag/reranker.py`: reranker protocol and Qwen-compatible HTTP client.
- `ai-service/app/rag/citations.py`: citation extraction and deterministic final-answer validation.
- `ai-service/app/rag/vectorstore.py`: vector top-20 adapter with complete metadata.
- `ai-service/app/tools/tools.py`: thin tool adapter and request-context propagation.
- `ai-service/app/api/chat.py`: RAG-only buffering and final guard.
- `backend/src/main/java/com/aimall/backend/internal/Bm25Retriever.java`: tokenizer and Okapi ranking.
- `backend/src/main/java/com/aimall/backend/internal/InternalKbController.java`: ACTIVE corpus loading and response contract.
- `eval/scripts/calibrate_answerability.py`: report-only threshold sweep.

### Task 1: Retrieval configuration contract

**Files:**
- Modify: `ai-service/app/config.py`
- Modify: `ai-service/.env.example`
- Modify: `docker-compose.yml`
- Create: `ai-service/tests/test_rag_config.py`

**Interfaces:**
- Consumes: existing `Settings`.
- Produces: `rag_vector_recall_k`, `rag_bm25_recall_k`, `rag_rrf_k`, `rag_rrf_top_k`, `rag_final_top_k`, answer-score fields, and `rag_reranker_*` fields.

- [ ] **Step 1: Write the failing settings tests**

```python
import pytest
from pydantic import ValidationError
from app.config import Settings


def test_t10_defaults():
    s = Settings(_env_file=None)
    assert (s.rag_vector_recall_k, s.rag_bm25_recall_k) == (20, 20)
    assert (s.rag_rrf_k, s.rag_rrf_top_k, s.rag_final_top_k) == (60, 10, 4)
    assert (s.rag_answer_min_score, s.rag_answer_high_confidence_score) == (.45, .65)
    assert s.rag_answer_min_margin == .05
    assert s.rag_reranker_enabled is False
    assert s.rag_reranker_model == "Qwen/Qwen3-Reranker-4B"


@pytest.mark.parametrize("values", [
    {"rag_final_top_k": 11, "rag_rrf_top_k": 10},
    {"rag_rrf_top_k": 21},
    {"rag_answer_min_score": -.01},
    {"rag_answer_high_confidence_score": 1.01},
    {"rag_vector_score_scale": 0},
    {"rag_reranker_timeout_s": 0},
])
def test_invalid_settings_fail(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)
```

- [ ] **Step 2: Verify RED**

Run: `cd ai-service; python -m pytest tests/test_rag_config.py -q`  
Expected: FAIL because T10 fields are absent.

- [ ] **Step 3: Implement exact defaults and validation**

Use Pydantic `Field` bounds for positive counts/scales/timeouts and `[0,1]` scores. Extend the model validator with:

```python
if self.rag_final_top_k > self.rag_rrf_top_k:
    raise ValueError("rag_final_top_k must not exceed rag_rrf_top_k")
if self.rag_rrf_top_k > min(self.rag_vector_recall_k, self.rag_bm25_recall_k):
    raise ValueError("rag_rrf_top_k must fit within recall windows")
if self.rag_answer_min_score > self.rag_answer_high_confidence_score:
    raise ValueError("rag_answer_min_score must not exceed high confidence score")
```

Add every spec key to `.env.example`; add disabled Qwen defaults to the `ai-service` environment in `docker-compose.yml` without adding a reranker container.

- [ ] **Step 4: Verify GREEN**

Run: `cd ai-service; python -m pytest tests/test_rag_config.py tests/test_rag_rrf_chunk.py::TestChunkSettings -q`  
Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```powershell
git add -- ai-service/app/config.py ai-service/.env.example docker-compose.yml ai-service/tests/test_rag_config.py
git commit -m "feat(rag): configure T10 retrieval pipeline"
```

### Task 2: Pure retrieval primitives and answerability

**Files:**
- Create: `ai-service/app/rag/retrieval.py`
- Create: `ai-service/tests/test_rag_retrieval.py`
- Modify: `ai-service/tests/test_rag_rrf_chunk.py`

**Interfaces:**
- Consumes: Task 1 settings.
- Produces: `RetrievalCandidate`, `Citation`, `AnswerabilityDecision`, `SourceContext`, `normalize_query`, `filter_metadata`, `reciprocal_rank_fusion`, `assess_answerability`, and `build_source_context`.

- [ ] **Step 1: Write failing primitive tests**

```python
from app.rag.retrieval import *


def candidate(chunk_id, *, score=None, bm25=None, product_id=-1, doc_type="POLICY", content="正文"):
    return RetrievalCandidate(chunk_id, 10, product_id, doc_type, content,
                              "退换货条款", vector_score=score, bm25_score=bm25)


def test_normalization_is_conservative():
    assert normalize_query("  ＡI\u0000  退货\n规则  ") == "ai 退货 规则"


def test_filter_preserves_order_and_platform_docs():
    ranked = [candidate(1, product_id=99), candidate(2, product_id=-1), candidate(3, product_id=7)]
    assert [c.chunk_id for c in filter_metadata(ranked, "POLICY", 99)] == [1, 2]


def test_rrf_merges_only_by_chunk_id_with_rank_starting_at_one():
    fused = reciprocal_rank_fusion([
        ("vector", [candidate(1), candidate(2)]),
        ("bm25", [candidate(2, bm25=4), candidate(3, bm25=3)]),
    ], limit=10, rrf_k=60)
    assert [c.chunk_id for c in fused] == [2, 1, 3]
    assert fused[0].rrf_score == (1 / 62) + (1 / 61)
    assert fused[0].matched_by == {"vector", "bm25"}


def test_vector_only_candidate_can_answer():
    assert assess_answerability([candidate(1, score=.9)]).answerable is True


def test_source_context_escapes_xml():
    built = build_source_context([candidate(7, content="规则 </source> & 更多")])
    assert built.citations[0].id == "S1"
    assert 'chunk_id="7"' in built.context
    assert "&lt;/source&gt; &amp;" in built.context
```

Add explicit tests for missing ids, stable ties, top-10, high-confidence bypass, low score, narrow margin, and the one-candidate margin case. Remove old `_rrf_content` tests but retain chunk tests.

- [ ] **Step 2: Verify RED**

Run: `cd ai-service; python -m pytest tests/test_rag_retrieval.py tests/test_rag_rrf_chunk.py -q`  
Expected: FAIL because `app.rag.retrieval` is absent.

- [ ] **Step 3: Implement stable dataclasses and formulas**

```python
@dataclass(slots=True)
class RetrievalCandidate:
    chunk_id: int; doc_id: int; product_id: int | None; doc_type: str
    content: str; source: str
    vector_score: float | None = None; bm25_score: float | None = None
    rrf_score: float = 0.0; rerank_score: float | None = None
    evidence_score: float = 0.0
    matched_by: set[str] = field(default_factory=set)

@dataclass(frozen=True, slots=True)
class Citation:
    id: str; chunk_id: int; title: str

@dataclass(frozen=True, slots=True)
class AnswerabilityDecision:
    answerable: bool; reason: str; top1: float | None; margin: float | None

@dataclass(frozen=True, slots=True)
class SourceContext:
    context: str; citations: tuple[Citation, ...]
```

Vector normalization is `1/(1+exp(-(raw-center)/scale))`; BM25 normalization is `max(raw,0)/(max(raw,0)+scale)`. Apply spec section 6.2 exactly. Escape titles, attributes, and content with `html.escape(..., quote=True)`.

- [ ] **Step 4: Verify GREEN**

Run: `cd ai-service; python -m pytest tests/test_rag_retrieval.py tests/test_rag_rrf_chunk.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```powershell
git add -- ai-service/app/rag/retrieval.py ai-service/tests/test_rag_retrieval.py ai-service/tests/test_rag_rrf_chunk.py
git commit -m "feat(rag): add fusion and answerability primitives"
```

### Task 3: Exact backend BM25 retrieval

**Files:**
- Create: `backend/src/main/java/com/aimall/backend/internal/Bm25Retriever.java`
- Create: `backend/src/test/java/com/aimall/backend/internal/Bm25RetrieverTest.java`
- Create: `backend/src/test/java/com/aimall/backend/internal/InternalKbSearchTest.java`
- Modify: `backend/src/main/java/com/aimall/backend/internal/InternalKbController.java`

**Interfaces:**
- Consumes: ACTIVE `KbDoc` and associated `KbChunk` rows.
- Produces: `Bm25Retriever.search(String, List<Document>, int)` and complete `/internal/kb/search` hits.

- [ ] **Step 1: Write failing BM25 unit tests**

```java
class Bm25RetrieverTest {
    private final Bm25Retriever retriever = new Bm25Retriever(1.5, 0.75);

    @Test void tokenizesChineseBigramsAndAsciiWords() {
        assertEquals(List.of("退换", "换货", "iphone15"),
                retriever.tokenize("退换货 iPhone15"));
    }

    @Test void ranksRareRelevantTermsFirst() {
        var corpus = List.of(
            new Bm25Retriever.Document(1L, 10L, null, "POLICY", "七天无理由退货", "退换货条款"),
            new Bm25Retriever.Document(2L, 11L, null, "POLICY", "七天配送说明", "配送条款"),
            new Bm25Retriever.Document(3L, 12L, null, "POLICY", "保修说明", "保修条款"));
        var hits = retriever.search("无理由退货", corpus, 20);
        assertEquals(1L, hits.get(0).document().chunkId());
        assertTrue(hits.get(0).score() > 0);
    }

    @Test void capsOutputAtTwenty() {
        var corpus = LongStream.rangeClosed(1, 30)
            .mapToObj(i -> new Bm25Retriever.Document(i, i, null, "FAQ", "退货规则" + i, "规则"))
            .toList();
        assertEquals(20, retriever.search("退货", corpus, 200).size());
    }
}
```

- [ ] **Step 2: Verify RED**

Run: `cd backend; mvn -Dtest=Bm25RetrieverTest test`  
Expected: FAIL because `Bm25Retriever` is absent.

- [ ] **Step 3: Implement exact Okapi scoring**

Create a Spring component with:

```java
public record Document(Long chunkId, Long docId, Long productId,
                       String docType, String content, String source) {}
public record Hit(Document document, double score) {}
```

Tokenize Chinese as overlapping bigrams and ASCII as lowercase alphanumeric words. Deduplicate query terms. Compute per-document TF, corpus DF, average length, and the spec's IDF/score formula with `k1=1.5`, `b=.75`. Remove zero scores; sort score descending then chunk id ascending; clamp output count to 1..20.

- [ ] **Step 4: Write a failing controller contract test**

Mock both mappers and call `controller.search(body)`. Supply one ACTIVE and one non-ACTIVE doc and assert only the ACTIVE id loads chunks. Assert the returned hit:

```java
assertEquals(1L, hit.get("chunk_id"));
assertEquals(10L, hit.get("doc_id"));
assertTrue(hit.containsKey("product_id"));
assertEquals("POLICY", hit.get("docType"));
assertEquals("退换货条款", hit.get("source"));
assertTrue(((Number) hit.get("score")).doubleValue() > 0);
```

Run: `cd backend; mvn -Dtest=Bm25RetrieverTest,InternalKbSearchTest test`  
Expected: FAIL because the controller still uses LIKE-count ranking and omits fields.

- [ ] **Step 5: Replace controller search orchestration**

Inject `Bm25Retriever`. Query `status=ACTIVE` and `deleted=0` docs, then load chunks for those ids. Build `Document` values with titles and call `search(query, corpus, topK)`. Do not apply request `docType` or `productId`. Return `chunk_id`, `doc_id`, `product_id`, `docType`, `content`, `source`, `score`, and `total`. Empty query/corpus returns empty success.

- [ ] **Step 6: Verify GREEN**

Run: `cd backend; mvn -Dtest=Bm25RetrieverTest,InternalKbSearchTest test`  
Expected: PASS.

- [ ] **Step 7: Commit Task 3**

```powershell
git add -- backend/src/main/java/com/aimall/backend/internal/Bm25Retriever.java backend/src/main/java/com/aimall/backend/internal/InternalKbController.java backend/src/test/java/com/aimall/backend/internal/Bm25RetrieverTest.java backend/src/test/java/com/aimall/backend/internal/InternalKbSearchTest.java
git commit -m "feat(rag): replace keyword count with BM25"
```

### Task 4: Qwen-compatible optional reranker

**Files:**
- Create: `ai-service/app/rag/reranker.py`
- Create: `ai-service/tests/test_rag_reranker.py`

**Interfaces:**
- Consumes: `RetrievalCandidate` and `rag_reranker_*` settings.
- Produces: `Reranker` protocol, `QwenHttpReranker.rerank(query, candidates)`, and `get_reranker()`.

- [ ] **Step 1: Write failing HTTP contract tests**

```python
class FakeResponse:
    def __init__(self, payload): self.payload = payload
    def raise_for_status(self): return None
    def json(self): return self.payload

def candidate(chunk_id):
    return RetrievalCandidate(chunk_id, 10, -1, "POLICY", f"正文{chunk_id}", "条款")

@pytest.mark.asyncio
async def test_qwen_request_and_sort(monkeypatch):
    seen = {}
    async def fake_post(self, url, **kwargs):
        seen.update(url=url, **kwargs)
        return FakeResponse({"results": [
            {"index": 1, "relevance_score": .91},
            {"index": 0, "relevance_score": .32},
        ]})
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    ranked = await QwenHttpReranker(settings).rerank("退货", [candidate(10), candidate(20)])
    assert seen["json"]["model"] == "Qwen/Qwen3-Reranker-4B"
    assert seen["json"]["documents"] == ["正文10", "正文20"]
    assert [c.chunk_id for c in ranked] == [20, 10]
```

Add cases for duplicate/missing/out-of-range indexes, scores outside `[0,1]`, HTTP failure, and disabled `get_reranker() is None`.

- [ ] **Step 2: Verify RED**

Run: `cd ai-service; python -m pytest tests/test_rag_reranker.py -q`  
Expected: FAIL because the module is absent.

- [ ] **Step 3: Implement the provider boundary**

```python
class Reranker(Protocol):
    async def rerank(self, query: str,
                     candidates: list[RetrievalCandidate]) -> list[RetrievalCandidate]: ...
```

Post `{model, query, documents, top_n}` to `base_url + endpoint`; send Bearer auth only for a non-empty key; use configured timeout. Require exactly one valid result per input. Copy `relevance_score` to both `rerank_score` and `evidence_score`; sort descending and retain original RRF order for ties. Log neither documents nor headers.

- [ ] **Step 4: Verify GREEN**

Run: `cd ai-service; python -m pytest tests/test_rag_reranker.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```powershell
git add -- ai-service/app/rag/reranker.py ai-service/tests/test_rag_reranker.py
git commit -m "feat(rag): add optional Qwen reranker client"
```

### Task 5: Retrieval pipeline orchestration and adapters

**Files:**
- Modify: `ai-service/app/rag/retrieval.py`
- Modify: `ai-service/app/rag/vectorstore.py`
- Modify: `ai-service/app/clients/backend_client.py`
- Create: `ai-service/tests/test_rag_pipeline.py`
- Modify: `ai-service/tests/conftest.py`
- Modify: `ai-service/app/observability/telemetry.py`
- Create: `ai-service/tests/test_rag_telemetry.py`

**Interfaces:**
- Consumes: `VectorStore.search(query, top_k=20)`, `BackendClient.kb_keyword_search(query, top_k=20)`, and optional `Reranker`.
- Produces: `RetrievalResult`, `RetrievalPipeline.search(query, doc_type="ALL", product_id=None)`, and `get_retrieval_pipeline()`.

- [ ] **Step 1: Write failing orchestration tests**

```python
def raw_hit(chunk_id, *, product_id=-1, score=.9):
    return {"chunk_id": chunk_id, "doc_id": 10, "product_id": product_id,
            "docType": "POLICY", "content": "退货正文",
            "source": "退换货条款", "score": score}

async def good_vector(query, top_k):
    return {"hits": [raw_hit(1, score=.9)]}

@pytest.mark.asyncio
async def test_both_top_twenty_then_filter_fuse_and_build_sources():
    vector = AsyncMock(return_value={"hits": [raw_hit(1, product_id=7, score=.9)]})
    bm25 = AsyncMock(return_value={"hits": [raw_hit(1, product_id=7, score=9.0)]})
    pipeline = RetrievalPipeline(vector_search=vector, bm25_search=bm25, reranker=None)
    result = await pipeline.search("  退货  ", doc_type="POLICY", product_id=7)
    vector.assert_awaited_once_with("退货", top_k=20)
    bm25.assert_awaited_once_with("退货", top_k=20)
    assert result.answerable is True
    assert result.hits[0].chunk_id == 1
    assert result.citations[0].id == "S1"
    assert '<source id="S1"' in result.context


@pytest.mark.asyncio
async def test_failed_bm25_leg_degrades_without_vetoing_vector_answer():
    async def broken(*args, **kwargs):
        raise RuntimeError("offline")
    pipeline = RetrievalPipeline(vector_search=good_vector, bm25_search=broken, reranker=None)
    result = await pipeline.search("保修")
    assert result.answerable is True
    assert result.degraded is True
    assert "bm25_unavailable" in result.degraded_reasons
```

Add tests proving concurrent start, both-leg failure, both-leg empty, metadata filtering before RRF, invalid query skipping adapters, reranker success top-4, and reranker exception fallback top-4. In `test_rag_telemetry.py`, install a fake trace, execute one search, and assert the completed `rag::hybrid_retrieval` span contains normalized-query summary, each leg count, post-filter counts, RRF/rerank counts, top1, margin, decision reason, and degradation reasons, while serialized output contains neither candidate `content` nor authorization headers.

- [ ] **Step 2: Verify RED**

Run: `cd ai-service; python -m pytest tests/test_rag_pipeline.py -q`  
Expected: FAIL because `RetrievalPipeline` is absent.

- [ ] **Step 3: Make adapters metadata-complete**

Change vector search to request the provided top count without `doc_type/product_id` request filters and include `chunk_id`, `doc_id`, `product_id`, `docType`, `content`, `source`, and `score`. Change backend keyword search to send normalized `query` and `topK`; preserve optional Python parameters only if source compatibility requires it. Update `_FakeVectorStore.search` accordingly.

- [ ] **Step 4: Implement orchestration**

Use `asyncio.gather(..., return_exceptions=True)`. Parse raw hits, discard malformed identities, filter each ranked list, RRF top-10, optionally rerank, select top-4, assign evidence scores, assess answerability, and only then build context.

```python
@dataclass(frozen=True, slots=True)
class RetrievalResult:
    answerable: bool
    reason: str
    hits: tuple[RetrievalCandidate, ...]
    context: str
    citations: tuple[Citation, ...]
    degraded: bool
    degraded_reasons: tuple[str, ...]
```

Both exceptions yield `retrieval_unavailable`; successful empty/weak evidence yields `insufficient_evidence`. An enabled reranker exception appends `reranker_unavailable` and uses RRF top-4. Extend `span_ctx` with a `complete(output)` method, wrap the whole pipeline in `rag::hybrid_retrieval`, and complete it with counts and decision metadata only—never source content or secrets.

- [ ] **Step 5: Verify GREEN**

Run: `cd ai-service; python -m pytest tests/test_rag_pipeline.py tests/test_rag_retrieval.py tests/test_rag_reranker.py tests/test_rag_telemetry.py -q`  
Expected: PASS.

- [ ] **Step 6: Commit Task 5**

```powershell
git add -- ai-service/app/rag/retrieval.py ai-service/app/rag/vectorstore.py ai-service/app/clients/backend_client.py ai-service/tests/test_rag_pipeline.py ai-service/tests/conftest.py ai-service/app/observability/telemetry.py ai-service/tests/test_rag_telemetry.py
git commit -m "feat(rag): orchestrate hybrid retrieval pipeline"
```

### Task 6: Tool protocol and source-aware prompt

**Files:**
- Modify: `ai-service/app/tools/tools.py`
- Modify: `ai-service/app/agent/prompts.py`
- Create: `ai-service/tests/test_kb_search_tool.py`

**Interfaces:**
- Consumes: `get_retrieval_pipeline().search(...) -> RetrievalResult`.
- Produces: tool keys `answerable`, `reason`, `context`, `citations`, `hits`, `degraded`, `degraded_reasons`; context keys `rag_used`, `rag_answerable`, `rag_reason`, `rag_allowed_citations`.

- [ ] **Step 1: Write failing tool tests**

```python
class FakePipeline:
    def __init__(self, result): self.result = result
    async def search(self, *args, **kwargs): return self.result

def answerable_result():
    hit = RetrievalCandidate(1, 10, -1, "POLICY", "七天退货", "退换货条款", vector_score=.9)
    return RetrievalResult(True, "answerable", (hit,),
        '<source id="S1" chunk_id="1" title="退换货条款">七天退货</source>',
        (Citation("S1", 1, "退换货条款"),), False, ())

@pytest.mark.asyncio
async def test_kb_search_returns_context_and_records_allowed_ids(monkeypatch):
    monkeypatch.setattr(retrieval, "get_retrieval_pipeline",
                        lambda: FakePipeline(answerable_result()))
    set_tool_ctx({})
    result = await kb_search.ainvoke({"query": "七天退货", "doc_type": "POLICY"})
    assert result["answerable"] is True
    assert result["context"].startswith('<source id="S1"')
    assert result["citations"] == [
        {"id": "S1", "chunk_id": 1, "title": "退换货条款"}
    ]
    assert get_tool_ctx()["rag_allowed_citations"] == {
        "S1": result["citations"][0]
    }
```

Add insufficient-evidence, retrieval-unavailable, and degraded-context cases.

- [ ] **Step 2: Verify RED**

Run: `cd ai-service; python -m pytest tests/test_kb_search_tool.py -q`  
Expected: FAIL because `kb_search` still owns both retrieval legs and RRF.

- [ ] **Step 3: Replace tool-local retrieval logic**

Delete `_rrf_content` and direct adapter calls. Call the pipeline once, serialize dataclasses to the exact protocol, and store only citation ids/titles/chunk ids in request context. Set `rag_used=True` for every call. Set global degraded for `retrieval_unavailable` or pipeline degradation. Do not store allowed ids when answerability is false.

- [ ] **Step 4: Update prompt rules**

Replace title-only citation instructions with:

```text
kb_search 返回 context 时，只能依据 <source id="Sx">...</source> 中的内容回答。
每个知识库事实句末必须引用对应的 [Sx]；禁止使用 context 中不存在的 id。
answerable=false 时必须说明当前证据不足，不得根据常识补全政策。
```

Keep the ban on internal fallback titles.

- [ ] **Step 5: Verify GREEN**

Run: `cd ai-service; python -m pytest tests/test_kb_search_tool.py tests/test_rag_rrf_chunk.py -q`  
Expected: PASS.

- [ ] **Step 6: Commit Task 6**

```powershell
git add -- ai-service/app/tools/tools.py ai-service/app/agent/prompts.py ai-service/tests/test_kb_search_tool.py
git commit -m "feat(rag): expose structured source context"
```

### Task 7: Citation guard and RAG-safe streaming

**Files:**
- Create: `ai-service/app/rag/citations.py`
- Create: `ai-service/tests/test_rag_citations.py`
- Modify: `ai-service/app/api/chat.py`
- Create: `ai-service/tests/test_chat_rag_citations.py`

**Interfaces:**
- Consumes: answer text and request-context `rag_used`, `rag_answerable`, `rag_reason`, `rag_allowed_citations`.
- Produces: `CitationValidation`, `validate_citations(...)`, and an SSE stream whose RAG tokens concatenate exactly to `done.content`.

- [ ] **Step 1: Write failing guard tests**

```python
from app.rag.citations import validate_citations

ALLOWED = {"S1": {"id": "S1", "chunk_id": 7, "title": "退换货条款"}}


def test_valid_ids_return_referenced_metadata():
    result = validate_citations("支持七天退货。[S1]", allowed=ALLOWED, answerable=True)
    assert result.valid is True
    assert result.content == "支持七天退货。[S1]"
    assert result.citations == (ALLOWED["S1"],)


def test_missing_and_unknown_ids_fail():
    assert validate_citations("支持七天退货。", allowed=ALLOWED,
                              answerable=True).reason == "missing_citation"
    assert validate_citations("支持七天退货。[S9]", allowed=ALLOWED,
                              answerable=True).reason == "unknown_citation"


def test_unanswerable_cannot_emit_substantive_answer():
    result = validate_citations("我认为可以退货。", allowed={}, answerable=False)
    assert result.valid is False
    assert result.content == "当前知识库证据不足，暂时无法可靠回答该问题。"
```

Add referenced-id deduplication/order and `retrieval_unavailable` wording tests.

- [ ] **Step 2: Verify RED**

Run: `cd ai-service; python -m pytest tests/test_rag_citations.py -q`  
Expected: FAIL because the module is absent.

- [ ] **Step 3: Implement deterministic validation**

Extract ids with `\[(S[1-9][0-9]*)\]`. For answerable knowledge context, require at least one id and reject any unknown id. For unanswerable context, replace substantive model output. Select `知识库暂时不可用，请稍后再试。` for `retrieval_unavailable`. This module must not import or call an LLM.

```python
@dataclass(frozen=True, slots=True)
class CitationValidation:
    content: str
    citations: tuple[dict, ...]
    valid: bool
    reason: str
```

- [ ] **Step 4: Write failing SSE tests**

Simulate events: `kb_search on_tool_end`, answer tokens `支持七天` and `退货。[S1]`, then graph end. Assert no RAG answer token is yielded before completion, then:

```python
assert "".join(e["content"] for e in token_events) == done["content"]
assert done["citations"] == [
    {"id": "S1", "chunk_id": 7, "title": "退换货条款"}
]
```

Add unknown-id coverage proving invalid model text appears in no token event.

- [ ] **Step 5: Implement RAG-only buffering**

Keep ordinary streaming unchanged until `ctx["rag_used"]` is true. Buffer RAG natural-language parts, validate after graph completion, emit one validated token event, then `done` with identical content and citations. Tool events remain immediate. Apply existing link guard after citation validation and prove it leaves source ids unchanged.

- [ ] **Step 6: Verify GREEN**

Run: `cd ai-service; python -m pytest tests/test_rag_citations.py tests/test_chat_rag_citations.py -q`  
Expected: PASS.

- [ ] **Step 7: Commit Task 7**

```powershell
git add -- ai-service/app/rag/citations.py ai-service/tests/test_rag_citations.py ai-service/app/api/chat.py ai-service/tests/test_chat_rag_citations.py
git commit -m "feat(rag): validate citations before streaming"
```

### Task 8: Calibration, documentation, and full verification

**Files:**
- Create: `eval/dataset/rag_answerability.jsonl`
- Create: `eval/scripts/calibrate_answerability.py`
- Create: `eval/tests/test_calibrate_answerability.py`
- Modify: `eval/README.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: JSONL rows `{query, answerable, top1, top2}`.
- Produces: report keys `best`, `candidates`, and per-candidate `precision`, `recall`, `f1`, `reject_rate`; never changes app configuration.

- [ ] **Step 1: Write failing calibration tests**

```python
from eval.scripts.calibrate_answerability import evaluate_thresholds, sweep


def test_metrics_are_reproducible():
    rows = [
        {"answerable": True, "top1": .80, "top2": .20},
        {"answerable": True, "top1": .70, "top2": .69},
        {"answerable": False, "top1": .30, "top2": .29},
        {"answerable": False, "top1": .50, "top2": .49},
    ]
    metrics = evaluate_thresholds(rows, min_score=.45,
                                  high_score=.65, min_margin=.05)
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["reject_rate"] == .5


def test_sweep_only_returns_a_report(tmp_path):
    report = sweep([
        {"answerable": True, "top1": .8, "top2": .2},
        {"answerable": False, "top1": .3, "top2": .29},
    ])
    assert {"min_score", "high_score", "min_margin", "f1"} <= report["best"].keys()
    assert list(tmp_path.iterdir()) == []
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest eval/tests/test_calibrate_answerability.py -q`  
Expected: FAIL because calibration code is absent.

- [ ] **Step 3: Implement report-only sweep**

Apply the production decision rule to these finite grids:

```python
MIN_SCORES = [.30, .35, .40, .45, .50, .55]
HIGH_SCORES = [.55, .60, .65, .70, .75, .80]
MARGINS = [.00, .03, .05, .08, .10, .15]
```

Sort by F1 descending, precision descending, reject rate ascending, then parameter tuple. CLI accepts required `--input` and `--output`; only the explicit output is written. Seed at least six answerable and six unanswerable policy, warranty, unrelated, and ambiguous cases.

- [ ] **Step 4: Document operation**

Document schema and:

```powershell
python eval/scripts/calibrate_answerability.py --input eval/dataset/rag_answerability.jsonl --output eval/results/answerability-calibration.json
```

Root README documents fixed stages, citation syntax, degradation, and local Qwen fields. State defaults are uncalibrated baselines and the report never edits `.env`.

- [ ] **Step 5: Verify calibration tests**

Run: `python -m pytest eval/tests/test_calibrate_answerability.py -q`  
Expected: PASS.

- [ ] **Step 6: Run complete verification**

```powershell
cd ai-service
python -m pytest -q
cd ..\backend
mvn test
cd ..
python eval/scripts/calibrate_answerability.py --input eval/dataset/rag_answerability.jsonl --output eval/results/answerability-calibration.json
```

Expected: all tests PASS; report contains `best` and `candidates`; unit tests require no network service.

- [ ] **Step 7: Inspect preservation and diff health**

```powershell
git status --short
git diff --check
git diff --stat
```

Confirm pre-existing embedding fallback, generated corpus, and dataset edits remain present and were neither reverted nor accidentally staged.

- [ ] **Step 8: Commit Task 8**

```powershell
git add -- eval/dataset/rag_answerability.jsonl eval/scripts/calibrate_answerability.py eval/tests/test_calibrate_answerability.py eval/README.md README.md
git commit -m "test(rag): add answerability calibration workflow"
```

- [ ] **Step 9: Record completion evidence**

Report exact test counts, elapsed times, the calibration best candidate, and remaining `git status --short` entries. Do not claim completion while a required suite fails.
