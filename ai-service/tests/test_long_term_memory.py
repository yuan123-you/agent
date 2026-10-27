"""长期记忆与多轮人设感知综合测试（精准复现与验证截图场景）"""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from app.agent.graph import build_graph
from app.agent.memory import (
    format_assistant_greeting,
    format_memory_prompt,
    parse_naming_command,
    background_memory_extraction,
)
from app.api import chat
from app.tools.tools import set_tool_ctx


@pytest.fixture(autouse=True)
def isolated_ctx():
    set_tool_ctx({})
    yield
    set_tool_ctx({})


def test_parse_naming_command_extracts_roles():
    # 双方互定
    cmd1 = "从现在开始，你叫大肥鱼，我叫派蒙，记住了吗"
    res1 = parse_naming_command(cmd1)
    assert res1 == {"assistant_name": "大肥鱼", "user_name": "派蒙"}

    cmd2 = "你叫大肥鱼，我叫派蒙"
    res2 = parse_naming_command(cmd2)
    assert res2 == {"assistant_name": "大肥鱼", "user_name": "派蒙"}

    cmd3 = "我叫派蒙，你叫大肥鱼"
    res3 = parse_naming_command(cmd3)
    assert res3 == {"assistant_name": "大肥鱼", "user_name": "派蒙"}

    # 单独指定
    assert parse_naming_command("从现在开始你叫大肥鱼") == {"assistant_name": "大肥鱼"}
    assert parse_naming_command("我叫派蒙") == {"user_name": "派蒙"}
    assert parse_naming_command("叫我派蒙") == {"user_name": "派蒙"}

    # 普通提问不误判
    assert parse_naming_command("你是谁") == {}
    assert parse_naming_command("我叫什么名字") == {}
    assert parse_naming_command("推荐一款拍照好的手机") == {}


def test_format_assistant_greeting_with_persona():
    # 无自定义时保持基线
    greeting_default = format_assistant_greeting({})
    assert "我是「AI Mall」的 AI 购物助手" in greeting_default
    assert all(w in greeting_default for w in ("商品", "订单", "售后"))

    # 自定义人设时融合展示
    greeting_custom = format_assistant_greeting({"assistant_name": "大肥鱼", "user_name": "派蒙"})
    assert "我是「AI Mall」的 AI 购物助手（也是您的专属伙伴「大肥鱼」）" in greeting_custom
    assert "派蒙" in greeting_custom
    assert all(w in greeting_custom for w in ("商品", "订单", "售后"))


def test_format_memory_prompt_generates_markdown():
    profile = {"user_name": "派蒙", "assistant_name": "大肥鱼", "budget": "3000左右"}
    memories = [
        {"category": "PREFERENCE", "key": "favorite_feature", "value": "拍照好"},
        {"category": "FACT", "key": "pet", "value": "家里有一只猫"},
    ]
    prompt = format_memory_prompt(profile, memories)
    assert "派蒙" in prompt
    assert "大肥鱼" in prompt
    assert "拍照好" in prompt
    assert "家里有一只猫" in prompt
    assert "你叫「大肥鱼」，用户叫「派蒙」" in prompt


@pytest.mark.asyncio
async def test_naming_command_immediately_updates_active_turn_state():
    req = chat.ChatRequest(
        conversation_id=101,
        user_id=1,
        message="从现在开始，你叫大肥鱼，我叫派蒙，记住了吗",
        user_profile={},
    )
    state = chat.build_state(req)
    assert state.get("user_profile", {}).get("assistant_name") == "大肥鱼"
    assert state.get("user_profile", {}).get("user_name") == "派蒙"


@pytest.mark.asyncio
async def test_identity_question_recalls_custom_names_in_fast_reply():
    cp = MemorySaver()
    graph = build_graph(cp)
    
    # 注入带有派蒙与大肥鱼人设的请求
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="你是谁")],
            "user_id": "1",
            "conversation_id": "102",
            "user_profile": {"assistant_name": "大肥鱼", "user_name": "派蒙"},
        },
        {"configurable": {"thread_id": "conv_102"}},
    )
    answer = result["messages"][-1].content
    assert "大肥鱼" in answer
    assert "派蒙" in answer
    assert "AI Mall" in answer
    assert all(w in answer for w in ("商品", "订单", "售后"))


