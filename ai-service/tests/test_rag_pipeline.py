import asyncio
import logging
from unittest.mock import AsyncMock

import pytest

from app.clients.backend_client import BackendClient
from app.rag import retrieval
from app.rag.retrieval import RetrievalPipeline
from app.rag.vectorstore import VectorStore


def raw_hit(chunk_id, *, product_id=-1, doc_type="POLICY", score=.9, content="退货正文"):
    return {
        "chunk_id": chunk_id,
        "doc_id": 10,
        "product_id": product_id,
        "docType": doc_type,
        "content": content,
        "source": "退换货条款",
        "score": score,
    }


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
    assert result.hits[0].matched_by == {"vector", "bm25"}
    assert result.citations[0].id == "S1"
    assert '<source id="S1"' in result.context


@pytest.mark.asyncio
async def test_recall_legs_start_concurrently():
    vector_started = asyncio.Event()
    bm25_started = asyncio.Event()

    async def vector(query, top_k):
        vector_started.set()
        await asyncio.wait_for(bm25_started.wait(), timeout=.2)
        return {"hits": []}

    async def bm25(query, top_k):
        bm25_started.set()
        await asyncio.wait_for(vector_started.wait(), timeout=.2)
        return {"hits": []}

    result = await RetrievalPipeline(vector_search=vector, bm25_search=bm25, reranker=None).search("退货")

    assert result.reason == "insufficient_evidence"


@pytest.mark.asyncio
async def test_failed_bm25_leg_degrades_without_vetoing_vector_answer():
    async def broken(*args, **kwargs):
        raise RuntimeError("offline")

    result = await RetrievalPipeline(
        vector_search=good_vector, bm25_search=broken, reranker=None
    ).search("保修")

    assert result.answerable is True
    assert result.degraded is True
    assert result.degraded_reasons == ("bm25_unavailable",)


@pytest.mark.asyncio
async def test_both_failed_legs_are_retrieval_unavailable():
    async def broken(*args, **kwargs):
        raise RuntimeError("secret backend detail")

    result = await RetrievalPipeline(
        vector_search=broken, bm25_search=broken, reranker=None
    ).search("保修")

    assert result.answerable is False
    assert result.reason == "retrieval_unavailable"
    assert result.hits == ()
    assert result.context == ""
    assert result.citations == ()
    assert result.degraded_reasons == ("vector_unavailable", "bm25_unavailable")


@pytest.mark.asyncio
async def test_both_empty_legs_are_insufficient_evidence_not_unavailable():
    empty = AsyncMock(return_value={"hits": []})

    result = await RetrievalPipeline(vector_search=empty, bm25_search=empty, reranker=None).search("保修")

    assert result.reason == "insufficient_evidence"
    assert result.degraded is False


@pytest.mark.asyncio
async def test_metadata_filtering_happens_before_rrf_ranking():
    vector = AsyncMock(return_value={"hits": [
        raw_hit(1, product_id=8),
        raw_hit(2, product_id=7),
    ]})
    bm25 = AsyncMock(return_value={"hits": [raw_hit(2, product_id=7, score=9)]})

    result = await RetrievalPipeline(vector_search=vector, bm25_search=bm25, reranker=None).search(
        "退货", product_id=7
    )

    assert [hit.chunk_id for hit in result.hits] == [2]
    assert result.hits[0].rrf_score == pytest.approx(2 / 61)


@pytest.mark.asyncio
async def test_invalid_query_skips_both_adapters():
    vector = AsyncMock()
    bm25 = AsyncMock()

    result = await RetrievalPipeline(vector_search=vector, bm25_search=bm25, reranker=None).search(" \u0000 ")

    assert result.reason == "invalid_query"
    assert result.degraded is False
    vector.assert_not_awaited()
    bm25.assert_not_awaited()


@pytest.mark.asyncio
async def test_reranker_receives_rrf_top_ten_and_pipeline_selects_top_four():
    hits = [raw_hit(chunk_id, score=.9) for chunk_id in range(1, 13)]
    seen = {}

    class Reranker:
        async def rerank(self, query, candidates):
            seen["query"] = query
            seen["ids"] = [candidate.chunk_id for candidate in candidates]
            for index, candidate in enumerate(reversed(candidates), start=1):
                candidate.rerank_score = 1 - index / 100
            return list(reversed(candidates))

    result = await RetrievalPipeline(
        vector_search=AsyncMock(return_value={"hits": hits}),
        bm25_search=AsyncMock(return_value={"hits": []}),
        reranker=Reranker(),
    ).search(" 退货 ")

    assert seen == {"query": "退货", "ids": list(range(1, 11))}
    assert [hit.chunk_id for hit in result.hits] == [10, 9, 8, 7]


