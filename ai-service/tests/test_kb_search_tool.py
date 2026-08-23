import json

import pytest

from app.rag import retrieval
from app.rag.retrieval import Citation, RetrievalCandidate, RetrievalResult
from app.tools.tools import get_tool_ctx, kb_search, set_tool_ctx


class FakePipeline:
    def __init__(self, result: RetrievalResult):
        self.result = result
        self.calls = []

    async def search(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.result


def answerable_result(*, degraded: bool = False) -> RetrievalResult:
    hit = RetrievalCandidate(
        1, 10, -1, "POLICY", "七天退货", "知识库文档#10", vector_score=0.9
    )
    return RetrievalResult(
        True,
        "answerable",
        (hit,),
        '<source id="S1" chunk_id="1" title="退换货条款">七天退货</source>',
        (Citation("S1", 1, "退换货条款"),),
        degraded,
        ("bm25_unavailable",) if degraded else (),
    )


@pytest.mark.asyncio
async def test_kb_search_returns_context_and_records_allowed_ids(monkeypatch):
    pipeline = FakePipeline(answerable_result())
    monkeypatch.setattr(retrieval, "get_retrieval_pipeline", lambda: pipeline)
    set_tool_ctx({})

    result = await kb_search.ainvoke(
        {"query": "七天退货", "doc_type": "POLICY", "product_id": -1, "top_k": 2}
    )

    assert result["answerable"] is True
    assert result["context"].startswith('<source id="S1"')
    assert result["citations"] == [
        {"id": "S1", "chunk_id": 1, "title": "退换货条款"}
    ]
    assert result["hits"][0]["chunk_id"] == 1
    assert result["hits"][0]["source"] == "退换货条款"
    assert "知识库文档#10" not in str(result)
    json.dumps(result, ensure_ascii=False)
    assert set(result) == {
        "answerable",
        "reason",
        "context",
        "citations",
        "hits",
        "degraded",
        "degraded_reasons",
    }
    assert pipeline.calls == [(("七天退货",), {"doc_type": "POLICY", "product_id": -1})]
    assert get_tool_ctx() == {
        "rag_used": True,
        "rag_answerable": True,
        "rag_reason": "answerable",
        "rag_allowed_citations": {"S1": result["citations"][0]},
        "degraded": False,
    }


@pytest.mark.asyncio
async def test_kb_search_records_insufficient_evidence_without_allowed_ids(monkeypatch):
    result_value = RetrievalResult(False, "insufficient_evidence", (), "", (), False, ())
    monkeypatch.setattr(
        retrieval, "get_retrieval_pipeline", lambda: FakePipeline(result_value)
    )
    set_tool_ctx({})

    result = await kb_search.ainvoke({"query": "不存在的政策"})

    assert result["reason"] == "insufficient_evidence"
    assert result["answerable"] is False
    assert result["context"] == ""
    assert result["citations"] == []
    assert get_tool_ctx()["rag_allowed_citations"] == {}
    assert get_tool_ctx()["degraded"] is False


@pytest.mark.asyncio
async def test_kb_search_marks_retrieval_unavailable_as_globally_degraded(monkeypatch):
    result_value = RetrievalResult(False, "retrieval_unavailable", (), "", (), False, ())
    monkeypatch.setattr(
        retrieval, "get_retrieval_pipeline", lambda: FakePipeline(result_value)
    )
    set_tool_ctx({})

    result = await kb_search.ainvoke({"query": "退货政策"})

    assert result["reason"] == "retrieval_unavailable"
    assert result["degraded"] is False
    assert get_tool_ctx()["rag_reason"] == "retrieval_unavailable"
    assert get_tool_ctx()["rag_allowed_citations"] == {}
    assert get_tool_ctx()["degraded"] is True


@pytest.mark.asyncio
async def test_kb_search_preserves_answerable_context_when_pipeline_is_degraded(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "get_retrieval_pipeline",
        lambda: FakePipeline(answerable_result(degraded=True)),
    )
    set_tool_ctx({"degraded": False})

    result = await kb_search.ainvoke({"query": "七天退货"})

    assert result["answerable"] is True
    assert result["context"].startswith('<source id="S1"')
    assert result["degraded"] is True
    assert result["degraded_reasons"] == ["bm25_unavailable"]
    assert get_tool_ctx()["rag_allowed_citations"]["S1"]["title"] == "退换货条款"
    assert get_tool_ctx()["degraded"] is True


def test_shop_prompt_requires_source_ids_without_title_citations():
    from app.agent.prompts import SHOP_SYSTEM_PROMPT

    assert '只能依据 <source id="Sx">...</source> 中的内容回答' in SHOP_SYSTEM_PROMPT
    assert '每个知识库事实句末必须引用对应的 [Sx]' in SHOP_SYSTEM_PROMPT
    assert 'answerable=false 时必须说明当前证据不足' in SHOP_SYSTEM_PROMPT
    assert '（来源：《退换货条款》）' not in SHOP_SYSTEM_PROMPT
