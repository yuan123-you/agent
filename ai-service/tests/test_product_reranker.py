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

    monkeypatch.setattr(product_index, "get_product_index", lambda: Index())
    monkeypatch.setattr(product_index, "get_reranker", lambda: Reranker(), raising=False)
    result = await product_index.hybrid_product_search("游戏手机", None, None, None, top_k=1)
    assert [p["productId"] for p in result["products"]] == [2]