@pytest.mark.asyncio
async def test_reranker_failure_degrades_to_original_rrf_top_four():
    class BrokenReranker:
        async def rerank(self, query, candidates):
            raise RuntimeError("offline")

    hits = [raw_hit(chunk_id, score=.9) for chunk_id in range(1, 7)]
    result = await RetrievalPipeline(
        vector_search=AsyncMock(return_value={"hits": hits}),
        bm25_search=AsyncMock(return_value={"hits": []}),
        reranker=BrokenReranker(),
    ).search("退货")

    assert [hit.chunk_id for hit in result.hits] == [1, 2, 3, 4]
    assert result.degraded_reasons == ("reranker_unavailable",)


@pytest.mark.asyncio
async def test_missing_chunk_id_is_discarded_and_logged_without_content(caplog):
    secret_content = "NEVER_LOG_THIS_CANDIDATE"
    vector = AsyncMock(return_value={"hits": [raw_hit(None, content=secret_content), raw_hit(2)]})

    with caplog.at_level(logging.WARNING, logger="ai-service.retrieval"):
        result = await RetrievalPipeline(
            vector_search=vector,
            bm25_search=AsyncMock(return_value={"hits": []}),
            reranker=None,
        ).search("退货")

    assert [hit.chunk_id for hit in result.hits] == [2]
    assert "missing or invalid chunk_id" in caplog.text
    assert secret_content not in caplog.text


@pytest.mark.asyncio
async def test_backend_keyword_adapter_sends_only_query_and_top_k():
    client = BackendClient.__new__(BackendClient)
    client._post = AsyncMock(return_value={"hits": []})

    await client.kb_keyword_search("退货", doc_type="POLICY", product_id=7, top_k=20)

    client._post.assert_awaited_once_with("/internal/kb/search", {"query": "退货", "topK": 20})


@pytest.mark.asyncio
async def test_vector_adapter_requests_exact_top_k_and_returns_complete_metadata(monkeypatch):
    calls = []

    class Embeddings:
        async def aembed_query(self, query):
            return [0.1, 0.2]

    class Client:
        def search(self, **kwargs):
            calls.append(kwargs)
            return [[{"id": 3, "distance": .8, "entity": {
                "doc_id": 10,
                "product_id": 7,
                "doc_type": "POLICY",
                "content": "正文",
            }}]]

    store = VectorStore.__new__(VectorStore)
    store.embeddings = Embeddings()
    store.client = Client()
    monkeypatch.setattr("app.rag.vectorstore.backend_client.kb_current_chunks", AsyncMock(return_value={3: "条款"}))

    result = await store.search("退货", doc_type="OTHER", product_id=99, top_k=20)

    assert calls[0]["limit"] == 20
    assert calls[0]["filter"] == "doc_id >= 0"
    assert calls[0]["output_fields"] == ["content", "doc_id", "product_id", "doc_type"]
    assert result["hits"] == [{
        "chunk_id": 3,
        "doc_id": 10,
        "product_id": 7,
        "docType": "POLICY",
        "content": "正文",
        "source": "条款",
        "score": .8,
    }]


@pytest.mark.asyncio
async def test_cached_pipeline_degrades_when_vectorstore_initialization_fails(monkeypatch):
    from app.clients.backend_client import backend_client
    from app.rag import vectorstore

    def unavailable_vectorstore():
        raise RuntimeError("milvus initialization detail must stay internal")

    monkeypatch.setattr(vectorstore, "get_vectorstore", unavailable_vectorstore)
    monkeypatch.setattr(
        backend_client,
        "kb_keyword_search",
        AsyncMock(return_value={"hits": [raw_hit(9, score=100.0)]}),
    )
    retrieval.get_retrieval_pipeline.cache_clear()
    try:
        result = await retrieval.get_retrieval_pipeline().search("退货")
    finally:
        retrieval.get_retrieval_pipeline.cache_clear()

    assert result.answerable is True
    assert [hit.chunk_id for hit in result.hits] == [9]
    assert result.degraded is True
    assert result.degraded_reasons == ("vector_unavailable",)
