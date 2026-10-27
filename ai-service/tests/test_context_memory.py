"""上下文记忆与多轮会话实体链路专项测试"""
from unittest.mock import AsyncMock, patch
import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from app.agent.graph import build_graph
from app.agent.nodes import fallback_intent_by_rules, intent_router_node
from app.api.chat import ChatMessage, ChatRequest, build_state
from app.request_policy import (
    asks_assistant_identity,
    asks_conversation_context,
    asks_mutual_identity,
    asks_user_identity,
)
from app.tools.tools import clean_search_keyword, get_tool_ctx, order_create, product_detail, set_tool_ctx


@pytest.fixture(autouse=True)
def isolated_ctx():
    set_tool_ctx({})
    yield
    set_tool_ctx({})


def test_user_and_context_identity_detection():
    # 问自己名字
    assert asks_user_identity("我叫什么名字") is True
    assert asks_user_identity("我是谁") is True
    assert asks_user_identity("你知道我是谁吗") is True
    assert asks_user_identity("你还记得我叫什么吗") is True
    assert asks_user_identity("我的名字是什么") is True
    assert asks_user_identity("我叫啥") is True

    # 双方互问
    assert asks_mutual_identity("你叫什么名字，我叫什么名字") is True
    assert asks_mutual_identity("你是谁我是谁") is True
    assert asks_mutual_identity("你叫什么我叫什么") is True

    # 问前序对话内容
    assert asks_conversation_context("我刚才问了你什么") is True
    assert asks_conversation_context("我刚才说了什么") is True
    assert asks_conversation_context("我上一句话说了什么") is True
    assert asks_conversation_context("刚才我们聊了什么") is True
    assert asks_conversation_context("我们刚才聊了什么") is True
    assert asks_conversation_context("刚才聊了什么") is True
    assert asks_conversation_context("聊到哪了") is True

    # 普通购物提问不误判
    assert asks_user_identity("推荐一款拍照好的手机") is False
    assert asks_mutual_identity("推荐一款拍照好的手机") is False
    assert asks_conversation_context("推荐一款拍照好的手机") is False


def test_fallback_intent_for_context_and_user_identity():
    assert fallback_intent_by_rules("我叫什么名字") in {"SMALL_TALK", "ASSISTANT_META"}
    assert fallback_intent_by_rules("我是谁") in {"SMALL_TALK", "ASSISTANT_META"}
    assert fallback_intent_by_rules("你还记得我叫什么吗") in {"SMALL_TALK", "ASSISTANT_META"}
    assert fallback_intent_by_rules("你叫什么名字，我叫什么名字") in {"SMALL_TALK", "ASSISTANT_META"}
    assert fallback_intent_by_rules("我刚才问了你什么") in {"SMALL_TALK", "ASSISTANT_META"}
    assert fallback_intent_by_rules("刚才我们聊了什么") in {"SMALL_TALK", "ASSISTANT_META"}


@pytest.mark.asyncio
async def test_small_talk_recalls_user_name_directly():
    cp = MemorySaver()
    graph = build_graph(cp)

    res = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="我叫什么名字")],
            "user_id": "1",
            "conversation_id": "301",
            "user_profile": {"user_name": "派蒙"},
        },
        {"configurable": {"thread_id": "conv_301"}},
    )
    answer = res["messages"][-1].content
    assert "派蒙" in answer


@pytest.mark.asyncio
async def test_small_talk_recalls_mutual_names_directly():
    cp = MemorySaver()
    graph = build_graph(cp)

    res = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="你叫什么名字，我叫什么名字")],
            "user_id": "1",
            "conversation_id": "302",
            "user_profile": {"assistant_name": "大肥鱼", "user_name": "派蒙"},
        },
        {"configurable": {"thread_id": "conv_302"}},
    )
    answer = res["messages"][-1].content
    assert "大肥鱼" in answer
    assert "派蒙" in answer


def test_clean_search_keyword_preference_and_pronouns():
    assert clean_search_keyword("换便宜点的") is None
    assert clean_search_keyword("有没有便宜一点的") is None
    assert clean_search_keyword("推荐一款手机 便宜一点的") == "手机"
    assert clean_search_keyword("第一款") is None
    assert clean_search_keyword("第二款") is None
    assert clean_search_keyword("再推荐几款别的") is None


@pytest.mark.asyncio
async def test_order_create_resolves_ordinal_from_active_entities():
    ctx = {
        "user_id": "1",
        "conversation_id": "303",
        "latest_user_text": "帮我下单第二款",
        "active_entities": {
            "last_products": [
                {"id": 101, "name": "手机A", "price": 2999},
                {"id": 102, "name": "手机B", "price": 3999},
            ]
        },
    }
    set_tool_ctx(ctx)

    with patch("app.tools.tools.backend_client.order_prepare", new_callable=AsyncMock) as mock_prepare:
        mock_prepare.return_value = {"orderId": 501, "totalAmount": 3999}
        res = await order_create.ainvoke({"quantity": 1})
        mock_prepare.assert_awaited_once()
        kwargs = mock_prepare.call_args[1]
        assert kwargs["product_id"] == 102


@pytest.mark.asyncio
async def test_product_detail_resolves_ordinal_from_active_entities():
    ctx = {
        "user_id": "1",
        "conversation_id": "304",
        "latest_user_text": "详细介绍下第二款",
        "active_entities": {
            "last_products": [
                {"id": 101, "name": "手机A", "price": 2999},
                {"id": 102, "name": "手机B", "price": 3999},
            ]
        },
    }
    set_tool_ctx(ctx)

    with patch("app.tools.tools.backend_client.product_detail", new_callable=AsyncMock) as mock_detail:
        mock_detail.return_value = {"productId": 102, "name": "手机B", "price": 3999}
        res = await product_detail.ainvoke({})
        mock_detail.assert_awaited_once()
        kwargs = mock_detail.call_args[1]
        assert kwargs["product_id"] == 102


def test_build_state_recovers_entities_from_history_without_checkpoint():
    req = ChatRequest(
        conversation_id=305,
        user_id=1,
        message="第一款多少钱",
        history=[
            ChatMessage(role="USER", content="我想买手机，预算在3000左右"),
            ChatMessage(role="AI", content="为您推荐了以下手机..."),
        ],
    )
    state = build_state(req, checkpointer=None)
    entities = state.get("active_entities") or {}
    assert entities.get("last_category") == "PHONE"
    assert entities.get("budget") == {"min_price": None, "max_price": 3000.0}
