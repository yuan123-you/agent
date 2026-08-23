import json

import httpx
import pytest

from app.rag.reranker import OllamaReranker


@pytest.mark.asyncio
async def test_ollama_reranker_orders_candidates_by_relevance_score():
    scores = iter([0.18, 0.91, 0.52])

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "dengcao/Qwen3-Reranker-4B:Q4_K_M"
        assert payload["stream"] is False
        assert payload["format"]["properties"]["score"]["type"] == "number"
        return httpx.Response(200, json={"response": json.dumps({"score": next(scores)})})

    reranker = OllamaReranker(
        base_url="http://ollama:11434",
        model="dengcao/Qwen3-Reranker-4B:Q4_K_M",
        transport=httpx.MockTransport(handler),
    )
    hits = [
        {"chunk_id": 1, "content": "不相关内容"},
        {"chunk_id": 2, "content": "七天无理由退货"},
        {"chunk_id": 3, "content": "退款通常原路返回"},
    ]

    result = await reranker.rerank("退款规则", hits, top_n=2)

    assert [hit["chunk_id"] for hit in result] == [2, 3]
    assert [hit["rerank_score"] for hit in result] == [0.91, 0.52]


@pytest.mark.asyncio
async def test_ollama_reranker_returns_original_order_when_disabled():
    reranker = OllamaReranker(base_url="", model="")
    hits = [{"content": "a"}, {"content": "b"}]
    assert await reranker.rerank("query", hits, top_n=1) == hits[:1]

@pytest.mark.asyncio
async def test_ollama_reranker_retries_one_transient_server_error():
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500, json={"error": "temporary model load failure"})
        return httpx.Response(200, json={"response": json.dumps({"score": 0.87})})

    reranker = OllamaReranker(
        base_url="http://ollama:11434",
        model="dengcao/Qwen3-Reranker-4B:Q4_K_M",
        transport=httpx.MockTransport(handler),
    )

    result = await reranker.rerank(
        "大件配送", [{"chunk_id": 1, "content": "可以预约配送时间"}], top_n=1
    )

    assert attempts == 2
    assert result[0]["rerank_score"] == 0.87
