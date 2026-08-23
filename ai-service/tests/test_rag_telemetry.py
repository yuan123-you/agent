import json

import pytest

from app.observability import telemetry
from app.rag.retrieval import RetrievalPipeline


class FakeSpan:
    def __init__(self, name, kwargs):
        self.name = name
        self.kwargs = kwargs
        self.output = None

    def end(self, *, output=None):
        self.output = output


class FakeTrace:
    def __init__(self):
        self.spans = []

    def span(self, *, name, **kwargs):
        span = FakeSpan(name, kwargs)
        self.spans.append(span)
        return span

    observation = span


@pytest.mark.asyncio
async def test_hybrid_retrieval_span_contains_safe_decision_metadata_only():
    trace = FakeTrace()
    token = telemetry._trace_ctx.set({"trace": trace, "client": None})

    async def vector(query, top_k):
        return {"hits": [{
            "chunk_id": 1,
            "doc_id": 10,
            "product_id": -1,
            "docType": "POLICY",
            "content": "SECRET_SOURCE_TEXT",
            "source": "退换货条款",
            "score": .9,
            "headers": {"Authorization": "Bearer SECRET_KEY"},
        }]}

    async def bm25(query, top_k):
        raise RuntimeError("Authorization: Bearer SECRET_KEY")

    try:
        result = await RetrievalPipeline(vector_search=vector, bm25_search=bm25, reranker=None).search("  退货  ")
    finally:
        telemetry._trace_ctx.reset(token)

    assert result.answerable is True
    span = trace.spans[0]
    assert span.name == "rag::hybrid_retrieval"
    assert span.output == {
        "normalized_query": {"length": 2, "word_count": 1},
        "vector_count": 1,
        "bm25_count": 0,
        "vector_filtered_count": 1,
        "bm25_filtered_count": 0,
        "rrf_count": 1,
        "rerank_count": 0,
        "top1": result.hits[0].evidence_score,
        "margin": None,
        "answerable": True,
        "decision_reason": "high_confidence",
        "degradation_reasons": ["bm25_unavailable"],
    }
    serialized = json.dumps({"input": span.kwargs, "output": span.output})
    assert "SECRET_SOURCE_TEXT" not in serialized
    assert "Authorization" not in serialized
    assert "SECRET_KEY" not in serialized


def test_span_context_sanitizes_escaping_exception_output():
    trace = FakeTrace()
    token = telemetry._trace_ctx.set({"trace": trace, "client": None})
    sentinel = "SENTINEL_API_KEY_DO_NOT_RECORD"

    try:
        with pytest.raises(RuntimeError, match=sentinel):
            with telemetry.span_ctx("rag::failing"):
                raise RuntimeError(f"request headers and URL contained {sentinel}")
    finally:
        telemetry._trace_ctx.reset(token)

    assert trace.spans[0].output == {"error": "span_failed"}
    serialized = json.dumps(trace.spans[0].output)
    assert "request headers" not in serialized
    assert sentinel not in serialized


def test_tool_span_sanitizes_escaping_exception_output():
    trace = FakeTrace()
    token = telemetry._trace_ctx.set({"trace": trace, "client": None})
    sentinel = "SENTINEL_TOOL_SECRET_DO_NOT_RECORD"

    try:
        with pytest.raises(RuntimeError, match=sentinel):
            with telemetry.tool_span("failing"):
                raise RuntimeError(f"tool response contained {sentinel}")
    finally:
        telemetry._trace_ctx.reset(token)

    assert trace.spans[0].output == {"error": "span_failed"}
    assert sentinel not in json.dumps(trace.spans[0].output)


@pytest.mark.asyncio
async def test_observe_retrieval_records_only_safe_hit_aggregates(monkeypatch):
    trace = FakeTrace()
    token = telemetry._trace_ctx.set({"trace": trace, "client": None})
    monkeypatch.setattr(telemetry, "tracing_enabled", lambda: True)
    content_sentinel = "SENTINEL_CANDIDATE_CONTENT"
    title_sentinel = "SENTINEL_SOURCE_TITLE"

    @telemetry.observe_retrieval("rag::legacy_search")
    async def search(query):
        return {
            "total": 1,
            "hits": [{"content": content_sentinel, "source": title_sentinel}],
        }

    try:
        result = await search("safe query")
    finally:
        telemetry._trace_ctx.reset(token)

    assert result["hits"][0]["content"] == content_sentinel
    assert trace.spans[0].output == {"total": 1, "hit_count": 1, "metric": "hits"}
    serialized = json.dumps(trace.spans[0].output)
    assert content_sentinel not in serialized
    assert title_sentinel not in serialized


@pytest.mark.asyncio
async def test_observe_retrieval_sanitizes_escaping_exception_output(monkeypatch):
    trace = FakeTrace()
    token = telemetry._trace_ctx.set({"trace": trace, "client": None})
    monkeypatch.setattr(telemetry, "tracing_enabled", lambda: True)
    sentinel = "SENTINEL_RETRIEVAL_SECRET"

    @telemetry.observe_retrieval("rag::legacy_search")
    async def search(query):
        raise RuntimeError(f"retrieval response contained {sentinel}")

    try:
        with pytest.raises(RuntimeError, match=sentinel):
            await search("safe query")
    finally:
        telemetry._trace_ctx.reset(token)

    assert trace.spans[0].output == {"error": "span_failed"}
    assert sentinel not in json.dumps(trace.spans[0].output)
