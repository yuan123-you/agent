import pytest

from app.rag import product_index


@pytest.mark.asyncio
async def test_hybrid_product_search_uses_second_stage_reranker(monkeypatch):
    class Corpus:
        products = {
            1: {"productId": 1, "name": "普通手机", "price": 999},
            2: {"productId": 2, "name": "目标游戏手机", "price": 1999},
        }
        def ready(self): return True
        def bm25_recall(self, *args): return [(1, 1.0), (2, 0.5)]

    class Index:
        corpus = Corpus()
        async def vector_recall(self, *args): return [(1, 0.8), (2, 0.7)]

    class Reranker:
        async def rerank(self, query, hits, top_n):
            return [hits[1]]

    monkeypatch.setattr(product_index, "get_product_corpus", lambda: Index.corpus)
    monkeypatch.setattr(product_index, "get_product_index", lambda: Index())
    monkeypatch.setattr(product_index, "get_reranker", lambda: Reranker(), raising=False)
    result = await product_index.hybrid_product_search("游戏手机", None, None, None, top_k=1)
    assert [p["productId"] for p in result["products"]] == [2]


@pytest.mark.asyncio
async def test_hybrid_search_keeps_bm25_results_when_vector_leg_fails(monkeypatch):
    class Corpus:
        products = {2: {"productId": 2, "name": "目标手机", "price": 1999}}
        def ready(self): return True
        def bm25_recall(self, *args): return [(2, 1.0)]

    class Index:
        async def vector_recall(self, *args):
            raise RuntimeError("milvus offline")

    class Reranker:
        async def rerank(self, query, hits, top_n): return hits[:top_n]

    monkeypatch.setattr(product_index, "get_product_corpus", lambda: Corpus(), raising=False)
    monkeypatch.setattr(product_index, "get_product_index", lambda: Index())
    monkeypatch.setattr(product_index, "get_reranker", lambda: Reranker(), raising=False)

    result = await product_index.hybrid_product_search("目标手机", None, None, None, top_k=1)

    assert [item["productId"] for item in result["products"]] == [2]


@pytest.mark.asyncio
async def test_product_sync_builds_keyword_corpus_before_embedding_failure(monkeypatch):
    from unittest.mock import AsyncMock
    from app.rag import ingest

    products = [{"productId": 2, "name": "目标手机", "category": "PHONE", "price": 1999}]

    class Corpus:
        def __init__(self): self.products = {}
        def rebuild(self, rows, texts): self.products = {row["productId"]: row for row in rows}

    class BrokenEmbeddings:
        async def aembed_documents(self, texts): raise RuntimeError("embedding offline")

    corpus = Corpus()
    monkeypatch.setattr(ingest.backend_client, "products_all", AsyncMock(return_value=products))
    monkeypatch.setattr(ingest, "get_product_corpus", lambda: corpus, raising=False)
    monkeypatch.setattr(ingest, "get_embeddings", lambda: BrokenEmbeddings())

    result = await ingest.sync_products()

    assert list(corpus.products) == [2]
    assert result["indexed"] == 1
    assert result["vectorIndexed"] == 0


def test_structured_recommendations_prefer_sales_signal_over_cheapest_accessory():
    corpus = product_index.ProductCorpus()
    products = [
        {"productId": 1, "name": "充电器", "category": "PHONE", "price": 99, "sales": 10},
        {"productId": 2, "name": "热门手机", "category": "PHONE", "price": 2999, "sales": 900},
    ]
    corpus.products = {item["productId"]: item for item in products}

    result = corpus.structured("PHONE", None, None, 2)

    assert [item["productId"] for item in result] == [2, 1]


@pytest.mark.asyncio
async def test_hybrid_search_returns_none_for_sql_fallback_when_all_legs_unavailable(monkeypatch):
    class Corpus:
        products = {2: {"productId": 2, "name": "目标手机", "price": 1999}}
        def ready(self): return True
        def bm25_recall(self, *args): return []

    class Index:
        async def vector_recall(self, *args): raise RuntimeError("milvus offline")

    monkeypatch.setattr(product_index, "get_product_corpus", lambda: Corpus())
    monkeypatch.setattr(product_index, "get_product_index", lambda: Index())

    assert await product_index.hybrid_product_search("未知词", None, None, None, 5) is None
