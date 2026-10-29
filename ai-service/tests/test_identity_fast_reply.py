"""Simple identity answers must not depend on remote model latency."""
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from app.agent import nodes
from app.agent.graph import build_graph
from app.api import chat
from app.tools.tools import set_tool_ctx


@pytest.fixture(autouse=True)
def isolated_context():
    set_tool_ctx({})
    yield
    set_tool_ctx({})


def forbid_models(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("A standalone identity question must not wait for a remote model")

    monkeypatch.setattr(nodes, "get_intent_llm", forbidden)
    monkeypatch.setattr(nodes, "get_chat_llm", forbidden)


@pytest.mark.parametrize("text", [
    "你是谁", "  你是谁？  ", "你叫什么", "你叫啥", "你的名字是什么", "介绍你自己", "介绍下你自己",
    "你能做什么", "你能帮我做什么", "你有什么功能", "你是真人还是机器人",
])
async def test_standalone_identity_answers_without_model_calls(monkeypatch, text):
    forbid_models(monkeypatch)
    result = await build_graph(MemorySaver()).ainvoke(
        {"messages": [HumanMessage(content=text)], "user_id": "1", "conversation_id": "1"},
        {"configurable": {"thread_id": "quick-identity"}},
    )
    assert result["intent"] == "ASSISTANT_META"
    answer = result["messages"][-1]
    assert isinstance(answer, AIMessage)
    assert "AI Mall" in answer.content
    assert all(word in answer.content for word in ("商品", "订单", "售后"))
    assert not answer.tool_calls


@pytest.mark.parametrize("text", [
    "你是谁，用英文回答", "你能做什么，顺便介绍退货政策", "为什么你是谁这个问题要等10秒",
])
async def test_contextual_meta_questions_keep_model_generation(monkeypatch, text):
    from unittest.mock import AsyncMock, MagicMock

    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="按用户要求回答"))
    monkeypatch.setattr(nodes, "get_chat_llm", lambda: llm)
    result = await nodes.small_talk_node({
        "intent": "ASSISTANT_META", "messages": [HumanMessage(content=text)],
    })
    llm.ainvoke.assert_awaited_once()
    assert result["messages"][0].content == "按用户要求回答"


async def test_identity_reply_is_sent_and_checkpointed_without_model_events(monkeypatch):
    forbid_models(monkeypatch)
    cp = MemorySaver()
    graph = build_graph(cp)
    config = {"configurable": {"thread_id": "conv_734"}}
    graph.update_state(config, {"messages": [
        HumanMessage(content="你好"), AIMessage(content="之前的回复"),
    ]})
    monkeypatch.setattr(chat, "checkpointer", cp)
    monkeypatch.setattr(chat, "graph", graph)

    class Request:
        async def is_disconnected(self):
            return False

    response = await chat.chat_stream(
        chat.ChatRequest(conversation_id=734, user_id=1, message="你是谁"), Request(),
    )
    events = []
    async for raw in response.body_iterator:
        if isinstance(raw, bytes):
            raw = raw.decode()
        lines = raw.strip().splitlines()
        events.append((lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: "))))
    assert not any(kind == "error" for kind, _ in events)
    content = "".join(data["content"] for kind, data in events if kind == "token")
    done = [data for kind, data in events if kind == "done"]
    assert len(done) == 1
    assert "AI Mall" in content
    assert done[0]["content"] == content
    assert not done[0]["timedOut"]
    assert graph.get_state(config).values["messages"][-1].content == content
