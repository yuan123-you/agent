"""Offline model HTTP contract tests; every request uses MockTransport."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from app.clients import llm
from app.clients.ollama import OllamaEmbeddings
from app.rag.reranker import OllamaReranker, QwenHttpReranker
from app.rag.retrieval import RetrievalCandidate


@pytest.fixture(autouse=True)
def forbid_real_http(monkeypatch):
    async def forbidden_async(*args, **kwargs):
        pytest.fail("model resilience tests must not make network requests")

    def forbidden_sync(*args, **kwargs):
        pytest.fail("model resilience tests must not make network requests")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden_async)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden_sync)


@pytest.fixture(autouse=True)
async def close_test_model_clients():
    yield
    await llm.close_model_clients()


def mock_http(monkeypatch, handler):
    original = httpx.AsyncClient
    transport = httpx.MockTransport(handler)

    def client(**kwargs):
        if kwargs.get("transport") is None:
            kwargs["transport"] = transport
        return original(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client)
    return transport


def model_operation(kind, *, timeout=1.0, count=1):
    if kind == "ollama":
        model = OllamaEmbeddings("http://model", "existing", 2, timeout=timeout, max_batch_size=1)
        return lambda: model.aembed_documents(["document"] * count)
    if kind == "maas":
        model = llm.MaaSEmbeddings("http://model", "test", "existing")
        return lambda: model.aembed_documents(["document"] * count)
    if kind == "qwen":
        config = SimpleNamespace(
            rag_reranker_base_url="http://model", rag_reranker_endpoint="/rerank",
            rag_reranker_model="existing", rag_reranker_api_key="test",
            rag_reranker_timeout_s=timeout, rag_reranker_batch_size=1,
        )
        model = QwenHttpReranker(config)
        candidates = [RetrievalCandidate(i + 1, 1, None, "POLICY", "document", "source") for i in range(count)]
        return lambda: model.rerank("query", candidates)
    model = OllamaReranker("http://model", "existing", timeout=timeout)
    return lambda: model.rerank("query", [{"content": "document"}] * count, count)


def success(kind, request=None):
    count = len(json.loads(request.content)["input"]) if kind == "maas" and request else 1
    payload = {
        "ollama": {"embeddings": [[1.0, 2.0]]},
        "maas": {"data": [{"index": i, "embedding": [1.0, 2.0]} for i in range(count)]},
        "qwen": {"results": [{"index": 0, "relevance_score": 0.7}]},
        "legacy": {"response": '{"score": 0.7}'},
    }[kind]
    return httpx.Response(200, json=payload)


@pytest.mark.parametrize("kind", ["ollama", "maas", "qwen", "legacy"])
async def test_transient_model_http_is_retried(kind, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503) if len(calls) == 1 else success(kind, request)

    mock_http(monkeypatch, handler)
    result = await model_operation(kind, timeout=2.0)()
    assert len(calls) == 2
    assert len(result) == 1
    if kind in ("ollama", "maas"):
        assert result == [[1.0, 2.0]]
    elif kind == "qwen":
        assert result[0].rerank_score == 0.7
    else:
        assert result[0]["rerank_score"] == 0.7


@pytest.mark.parametrize("kind", ["ollama", "maas", "qwen", "legacy"])
async def test_malformed_model_json_is_never_retried(kind, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=b"not-json")

    mock_http(monkeypatch, handler)
    if kind == "legacy":
        assert await model_operation(kind)() == [{"content": "document"}]
    else:
        with pytest.raises(ValueError):
            await model_operation(kind)()
    assert len(calls) == 1


async def test_embedding_dimension_failure_is_not_retried(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"embeddings": [[1.0]]})

    mock_http(monkeypatch, handler)
    with pytest.raises(ValueError, match="expected dimension 2"):
        await model_operation("ollama")()
    assert len(calls) == 1


async def test_reranker_invalid_score_contract_is_not_retried(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"results": [{"index": 0, "relevance_score": 2.0}]})

    mock_http(monkeypatch, handler)
    with pytest.raises(ValueError, match="outside"):
        await model_operation("qwen")()
    assert len(calls) == 1


@pytest.mark.parametrize("kind", ["ollama", "maas", "qwen", "legacy"])
async def test_model_http_callback_cancellation_is_not_retried_or_degraded(kind, monkeypatch):
    calls = []

    async def handler(request):
        calls.append(request)
        raise asyncio.CancelledError()

    mock_http(monkeypatch, handler)
    with pytest.raises(asyncio.CancelledError):
        await model_operation(kind)()
    assert len(calls) == 1


@pytest.mark.parametrize("kind", ["ollama", "maas", "qwen", "legacy"])
async def test_batch_retries_share_parent_permit_budget(kind, monkeypatch):
    from app.resilience import RetryBudgetExhausted, budget_scope

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503) if len(calls) % 2 else success(kind, request)

    mock_http(monkeypatch, handler)
    with budget_scope(5.0, retry_tokens=1):
        if kind == "legacy":
            assert await model_operation(kind, timeout=5.0, count=2)() == [{"content": "document"}] * 2
        else:
            with pytest.raises(RetryBudgetExhausted):
                await model_operation(kind, timeout=5.0, count=5 if kind == "maas" else 2)()
    assert len(calls) == 3, "only the first failed batch may spend a retry permit"


@pytest.mark.parametrize("kind", ["ollama", "maas", "qwen", "legacy"])
async def test_all_batches_share_one_local_deadline(kind, monkeypatch):
    from app import resilience

    clock = [100.0]
    budgets = []
    timeouts = []

    def handler(request):
        budget = resilience.current_budget()
        budgets.append(budget.remaining() if budget else None)
        timeouts.append(request.extensions["timeout"]["read"])
        clock[0] += 0.25
        return success(kind, request)

    monkeypatch.setattr(resilience, "monotonic", lambda: clock[0])
    mock_http(monkeypatch, handler)
    await model_operation(kind, timeout=1.0, count=5 if kind == "maas" else 2)()
    limit = 30.0 if kind == "maas" else 1.0
    assert budgets == [limit, limit - 0.25]
    assert timeouts == [limit, limit - 0.25], "batch two must not restart the total timeout"


@pytest.mark.parametrize("kind", ["ollama", "maas", "qwen", "legacy"])
async def test_model_attempt_is_clipped_to_shared_deadline(kind, monkeypatch):
    from app.resilience import budget_scope

    calls = []

    async def handler(request):
        calls.append(request)
        assert 0 < request.extensions["timeout"]["read"] <= 0.03
        await asyncio.sleep(0.1)
        return success(kind, request)

    mock_http(monkeypatch, handler)
    with budget_scope(0.03):
        if kind == "legacy":
            assert await model_operation(kind)() == [{"content": "document"}]
        else:
            with pytest.raises(TimeoutError):
                await model_operation(kind)()
    assert len(calls) == 1


@pytest.mark.parametrize("factory", [llm.get_chat_llm, llm.get_intent_llm])
async def test_chat_and_intent_disable_sdk_hidden_retries(factory):
    model = factory()
    assert model.max_retries == 0
    assert model.root_async_client.max_retries == 0


async def test_openai_embeddings_disable_sdk_hidden_retries():
    model = llm._make_embeddings("http://model/v1", "test", "existing", provider="openai")
    assert model.max_retries == 0
    assert model.async_client._client.max_retries == 0


async def test_sync_embeddings_bridge_the_bounded_async_transport(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503) if len(calls) == 1 else success("ollama", request)

    transport = mock_http(monkeypatch, handler)
    model = OllamaEmbeddings("http://model", "existing", 2, transport=transport)
    assert await asyncio.to_thread(model.embed_query, "query") == [1.0, 2.0]
    assert len(calls) == 2


async def test_warmup_retries_share_the_whole_job_budget(monkeypatch):
    from app.resilience import RetryBudgetExhausted, budget_scope, current_budget

    calls = []
    budgets = []

    def handler(request):
        calls.append(request)
        budgets.append(current_budget().remaining() if current_budget() else None)
        return httpx.Response(503) if len(calls) % 2 else httpx.Response(200, json={"done": True})

    mock_http(monkeypatch, handler)
    monkeypatch.setattr(llm, "settings", SimpleNamespace(
        llm_warmup_enabled=True, llm_api_base="http://model/v1",
        llm_intent_model="existing", llm_chat_model="existing", llm_keep_alive_s=-1,
        llm_warmup_timeout_s=2.0,
    ))
    with budget_scope(2.0, retry_tokens=1):
        with pytest.raises(RetryBudgetExhausted):
            await llm.warm_local_models()
    assert len(calls) == 3
    assert budgets[0] is not None and 0 < budgets[-1] <= budgets[0]


async def test_sdk_transport_is_sole_retry_owner_and_clients_are_reused_and_closed(monkeypatch):
    from app.resilience import ResilientAsyncTransport, budget_scope

    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503, json={"error": {"message": "busy"}})
        return httpx.Response(200, json={
            "id": "test", "object": "chat.completion", "created": 0, "model": "existing",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
        })

    await llm.close_model_clients()
    monkeypatch.setattr(llm, "ResilientAsyncTransport", lambda *a, **kw: ResilientAsyncTransport(
        *a, transport=httpx.MockTransport(handler), **kw,
    ))
    try:
        model = llm.get_chat_llm(streaming=False)
        other = llm.get_chat_llm(streaming=False)
        assert model.http_async_client is other.http_async_client
        with budget_scope(3.0, retry_tokens=1):
            assert (await model.ainvoke("test")).content == "ok"
        assert len(calls) == 2
        assert model.max_retries == 0
    finally:
        await llm.close_model_clients()
    assert model.http_async_client.is_closed


async def test_sdk_partial_stream_is_never_replayed(monkeypatch):
    from app.resilience import ResilientAsyncTransport, budget_scope

    calls = []

    class PartialStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"id":"test","object":"chat.completion.chunk","created":0,"model":"existing","choices":[{"index":0,"delta":{"role":"assistant","content":"partial"},"finish_reason":null}]}\n\n'
            raise httpx.ReadError("stream disconnected")

    def handler(request):
        calls.append(request)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=PartialStream())

    await llm.close_model_clients()
    monkeypatch.setattr(llm, "ResilientAsyncTransport", lambda *a, **kw: ResilientAsyncTransport(
        *a, transport=httpx.MockTransport(handler), **kw,
    ))
    chunks = []
    try:
        with budget_scope(3.0):
            with pytest.raises(Exception):
                async for chunk in llm.get_chat_llm().astream("test"):
                    chunks.append(chunk.content)
        assert "partial" in chunks
        assert len(calls) == 1
    finally:
        await llm.close_model_clients()


@pytest.mark.parametrize("kind", ["ollama", "maas", "qwen", "legacy"])
async def test_model_full_jitter_backoff_spends_the_shared_deadline(kind, monkeypatch):
    from app import resilience

    clock = [100.0]
    waits = []
    caps = []
    timeouts = []

    def jitter(low, high):
        caps.append((low, high))
        return high / 2

    async def sleep(delay):
        waits.append(delay)
        clock[0] += delay

    def handler(request):
        timeouts.append(request.extensions["timeout"]["read"])
        return httpx.Response(503) if len(timeouts) < 3 else success(kind, request)

    monkeypatch.setattr(resilience, "monotonic", lambda: clock[0])
    monkeypatch.setattr(resilience.random, "uniform", jitter)
    monkeypatch.setattr(resilience, "_sleep", sleep)
    mock_http(monkeypatch, handler)
    with resilience.budget_scope(0.5, retry_tokens=2):
        result = await model_operation(kind, timeout=2.0)()
    assert len(result) == 1
    assert caps == [(0, 0.25), (0, 0.5)]
    assert waits == [0.125, 0.25]
    assert timeouts == [0.5, 0.375, 0.125]


@pytest.mark.parametrize("kind", ["ollama", "maas", "qwen", "legacy"])
async def test_model_retry_after_that_cannot_fit_is_not_retried(kind, monkeypatch):
    from app.resilience import budget_scope

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "10"})

    mock_http(monkeypatch, handler)
    with budget_scope(1.0):
        if kind == "legacy":
            assert await model_operation(kind)() == [{"content": "document"}]
        else:
            with pytest.raises(httpx.HTTPStatusError):
                await model_operation(kind)()
    assert len(calls) == 1


async def test_legacy_malformed_score_preserves_fused_order_without_retry(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"response": "no relevance score"})

    mock_http(monkeypatch, handler)
    assert await model_operation("legacy")() == [{"content": "document"}]
    assert len(calls) == 1


async def test_maas_dimension_validation_degrades_without_http_retry(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"data": [{"embedding": [1.0]}]})

    mock_http(monkeypatch, handler)
    model = llm.FallbackEmbeddings([("existing", llm.MaaSEmbeddings("http://model", "test", "existing"))], expected_dim=2)
    with pytest.raises(llm.EmbeddingFallbackError, match="expected dimension 2"):
        await model.aembed_query("query")
    assert len(calls) == 1

@pytest.mark.parametrize("kind", ["ollama", "maas", "qwen", "legacy"])
@pytest.mark.parametrize("status", [401, 501])
async def test_permanent_model_http_failure_is_not_retried(kind, status, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status)

    mock_http(monkeypatch, handler)
    if kind == "legacy":
        assert await model_operation(kind)() == [{"content": "document"}]
    else:
        with pytest.raises(httpx.HTTPStatusError):
            await model_operation(kind)()
    assert len(calls) == 1


@pytest.mark.parametrize("kind", ["ollama", "maas", "qwen", "legacy"])
async def test_model_transient_failure_stops_at_three_http_attempts(kind, monkeypatch):
    from app import resilience

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503)

    monkeypatch.setattr(resilience.random, "uniform", lambda low, high: 0)
    mock_http(monkeypatch, handler)
    if kind == "legacy":
        assert await model_operation(kind)() == [{"content": "document"}]
    else:
        with pytest.raises(httpx.HTTPStatusError):
            await model_operation(kind)()
    assert len(calls) == 3


async def test_parallel_embedding_calls_cannot_multiply_parent_retry_permits(monkeypatch):
    from app.resilience import RetryBudgetExhausted, budget_scope

    attempts = {"a": 0, "b": 0}

    def handler(request):
        text = json.loads(request.content)["input"][0]
        attempts[text] += 1
        return httpx.Response(503) if attempts[text] == 1 else success("ollama", request)

    transport = mock_http(monkeypatch, handler)
    model = OllamaEmbeddings("http://model", "existing", 2, transport=transport)
    with budget_scope(3.0, retry_tokens=1):
        results = await asyncio.gather(model.aembed_query("a"), model.aembed_query("b"), return_exceptions=True)
    assert sum(attempts.values()) == 3
    assert sum(result == [1.0, 2.0] for result in results) == 1
    assert sum(isinstance(result, RetryBudgetExhausted) for result in results) == 1


@pytest.mark.parametrize("factory", [llm.get_chat_llm, llm.get_intent_llm])
async def test_sdk_malformed_json_is_not_retried(factory, monkeypatch):
    from app.resilience import ResilientAsyncTransport

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, headers={"content-type": "application/json"}, content=b"not-json")

    await llm.close_model_clients()
    monkeypatch.setattr(llm, "ResilientAsyncTransport", lambda *a, **kw: ResilientAsyncTransport(
        *a, transport=httpx.MockTransport(handler), **kw,
    ))
    try:
        model = factory(streaming=False) if factory is llm.get_chat_llm else factory()
        with pytest.raises(ValueError):
            await model.ainvoke("query")
        assert len(calls) == 1
    finally:
        await llm.close_model_clients()


async def test_openai_embedding_async_transport_retries_with_sdk_retries_off(monkeypatch):
    from app.resilience import ResilientAsyncTransport, budget_scope

    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503, json={"error": {"message": "busy"}})
        return httpx.Response(200, json={
            "object": "list", "model": "existing",
            "data": [{"object": "embedding", "index": 0, "embedding": [1.0, 2.0]}],
            "usage": {"prompt_tokens": 1, "total_tokens": 1},
        })

    await llm.close_model_clients()
    monkeypatch.setattr(llm, "ResilientAsyncTransport", lambda *a, **kw: ResilientAsyncTransport(
        *a, transport=httpx.MockTransport(handler), **kw,
    ))
    try:
        model = llm._make_embeddings("http://model/v1", "test", "existing", provider="openai")
        # Tokenizer downloads are unrelated to the HTTP boundary and forbidden here.
        model.check_embedding_ctx_length = False
        with budget_scope(3.0, retry_tokens=1):
            assert await model.aembed_query("query") == [1.0, 2.0]
        assert model.max_retries == 0
        assert len(calls) == 2
    finally:
        await llm.close_model_clients()
