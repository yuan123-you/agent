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
