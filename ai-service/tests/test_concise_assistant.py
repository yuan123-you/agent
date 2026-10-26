"""Narrow latency fast paths and concise shopping response contracts."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from app.agent import nodes
from app.agent.prompts import SHOP_SYSTEM_PROMPT, FINALIZE_SYSTEM_PROMPT, SMALL_TALK_PROMPT
from app.tools.tools import get_tool_ctx, set_tool_ctx


@pytest.fixture(autouse=True)
def isolated_context():
    set_tool_ctx({})
    yield
    set_tool_ctx({})


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [
    "推荐一款3000以内拍照好的手机", "帮我推荐游戏笔记本", "给我推荐一双鞋子", "请帮我找个背包。",
])
async def test_clear_shopping_request_skips_intent_inference(monkeypatch, text):
    factory = MagicMock(side_effect=AssertionError("unnecessary intent inference"))
    monkeypatch.setattr(nodes, "get_intent_llm", factory)
    result = await nodes.intent_router_node({"messages": [HumanMessage(content=text)]})
    assert result["intent"] == "PRODUCT_CONSULT"
    factory.assert_not_called()
    assert get_tool_ctx()["latest_user_text"] == text


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [
    "谢谢，顺便推荐个手机", "推荐手机，顺便查订单", "推荐手机退货怎么办", "帮我下单手机",
    "这个怎么样", "3000", "随便", "打游戏", "我想买这个手机", "推荐手机支持七天退货吗", "帮我找手机订单",
])
async def test_mixed_contextual_and_action_requests_keep_classifier(monkeypatch, text):
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content='{"intent":"PRODUCT_CONSULT"}'))
    monkeypatch.setattr(nodes, "get_intent_llm", lambda: llm)
    await nodes.intent_router_node({"messages": [HumanMessage(content=text)]})
    llm.ainvoke.assert_awaited_once()


@pytest.mark.parametrize("prompt", [SHOP_SYSTEM_PROMPT, SMALL_TALK_PROMPT, FINALIZE_SYSTEM_PROMPT],
                         ids=["shopping", "small-talk", "finalization"])
def test_response_prompts_allow_full_answers_without_arbitrary_caps(prompt):
    for restriction in ("默认用1—3句", "默认只用1句话", "最多推荐3款", "每款一行",
                        "只问一个必要问题", "每个商品一行", "一句推荐理由"):
        assert restriction not in prompt
    assert "不设固定句数、字数" in prompt
    assert "充分展开" in prompt


def test_response_style_preserves_context_and_business_safety():
    assert "不重复追问" in SHOP_SYSTEM_PROMPT
    assert "[Sx]" in SHOP_SYSTEM_PROMPT
    assert "等待买家点击卡片" in SHOP_SYSTEM_PROMPT
