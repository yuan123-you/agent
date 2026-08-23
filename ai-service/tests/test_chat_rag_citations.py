import json

import pytest
from langchain_core.messages import AIMessageChunk

from app.api import chat


class _Request:
    async def is_disconnected(self):
        return False


class _Graph:
    def __init__(
        self,
        context,
        *,
        answer_parts,
        rag=True,
        answerable=True,
        reason="answerable",
    ):
        self.context = context
        self.answer_parts = answer_parts
        self.rag = rag
        self.answerable = answerable
        self.reason = reason
        self.completed = False
        self.calls = 0

    async def astream_events(self, *_args, **_kwargs):
        self.calls += 1
        if self.rag:
            self.context.update({
                "rag_used": True,
                "rag_answerable": self.answerable,
                "rag_reason": self.reason,
                "rag_allowed_citations": {
                    "S1": {"id": "S1", "chunk_id": 7, "title": "退换货条款"}
                } if self.answerable else {},
            })
            yield {
                "event": "on_tool_end",
                "run_id": "kb-1",
                "name": "kb_search",
                "data": {"output": {"answerable": True}},
            }
        for part in self.answer_parts:
            yield {
                "event": "on_chat_model_stream",
                "metadata": {"langgraph_node": "agent"},
                "data": {"chunk": AIMessageChunk(content=part)},
            }
        self.completed = True
        yield {
            "event": "on_chain_end",
            "name": "LangGraph",
            "data": {"output": {}},
        }


def _decode(raw):
    if isinstance(raw, bytes):
        raw = raw.decode()
    lines = raw.strip().splitlines()
    return lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: "))


def _request():
    return chat.ChatRequest(conversation_id=1, user_id=2, message="退货规则？")


def _setup(
    monkeypatch,
    *,
    answer_parts,
    rag=True,
    answerable=True,
    reason="answerable",
):
    context = {}
    graph = _Graph(
        context,
        answer_parts=answer_parts,
        rag=rag,
        answerable=answerable,
        reason=reason,
    )
    monkeypatch.setattr(chat, "graph", graph)
    monkeypatch.setattr(chat, "set_tool_ctx", lambda ctx: setattr(graph, "context", ctx))
    monkeypatch.setattr(chat, "start_trace", lambda **_kwargs: False)
    monkeypatch.setattr(chat, "end_trace", lambda **_kwargs: None)
    return graph


@pytest.mark.asyncio
async def test_rag_answer_is_buffered_then_emitted_once_with_allowed_citations(monkeypatch):
    graph = _setup(
        monkeypatch,
        answer_parts=["支持[商品](mall://product/999)七天", "退货。[S1]"],
    )
    response = await chat.chat_stream(_request(), _Request())
    stream = response.body_iterator

    first = _decode(await anext(stream))
    assert first[0] == "tool_result"
    assert graph.completed is False

    events = [_decode(item) async for item in stream]
    assert graph.calls == 1
    token_events = [data for event, data in events if event == "token"]
    done = next(data for event, data in events if event == "done")

    assert graph.completed is True
    assert token_events == [{"content": "支持商品七天退货。[S1]"}]
    assert "".join(event["content"] for event in token_events) == done["content"]
    assert done["citations"] == [
        {"id": "S1", "chunk_id": 7, "title": "退换货条款"}
    ]
    assert "[S1]" in done["content"]


@pytest.mark.asyncio
async def test_unknown_citation_never_leaks_invalid_model_text(monkeypatch):
    invalid = "模型编造的退货答案。[S9]"
    graph = _setup(monkeypatch, answer_parts=[invalid])
    response = await chat.chat_stream(_request(), _Request())

    events = [_decode(item) async for item in response.body_iterator]
    token_events = [data for event, data in events if event == "token"]
    done = next(data for event, data in events if event == "done")
    fallback = "当前知识库证据不足，暂时无法可靠回答该问题。"

    assert graph.calls == 1
    assert token_events == [{"content": fallback}]
    assert done["content"] == fallback
    assert done["citations"] == []
    assert all(invalid not in event["content"] for event in token_events)


@pytest.mark.asyncio
async def test_retrieval_unavailable_keeps_distinct_stream_message(monkeypatch):
    graph = _setup(
        monkeypatch,
        answer_parts=["模型声称没有相关资料。"],
        answerable=False,
        reason="retrieval_unavailable",
    )
    response = await chat.chat_stream(_request(), _Request())

    events = [_decode(item) async for item in response.body_iterator]
    tokens = [data["content"] for event, data in events if event == "token"]
    done = next(data for event, data in events if event == "done")

    assert graph.calls == 1
    assert tokens == ["知识库暂时不可用，请稍后再试。"]
    assert done["content"] == tokens[0]
    assert done["citations"] == []


@pytest.mark.asyncio
async def test_non_rag_tokens_still_stream_immediately(monkeypatch):
    graph = _setup(monkeypatch, answer_parts=["普通", "回答"], rag=False)
    response = await chat.chat_stream(_request(), _Request())
    stream = response.body_iterator

    first = _decode(await anext(stream))

    assert first == ("token", {"content": "普通"})
    assert graph.completed is False
    remaining = [_decode(item) async for item in stream]
    assert [data["content"] for event, data in remaining if event == "token"] == ["回答"]
    done = next(data for event, data in remaining if event == "done")
    assert done["content"] == "普通回答"
    assert "citations" not in done
