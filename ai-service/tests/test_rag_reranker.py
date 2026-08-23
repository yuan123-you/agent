from types import SimpleNamespace

import httpx
import pytest

from app.rag.retrieval import RetrievalCandidate
from app.rag import reranker


def candidate(chunk_id: int) -> RetrievalCandidate:
    return RetrievalCandidate(chunk_id, 10, -1, "POLICY", f"正文{chunk_id}", "条款")


def reranker_settings(**overrides):
    values = {
        "rag_reranker_enabled": True,
        "rag_reranker_model": "Qwen/Qwen3-Reranker-4B",
        "rag_reranker_base_url": "http://reranker.example/",
        "rag_reranker_endpoint": "/v1/rerank",
        "rag_reranker_api_key": "test-secret",
        "rag_reranker_timeout_s": 7.5,
        "rag_reranker_batch_size": 10,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


@pytest.mark.asyncio
async def test_qwen_request_and_sort(monkeypatch):
    seen = {}

    async def fake_post(self, url, **kwargs):
        seen.update(url=url, **kwargs)
        return FakeResponse({"results": [
            {"index": 1, "relevance_score": 0.91},
            {"index": 0, "relevance_score": 0.32},
        ]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    ranked = await reranker.QwenHttpReranker(reranker_settings()).rerank(
        "退货", [candidate(10), candidate(20)]
    )

    assert seen["url"] == "http://reranker.example/v1/rerank"
    assert seen["json"] == {
        "model": "Qwen/Qwen3-Reranker-4B",
        "query": "退货",
        "documents": ["正文10", "正文20"],
        "top_n": 2,
    }
    assert seen["headers"] == {"Authorization": "Bearer test-secret"}
    assert seen["timeout"] == 7.5
    assert [item.chunk_id for item in ranked] == [20, 10]
    assert [item.rerank_score for item in ranked] == [0.91, 0.32]
    assert [item.evidence_score for item in ranked] == [0.91, 0.32]


@pytest.mark.asyncio
@pytest.mark.parametrize("results", [
    [{"index": 0, "relevance_score": 0.2}, {"index": 0, "relevance_score": 0.4}],
    [{"index": 0, "relevance_score": 0.2}],
    [{"index": 0, "relevance_score": 0.2}, {"index": 2, "relevance_score": 0.4}],
    [{"index": 0, "relevance_score": -0.1}, {"index": 1, "relevance_score": 0.4}],
    [{"index": 0, "relevance_score": 0.2}, {"index": 1, "relevance_score": 1.1}],
])
async def test_qwen_rejects_invalid_result_contract(monkeypatch, results):
    async def fake_post(self, url, **kwargs):
        return FakeResponse({"results": results})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(ValueError):
        await reranker.QwenHttpReranker(reranker_settings()).rerank("退货", [candidate(10), candidate(20)])


@pytest.mark.asyncio
async def test_qwen_propagates_http_failure(monkeypatch):
    async def fake_post(self, url, **kwargs):
        raise httpx.ConnectError("unavailable")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(httpx.ConnectError):
        await reranker.QwenHttpReranker(reranker_settings()).rerank("退货", [candidate(10)])


@pytest.mark.asyncio
async def test_qwen_batches_without_losing_candidate_identity(monkeypatch):
    requests = []

    async def fake_post(self, url, **kwargs):
        requests.append(kwargs["json"])
        return FakeResponse({"results": [
            {"index": index, "relevance_score": score}
            for index, score in enumerate([0.5, 0.5][:len(kwargs["json"]["documents"])])
        ]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    candidates = [candidate(10), candidate(20), candidate(30)]
    ranked = await reranker.QwenHttpReranker(reranker_settings(rag_reranker_batch_size=2)).rerank(
        "退货", candidates
    )

    assert [request["documents"] for request in requests] == [["正文10", "正文20"], ["正文30"]]
    assert ranked == candidates
    assert all(item.rerank_score == 0.5 and item.evidence_score == 0.5 for item in ranked)


def test_get_reranker_returns_none_when_http_reranker_is_disabled(monkeypatch):
    monkeypatch.setattr(reranker.settings, "rag_reranker_enabled", False)
    reranker.get_reranker.cache_clear()
    try:
        assert reranker.get_reranker() is None
    finally:
        reranker.get_reranker.cache_clear()


@pytest.mark.asyncio
async def test_qwen_omits_authorization_header_without_api_key(monkeypatch):
    seen = {}

    async def fake_post(self, url, **kwargs):
        seen.update(kwargs)
        return FakeResponse({"results": [{"index": 0, "relevance_score": 0.5}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    await reranker.QwenHttpReranker(reranker_settings(rag_reranker_api_key="")).rerank("退货", [candidate(10)])

    assert "headers" not in seen


def test_get_reranker_keeps_enabled_ollama_client_available(monkeypatch):
    monkeypatch.setattr(reranker.settings, "rag_reranker_enabled", False)
    monkeypatch.setattr(reranker.settings, "reranker_enabled", True)
    reranker.get_reranker.cache_clear()
    try:
        assert isinstance(reranker.get_reranker(), reranker.OllamaReranker)
    finally:
        reranker.get_reranker.cache_clear()
