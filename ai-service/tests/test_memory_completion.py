"""Explicit identity commits precede done; optional extraction is response-owned."""
import json
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage
from app.api import chat
from app.agent import memory


class Request:
    async def is_disconnected(self):
        return False


class Graph:
    async def astream_events(self, *_args, **_kwargs):
        yield {"event": "on_chain_end", "name": "LangGraph", "data": {"output": {
            "messages": [AIMessage(content="记住了，你是旅行者，我是派蒙。")],
        }}}


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(chat, "graph", Graph())
    monkeypatch.setattr(chat, "checkpointer", None)
    monkeypatch.setattr(chat, "start_trace", lambda **kwargs: False)
    monkeypatch.setattr(chat, "end_trace", lambda **kwargs: None)


def decode(raw):
    if isinstance(raw, bytes):
        raw = raw.decode()
    event, data = raw.strip().splitlines()
    return event.removeprefix("event: "), json.loads(data.removeprefix("data: "))


async def test_explicit_identity_is_persisted_before_done(configured, monkeypatch):
    save = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(memory.backend_client, "upsert_user_memory", save)
    extract = AsyncMock()
    monkeypatch.setattr(chat, "background_memory_extraction", extract)
    response = await chat.chat_stream(chat.ChatRequest(user_id=1, conversation_id=1,
        message="你叫派蒙，我叫旅行者"), Request())
    async for raw in response.body_iterator:
        event, data = decode(raw)
        if event == "done":
            save.assert_awaited_once()
            assert data["memorySaved"] is True
    if response.background:
        await response.background()
    extract.assert_not_awaited()


async def test_optional_extraction_is_owned_by_response_not_detached_task(configured, monkeypatch):
    extract = AsyncMock()
    monkeypatch.setattr(chat, "background_memory_extraction", extract)
    response = await chat.chat_stream(chat.ChatRequest(user_id=1, conversation_id=1,
        message="我比较喜欢拍照好的手机"), Request())
    events = [decode(raw) async for raw in response.body_iterator]
    assert any(event == "done" for event, _ in events)
    extract.assert_not_awaited()
    assert response.background is not None
    await response.background()
    extract.assert_awaited_once()


async def test_identity_persistence_failure_is_reported_without_losing_answer(configured, monkeypatch):
    save = AsyncMock(return_value={"error": "backend unavailable"})
    monkeypatch.setattr(memory.backend_client, "upsert_user_memory", save)
    response = await chat.chat_stream(chat.ChatRequest(user_id=1, conversation_id=1,
        message="你叫派蒙，我叫旅行者"), Request())
    events = [decode(raw) async for raw in response.body_iterator]
    done = next(data for event, data in events if event == "done")
    assert done["memorySaved"] is False
    assert "派蒙" in done["content"]
    assert not any(event == "error" for event, _ in events)


@pytest.mark.parametrize("text", ["退款多久能到账？", "帮我查一下当前订单物流", "最近有哪些技术新闻？", "你还记得我叫什么名字吗"])
async def test_queries_do_not_spend_a_second_model_call_on_memory(configured, monkeypatch, text):
    infer = AsyncMock()
    monkeypatch.setattr(memory, "extract_memories_with_llm", infer)
    await memory.background_memory_extraction(1, text, "回答内容")
    infer.assert_not_awaited()


async def test_failed_naming_generation_is_not_replaced_with_fake_success(monkeypatch):
    from unittest.mock import MagicMock
    from langchain_core.messages import HumanMessage
    from app.agent import nodes
    model = MagicMock()
    model.ainvoke = AsyncMock(side_effect=RuntimeError("upstream disconnected"))
    monkeypatch.setattr(nodes, "get_chat_llm", lambda: model)
    with pytest.raises(RuntimeError, match="upstream disconnected"):
        await nodes.small_talk_node({"messages": [HumanMessage(content="你叫派蒙，我叫旅行者")]})


async def test_disconnect_stops_completion_and_durable_side_effects(configured, monkeypatch):
    class Disconnected:
        async def is_disconnected(self):
            return True
    save = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(memory.backend_client, "upsert_user_memory", save)
    response = await chat.chat_stream(chat.ChatRequest(user_id=1, conversation_id=1,
        message="你叫派蒙，我叫旅行者"), Disconnected())
    events = [decode(raw) async for raw in response.body_iterator]
    assert not any(event in {"done", "token"} for event, _ in events)
    save.assert_not_awaited()
