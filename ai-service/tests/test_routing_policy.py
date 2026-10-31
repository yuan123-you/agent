"""Routing is decided once; the graph consumes the decision, not another classifier."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from app.agent import nodes
from app.agent.routing import RequestPolicy
from app.tools.tools import set_tool_ctx


@pytest.fixture(autouse=True)
def isolated_context():
    set_tool_ctx({})
    yield
    set_tool_ctx({})


@pytest.mark.parametrize("text,web,intent,route", [
    ("你太笨了，请转人工", False, "HUMAN_REQUEST", "escalate_node"),
    ("你太笨了", True, "SMALL_TALK", "small_talk"),
    ("帮我写一个排序算法", True, "SMALL_TALK", "small_talk"),
    ("你叫派蒙，我叫旅行者", True, "SMALL_TALK", "small_talk"),
    ("你是谁", True, "ASSISTANT_META", "small_talk"),
    ("平台退款规则是什么", True, "AFTER_SALE_FAQ", "agent"),
    ("推荐一款手机", False, "PRODUCT_CONSULT", "agent"),
])
async def test_semantic_or_local_decision_has_one_dispatch(monkeypatch, semantic_route, text, web, intent, route):
    semantic_route(intent)
    from types import SimpleNamespace
    needs_confirmation = RequestPolicy(text).fast_intent() is None and (intent in {"HUMAN_REQUEST", "AFTER_SALE_FAQ"} or (intent == "SMALL_TALK" and web))
    if needs_confirmation:
        factory = MagicMock(return_value=SimpleNamespace(ainvoke=AsyncMock(return_value=AIMessage(content='{"route":"HUMAN"}' if intent=="HUMAN_REQUEST" else ('{"route":"RULE"}' if intent=="AFTER_SALE_FAQ" else '{"route":"CHAT"}')))))
    else:
        factory = MagicMock(side_effect=AssertionError("Confident semantic/local decision needs no fallback"))
    monkeypatch.setattr(nodes, "get_intent_llm", factory)
    result = await nodes.intent_router_node({"messages": [HumanMessage(content=text)], "web_search_enabled": web})
    assert result["intent"] == intent
    assert result["reply_route"] == route
    assert nodes.route_by_intent(result) == route
    if needs_confirmation:
        factory.assert_called_once()
    else:
        factory.assert_not_called()


async def test_contextual_web_query_uses_one_classifier_then_reuses_its_route(monkeypatch):
    model = MagicMock()
    model.ainvoke = AsyncMock(return_value=AIMessage(content='{"intent":"SMALL_TALK","web_query":"北京明天天气"}'))
    monkeypatch.setattr(nodes, "get_intent_llm", lambda: model)
    state = {"messages": [HumanMessage(content="我明天去北京"), AIMessage(content="想了解天气？"),
                          HumanMessage(content="那里下雨吗")], "web_search_enabled": True}
    result = await nodes.intent_router_node(state)
    assert result["web_query"] == "北京明天天气"
    assert nodes.route_by_intent(result) == "agent"
    model.ainvoke.assert_awaited_once()


def test_graph_dispatch_does_not_reinterpret_a_completed_decision():
    assert nodes.route_by_intent({"intent": "SMALL_TALK", "reply_route": "small_talk",
                                  "web_search_enabled": True, "messages": []}) == "small_talk"


def test_unknown_intent_does_not_expose_web_search_when_disabled():
    assert "web_search" not in {tool.name for tool in nodes.get_tools_for_intent(None, False)}
