"""Identity is resolved once, from explicit user statements rather than AI output."""
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from app.agent.graph import build_graph
from app.agent import memory
from app.api.chat import ChatMessage, ChatRequest, build_state


def request(message="你叫什么", **kwargs):
    return ChatRequest(conversation_id=817, user_id=1, message=message, **kwargs)


def test_history_rebuilds_names_when_checkpoint_is_missing():
    state = build_state(request(user_profile={"nickname": "账号昵称", "assistant_name": "AI Mall"}, history=[
        ChatMessage(role="USER", content="从现在起，你叫派蒙，我叫旅行者"),
        ChatMessage(role="AI", content="我叫错误的名字"),
    ]))
    assert state["user_profile"]["assistant_name"] == "派蒙"
    assert state["user_profile"]["user_name"] == "旅行者"


def test_current_rename_has_highest_priority_and_does_not_mutate_inputs():
    profile = {"user_name": "旧用户", "assistant_name": "旧助手", "budget": "3000"}
    state = build_state(request("你叫小星，我叫小林", user_profile=profile, history=[
        ChatMessage(role="USER", content="你叫派蒙，我叫旅行者"),
    ]))
    assert state["user_profile"] == {"user_name": "小林", "assistant_name": "小星", "budget": "3000"}
    assert profile["assistant_name"] == "旧助手"


def test_only_user_history_can_change_identity():
    state = build_state(request(history=[ChatMessage(role="AI", content="你叫错误，我叫错误")]))
    assert not state["user_profile"].get("user_name")
    assert not state["user_profile"].get("assistant_name")


def test_regeneration_does_not_reuse_identity_from_discarded_checkpoint():
    cp = MemorySaver()
    graph = build_graph(cp)
    graph.update_state({"configurable": {"thread_id": "conv_817"}}, {
        "messages": [HumanMessage(content="你叫错误，我叫错误"), AIMessage(content="失败片段")],
        "user_profile": {"assistant_name": "错误", "user_name": "错误"},
    })
    state = build_state(request(options={"regenerate": True}, history=[
        ChatMessage(role="USER", content="你叫派蒙，我叫旅行者"),
    ]), cp)
    assert state["user_profile"]["assistant_name"] == "派蒙"
    assert state["user_profile"]["user_name"] == "旅行者"


async def test_explicit_name_is_not_rejected_by_a_placeholder_blacklist(monkeypatch):
    save = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(memory.backend_client, "upsert_user_memory", save)
    await memory.background_memory_extraction(1, "叫我朋友", "好的")
    save.assert_awaited_once_with(1, [{"category": "IDENTITY", "key": "user_name", "value": "朋友"}])


async def test_inferred_identity_cannot_overwrite_explicit_names(monkeypatch):
    extract = AsyncMock(return_value=[
        {"category": "IDENTITY", "key": "assistant_name", "value": "错名"},
        {"category": "FACT", "key": "user_name", "value": "误提取"},
        {"category": "PREFERENCE", "key": "brand", "value": "华为"},
    ])
    save = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(memory, "extract_memories_with_llm", extract)
    monkeypatch.setattr(memory.backend_client, "upsert_user_memory", save)
    await memory.background_memory_extraction(1, "我比较喜欢华为的手机", "我是购物助手")
    save.assert_awaited_once_with(1, [{"category": "PREFERENCE", "key": "brand", "value": "华为"}])


@pytest.mark.parametrize("text", ["你叫啥", "你叫啥名字", "我叫啥", "我叫什么名字"])
def test_colloquial_identity_questions_are_not_naming_commands(text):
    state = build_state(request(text, user_profile={"assistant_name": "派蒙", "user_name": "旅行者"}))
    assert state["user_profile"]["assistant_name"] == "派蒙"
    assert state["user_profile"]["user_name"] == "旅行者"
