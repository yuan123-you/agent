import pytest

from app.rag import product_index


class Corpus:
    products = {
        1: {"productId": 1, "name": "普通手机", "price": 999},
        2: {"productId": 2, "name": "目标游戏手机", "price": 1999},
    }

    def ready(self):
        return True

    def bm25_recall(self, *args):
        return [(1, 1.0), (2, 0.5)]


class Index:
    corpus = Corpus()

    async def vector_recall(self, *args):
        return [(1, 0.8), (2, 0.7)]


@pytest.mark.asyncio
async def test_hybrid_product_search_uses_legacy_second_stage_reranker(monkeypatch):
    class Reranker:
        async def rerank(self, query, hits, top_n):
            return [hits[1]]

    monkeypatch.setattr(product_index, "get_product_index", lambda: Index())
    monkeypatch.setattr(product_index, "_get_product_reranker", lambda: Reranker(), raising=False)

    result = await product_index.hybrid_product_search("游戏手机", None, None, None, top_k=1)

    assert [p["productId"] for p in result["products"]] == [2]


@pytest.mark.asyncio
async def test_t10_reranker_is_never_given_product_dicts_when_legacy_reranker_disabled(monkeypatch):
    class StrictQwenReranker:
        async def rerank(self, query, candidates):
            raise AssertionError("product dicts reached the typed T10 reranker")

    monkeypatch.setattr(product_index, "get_product_index", lambda: Index())
    monkeypatch.setattr(product_index.settings, "rag_reranker_enabled", True)
    monkeypatch.setattr(product_index.settings, "reranker_enabled", False)
    monkeypatch.setattr(product_index, "get_reranker", lambda: StrictQwenReranker(), raising=False)

    result = await product_index.hybrid_product_search("手机", None, None, None, top_k=1)

    assert [p["productId"] for p in result["products"]] == [1]


@pytest.mark.asyncio
async def test_product_search_skips_reranking_when_both_rerankers_are_disabled(monkeypatch):
    monkeypatch.setattr(product_index, "get_product_index", lambda: Index())
    monkeypatch.setattr(product_index.settings, "rag_reranker_enabled", False)
    monkeypatch.setattr(product_index.settings, "reranker_enabled", False)

    result = await product_index.hybrid_product_search("手机", None, None, None, top_k=1)

    assert [p["productId"] for p in result["products"]] == [1]


@pytest.mark.asyncio
async def test_product_search_uses_legacy_contract_when_both_rerankers_are_enabled(monkeypatch):
    seen = {}

    class LegacyReranker:
        def __init__(self, **kwargs):
            seen["configured"] = True

        async def rerank(self, query, hits, top_n):
            seen["dicts"] = all(isinstance(hit, dict) for hit in hits)
            return [hits[1]]

    monkeypatch.setattr(product_index, "get_product_index", lambda: Index())
    monkeypatch.setattr(product_index.settings, "rag_reranker_enabled", True)
    monkeypatch.setattr(product_index.settings, "reranker_enabled", True)
    monkeypatch.setattr(product_index, "OllamaReranker", LegacyReranker, raising=False)

    result = await product_index.hybrid_product_search("游戏手机", None, None, None, top_k=1)

    assert seen == {"configured": True, "dicts": True}
    assert [p["productId"] for p in result["products"]] == [2]