@pytest.mark.asyncio
async def test_multi_turn_persona_retention_reproducing_screenshot():
    """复现并验证截图中的全链路：
    Turn 1: 用户设定你叫大肥鱼，我叫派蒙
    Turn 2: 用户问你是谁，回答包含大肥鱼与派蒙
    Turn 3: 新会话继承长期记忆，问我叫什么名字，AI依然准确回答派蒙
    """
    cp = MemorySaver()
    graph = build_graph(cp)
    config = {"configurable": {"thread_id": "conv_200"}}

    # Turn 1: 设定名字
    state1 = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="从现在开始，你叫大肥鱼，我叫派蒙，记住了吗")],
            "user_id": "1",
            "conversation_id": "200",
            "user_profile": {"assistant_name": "大肥鱼", "user_name": "派蒙"},
        },
        config,
    )
    # Checkpoint 应记录 user_profile
    assert state1.get("user_profile", {}).get("assistant_name") == "大肥鱼"

    # Turn 2: 问你是谁（快速身份回复）
    state2 = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="你是谁")],
            "user_id": "1",
            "conversation_id": "200",
            "user_profile": state1.get("user_profile"),
        },
        config,
    )
    reply2 = state2["messages"][-1].content
    assert "大肥鱼" in reply2
    assert "派蒙" in reply2

    # Turn 3: 跨会话测试（新会话 ID conv_201，从数据库加载长期记忆 user_profile）
    config_new = {"configurable": {"thread_id": "conv_201"}}
    loaded_profile_from_db = {"user_name": "派蒙", "assistant_name": "大肥鱼"}
    state3 = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="你是谁")],
            "user_id": "1",
            "conversation_id": "201",
            "user_profile": loaded_profile_from_db,
        },
        config_new,
    )
    reply3 = state3["messages"][-1].content
    assert "大肥鱼" in reply3
    assert "派蒙" in reply3


@pytest.mark.asyncio
async def test_background_memory_extraction_calls_backend():
    with patch("app.agent.memory.backend_client.upsert_user_memory", new_callable=AsyncMock) as mock_upsert:
        mock_upsert.return_value = {"code": 0}
        await background_memory_extraction(
            user_id=12,
            user_text="从现在开始，你叫大肥鱼，我叫派蒙，记住了吗",
            ai_text="哈哈，派蒙，我是大肥鱼，记住了！",
        )
        mock_upsert.assert_awaited_once()
        called_args = mock_upsert.call_args[0]
        assert called_args[0] == 12
        memories = called_args[1]
        keys = {m["key"]: m["value"] for m in memories}
        assert keys.get("assistant_name") == "大肥鱼"
        assert keys.get("user_name") == "派蒙"


@pytest.mark.asyncio
async def test_mutual_identity_when_assistant_name_not_set_or_empty():
    cp = MemorySaver()
    graph = build_graph(cp)

    # 1. 用户未设置助手名字，但有昵称 paimeng: 绝对不产生空书名号「」
    result1 = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="你是谁，我是谁")],
            "user_id": "1",
            "conversation_id": "103",
            "user_profile": {"nickname": "paimeng", "assistant_name": ""},
        },
        {"configurable": {"thread_id": "conv_103"}},
    )
    ans1 = result1["messages"][-1].content
    assert "「」" not in ans1, f"Empty bracket found in: {ans1}"
    assert "paimeng" in ans1
    assert "我是「AI Mall」智能购物助手" in ans1

    # 2. 用户设定了助手名字大肥鱼: 正常呈现专属伙伴大肥鱼
    result2 = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="你是谁，我是谁")],
            "user_id": "1",
            "conversation_id": "104",
            "user_profile": {"user_name": "派蒙", "assistant_name": "大肥鱼"},
        },
        {"configurable": {"thread_id": "conv_104"}},
    )
    ans2 = result2["messages"][-1].content
    assert "「大肥鱼」" in ans2
    assert "「派蒙」" in ans2
