import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from app.agent import nodes
from app.tools.tools import set_tool_ctx

@pytest.fixture(autouse=True)
def isolated_context():
    set_tool_ctx({})
    yield
    set_tool_ctx({})

@pytest.mark.asyncio
async def test_confident_semantic_order_query_precedes_model_fallback(monkeypatch, semantic_route):
    semantic_route("ORDER_QUERY")
    model = SimpleNamespace(ainvoke=AsyncMock(return_value=AIMessage(content='{"intent":"SMALL_TALK"}')))
    monkeypatch.setattr(nodes, 'get_intent_llm', lambda: model)
    result = await nodes.intent_router_node({'messages': [HumanMessage(content='我的订单到哪了')]})
    assert result['intent'] == 'ORDER_QUERY'

@pytest.mark.asyncio
async def test_order_query_is_scheduled_even_if_model_ignores_tools(monkeypatch):
    class IgnoresTools:
        def bind_tools(self, *args, **kwargs):
            return self
        async def ainvoke(self, messages):
            return AIMessage(content='对不起，我需要查询您的订单以获取最新的物流信息。请稍等一下，我将帮您确认订单状态。')
    monkeypatch.setattr(nodes, 'get_chat_llm', lambda: IgnoresTools())
    state = {
        'intent': 'ORDER_QUERY',
        'messages': [HumanMessage(content='我的订单到哪了')],
        'tool_loop_count': 0,
        'active_entities': {},
    }
    result = await nodes.agent_node(state)
    calls = result['messages'][0].tool_calls
    assert len(calls) == 1
    assert calls[0]['name'] == 'order_query'
    assert calls[0]['args'].get('status') == 'ALL'
    assert result['tool_loop_count'] == 1

@pytest.mark.asyncio
async def test_order_query_is_not_rescheduled_after_tool_result(monkeypatch):
    class AnswerModel:
        def bind_tools(self, *args, **kwargs):
            return self
        async def ainvoke(self, messages):
            return AIMessage(content='您的订单已发货，物流单号为 SF123456789。')
    monkeypatch.setattr(nodes, 'get_chat_llm', lambda: AnswerModel())
    state = {
        'intent': 'ORDER_QUERY',
        'messages': [
            HumanMessage(content='我的订单到哪了'),
            AIMessage(content='', tool_calls=[{'name': 'order_query', 'args': {'status': 'ALL'}, 'id': 'o1'}]),
            ToolMessage(content='{"orders": []}', tool_call_id='o1', name='order_query'),
        ],
        'tool_loop_count': 1,
        'active_entities': {},
    }
    result = await nodes.agent_node(state)
    assert not getattr(result['messages'][0], 'tool_calls', None)
    assert '已发货' in result['messages'][0].content
