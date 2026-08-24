"""意图路由：查询各意图是否命中正确分支。"""
import json

import pytest

from app.agent.nodes import route_by_intent
from app.agent.state import AgentState


def _state(intent: str) -> AgentState:
    return AgentState(messages=[], intent=intent, tool_loop_count=0, escalated=False,
                      user_id="1", conversation_id="1", history=[], summary=None, web_search_enabled=False)


@pytest.mark.parametrize("intent,expected", [
    ("PRODUCT_CONSULT", "agent"),
    ("ORDER_QUERY", "agent"),
    ("ORDER_CREATE", "agent"),
    ("AFTER_SALE_FAQ", "agent"),
    ("SMALL_TALK", "small_talk"),
    ("ASSISTANT_META", "small_talk"),
    ("HUMAN_REQUEST", "escalate_node"),
])
def test_route_by_intent(intent, expected):
    assert route_by_intent(_state(intent)) == expected


def test_route_fallback_unknown_intent_goes_agent():
    assert route_by_intent(_state("UNKNOWN")) == "agent"


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeLLM:
    """同步注入意图 JSON 的假 LLM。"""

    def __init__(self, intent, confidence=0.9):
        self._payload = json.dumps({"intent": intent, "confidence": confidence})

    async def ainvoke(self, messages):
        return _FakeMessage(self._payload)


async def test_intent_router_node_parses_json(monkeypatch):
    from app.agent import nodes
    monkeypatch.setattr(nodes, "get_intent_llm", lambda: _FakeLLM("ORDER_QUERY", 0.95))
    state = AgentState(messages=[_FakeMessage("我的订单到哪了")], intent=None, tool_loop_count=0,
                       escalated=False, user_id="1", conversation_id="1", history=[], summary=None,
                       web_search_enabled=False)
    out = await nodes.intent_router_node(state)
    assert out["intent"] == "ORDER_QUERY"


async def test_intent_router_node_fallback_on_bad_json(monkeypatch):
    from app.agent import nodes

    class _BadLLM:
        async def ainvoke(self, messages):
            return _FakeMessage("这不是 JSON")

    monkeypatch.setattr(nodes, "get_intent_llm", lambda: _BadLLM())
    state = AgentState(messages=[_FakeMessage("随便")], intent=None, tool_loop_count=0,
                       escalated=False, user_id="1", conversation_id="1", history=[], summary=None,
                       web_search_enabled=False)
    out = await nodes.intent_router_node(state)
    assert out["intent"] == "PRODUCT_CONSULT"

def test_intent_prompt_explicitly_routes_identity_and_capability_questions():
    from app.agent.prompts import INTENT_SYSTEM_PROMPT

    assert "ASSISTANT_META" in INTENT_SYSTEM_PROMPT
    assert "你是谁" in INTENT_SYSTEM_PROMPT
    assert "你能帮我做什么" in INTENT_SYSTEM_PROMPT


class _ToolCallMessage:
    def __init__(self, name, args):
        self.tool_calls = [{"name": name, "args": args, "id": "call"}]
        self.content = ""


class _ToolResultMessage:
    tool_calls = []
    content = "result"


def _tool_loop_state(messages):
    return AgentState(messages=messages, intent="PRODUCT_CONSULT", tool_loop_count=2,
                      escalated=False, user_id="1", conversation_id="1", history=[],
                      summary=None, web_search_enabled=False)


def test_should_finalize_instead_of_reexecuting_identical_tool_call():
    from app.agent.nodes import FINALIZE_FLAG, should_continue
    first = _ToolCallMessage("product_search", {"category": "PHONE"})
    repeated = _ToolCallMessage("product_search", {"category": "PHONE"})

    assert should_continue(_tool_loop_state([first, _ToolResultMessage(), repeated])) == FINALIZE_FLAG


def test_should_execute_tool_again_when_arguments_change():
    from app.agent.nodes import should_continue
    first = _ToolCallMessage("product_search", {"category": "PHONE"})
    changed = _ToolCallMessage("product_search", {"category": "PHONE", "max_price": 3000})

    assert should_continue(_tool_loop_state([first, _ToolResultMessage(), changed])) == "tools"
