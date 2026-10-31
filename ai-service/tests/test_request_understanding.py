"""Regression coverage for misunderstood requests and unrequested human handoff."""
import json
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from app.agent import nodes
from app.agent.graph import build_graph
from app.tools import tools

class IntentLLM:
    def __init__(self, intent):
        self.intent, self.messages = intent, []
    async def ainvoke(self, messages):
        self.messages = messages
        return AIMessage(content=json.dumps({'intent': self.intent, 'confidence': 0.99, 'next_step': 'retrieve' if self.intent=='AFTER_SALE_FAQ' else 'assist'}))

@pytest.fixture(autouse=True)
def isolated_context():
    tools.set_tool_ctx({})
    yield
    tools.set_tool_ctx({})

@pytest.mark.asyncio
@pytest.mark.parametrize('text,model_intent,expected', [
    ('你是谁', 'HUMAN_REQUEST', 'ASSISTANT_META'),
    ('你能帮我做什么', 'PRODUCT_CONSULT', 'ASSISTANT_META'),
    ('你是真人还是机器人', 'HUMAN_REQUEST', 'ASSISTANT_META'),
    ('不要转人工，继续帮我推荐手机', 'HUMAN_REQUEST', 'PRODUCT_CONSULT'),
    ('不需要人工客服', 'HUMAN_REQUEST', 'SMALL_TALK'),
    ('人工客服几点上班', 'HUMAN_REQUEST', 'AFTER_SALE_FAQ'),
    ('请转人工客服', 'SMALL_TALK', 'HUMAN_REQUEST'),
    ('你好，帮我查订单', 'UNKNOWN', 'ORDER_QUERY'),
    ('帮我买一个拍照好看的手机', 'ORDER_CREATE', 'PRODUCT_CONSULT'),
])
async def test_semantic_request_route_precedes_model_guess(monkeypatch, semantic_route, text, model_intent, expected):
    semantic_route(expected)
    monkeypatch.setattr(nodes, 'get_intent_llm', lambda: IntentLLM(model_intent))
    result = await nodes.intent_router_node({'messages': [HumanMessage(content=text)]})
    assert result['intent'] == expected

@pytest.mark.asyncio
async def test_router_uses_checkpoint_messages_for_short_followup(monkeypatch):
    llm = IntentLLM('PRODUCT_CONSULT')
    monkeypatch.setattr(nodes, 'get_intent_llm', lambda: llm)
    await nodes.intent_router_node({'messages': [HumanMessage(content='拍照好的手机'),
        AIMessage(content='预算多少？'), HumanMessage(content='3000左右')], 'history': []})
    assert '拍照好的手机' in llm.messages[-1].content
    assert '预算多少' in llm.messages[-1].content

@pytest.mark.asyncio
async def test_misclassified_identity_question_never_calls_backend(monkeypatch):
    monkeypatch.setattr(nodes, 'get_intent_llm', lambda: IntentLLM('HUMAN_REQUEST'))
    monkeypatch.setattr(nodes, 'get_chat_llm', lambda: IntentLLM('ASSISTANT_META'))
    async def forbidden(**kwargs):
        pytest.fail('Identity questions must not request human handoff')
    monkeypatch.setattr(nodes.backend_client, 'escalate', forbidden)
    result = await build_graph(MemorySaver()).ainvoke({'messages': [HumanMessage(content='你是谁')],
        'user_id': '1', 'conversation_id': '1', 'tool_loop_count': 0},
        {'configurable': {'thread_id': 'identity-regression'}})
    assert result['intent'] == 'ASSISTANT_META'
    assert not result.get('escalated')

@pytest.mark.asyncio
async def test_handoff_tool_rejects_model_invented_permission(monkeypatch):
    tools.set_tool_ctx({'latest_user_text': '你是谁', 'user_id': '1', 'conversation_id': '1'})
    async def forbidden(**kwargs):
        pytest.fail('Tool must require the buyer to request handoff')
    monkeypatch.setattr(tools.backend_client, 'escalate', forbidden)
    result = await tools.escalate_to_human.ainvoke({'reason': '用户要求转人工'})
    assert 'error' in result
    assert not tools.get_tool_ctx().get('escalated')

@pytest.mark.asyncio
@pytest.mark.parametrize('budget,expected_min,expected_max', [('3000左右', None, 3000),
    ('预算2000到3000元', 2000, 3000), ('不超过2500元', None, 2500)])
async def test_search_applies_user_budget_even_when_model_omits_it(monkeypatch, budget, expected_min, expected_max):
    class ShoppingLLM:
        def bind_tools(self, *args, **kwargs):
            return self
        async def ainvoke(self, messages):
            return AIMessage(content='', tool_calls=[{'name': 'product_search', 'args': {}, 'id': 'search'}])
    monkeypatch.setattr(nodes, 'get_chat_llm', lambda: ShoppingLLM())
    await nodes.agent_node({'intent': 'PRODUCT_CONSULT', 'messages': [HumanMessage(content='拍照好的手机'), HumanMessage(content=budget)]})
    async def search(**kwargs):
        return {'products': [], 'filters': kwargs}
    monkeypatch.setattr(tools, '_observe_product', search)
    result = await tools.product_search.ainvoke({'category': 'COMPUTER'})
    assert result['filters']['category'] == 'PHONE'
    assert result['filters']['min_price'] == expected_min
    assert result['filters']['max_price'] == expected_max

@pytest.mark.asyncio
async def test_switching_category_does_not_keep_previous_budget(monkeypatch):
    class ShoppingLLM:
        def bind_tools(self, *args, **kwargs):
            return self
        async def ainvoke(self, messages):
            return AIMessage(content='请问您耳机预算多少？')
    monkeypatch.setattr(nodes, 'get_chat_llm', lambda: ShoppingLLM())
    result = await nodes.agent_node({'intent': 'PRODUCT_CONSULT',
        'messages': [HumanMessage(content='换成耳机吧')],
        'active_entities': {'last_category': 'PHONE', 'budget': {'min_price': None, 'max_price': 3000}}})
    assert not result['active_entities'].get('budget')

@pytest.mark.asyncio
async def test_wrong_category_keyword_cannot_contaminate_phone_search(monkeypatch):
    tools.set_tool_ctx({'requested_category': 'PHONE'})
    async def search(**kwargs):
        return {'products': [], 'filters': kwargs}
    monkeypatch.setattr(tools, '_observe_product', search)
    result = await tools.product_search.ainvoke({'category': 'COMPUTER', 'keyword': '游戏本电脑'})
    assert result['filters']['category'] == 'PHONE'
    assert result['filters']['keyword'] is None

@pytest.mark.parametrize('text,expected', [
    ('不要转人工', False), ('不用人工客服', False), ('怎么转人工', False),
    ('不是要转人工', False), ('人工客服几点上班', False), ('你是真人吗', False),
    ('帮我转人工', True), ('联系人工客服', True), ('找真人客服', True),
    ('我要投诉', True), ('不用推荐了，转人工', True),
])
def test_only_explicit_handoff_requests_authorize_transfer(text, expected):
    assert tools.requests_human(text) is expected

@pytest.mark.asyncio
@pytest.mark.parametrize('backend_result,expected', [({'success': True}, True), ({'error': 'unavailable'}, False)])
async def test_handoff_tool_reports_actual_backend_outcome(monkeypatch, backend_result, expected):
    tools.set_tool_ctx({'latest_user_text': '转人工', 'user_id': '1', 'conversation_id': '1'})
    async def escalate(**kwargs):
        return backend_result
    monkeypatch.setattr(tools.backend_client, 'escalate', escalate)
    result = await tools.escalate_to_human.ainvoke({'reason': '买家要求转接'})
    assert result == backend_result
    assert tools.get_tool_ctx()['escalated'] is expected

@pytest.mark.asyncio
@pytest.mark.parametrize('fallback', [False, True])
async def test_empty_search_clears_previous_recommendations(monkeypatch, fallback):
    tools.set_tool_ctx({'requested_category': 'PHONE', 'active_entities': {
        'last_category': 'PHONE', 'last_products': [{'id': 7, 'name': '旧推荐'}]}})
    async def search(**kwargs):
        return None if fallback else {'products': []}
    async def sql_search(**kwargs):
        return {'products': []}
    monkeypatch.setattr(tools, '_observe_product', search)
    monkeypatch.setattr(tools.backend_client, 'product_search', sql_search)
    await tools.product_search.ainvoke({'category': 'PHONE', 'max_price': 1000})
    assert not tools.get_tool_ctx()['active_entities'].get('last_products')

@pytest.mark.asyncio
async def test_sql_fallback_does_not_restore_rejected_keyword(monkeypatch):
    tools.set_tool_ctx({'requested_category': 'PHONE', 'requested_budget': {'min_price': None, 'max_price': 3000}})
    async def search(**kwargs):
        raise RuntimeError('vector search unavailable')
    async def sql_search(**kwargs):
        return {'products': [], 'filters': kwargs}
    monkeypatch.setattr(tools, '_observe_product', search)
    monkeypatch.setattr(tools.backend_client, 'product_search', sql_search)
    result = await tools.product_search.ainvoke({'category': 'COMPUTER', 'keyword': '游戏本电脑'})
    assert result['filters']['keyword'] is None
    assert result['filters']['category'] == 'PHONE'
    assert result['filters']['max_price'] == 3000

@pytest.mark.parametrize('text', ['我要人工客服', '我需要人工客服', '让真人客服来处理', '帮我接一下人工客服'])
def test_natural_explicit_handoff_phrasing_is_supported(text):
    assert tools.requests_human(text)

@pytest.mark.parametrize('text,expected', [
    ('预算3000以上', {'min_price': 3000, 'max_price': None}),
    ('预算2000到3000', {'min_price': 2000, 'max_price': 3000}),
    ('手机3000元', {'min_price': None, 'max_price': 3000}),
    ('看看iPhone17', {}), ('要256GB的', {}),
])
def test_budget_extraction_respects_bounds_and_ignores_model_numbers(text, expected):
    assert nodes.budget_from_text(text) == expected

@pytest.mark.asyncio
async def test_budget_reply_is_not_purchase_authorization(monkeypatch):
    monkeypatch.setattr(nodes, 'get_intent_llm', lambda: IntentLLM('ORDER_CREATE'))
    result = await nodes.intent_router_node({'messages': [HumanMessage(content='拍照手机'),
        AIMessage(content='您预算多少？'), HumanMessage(content='3000左右')]})
    assert result['intent'] == 'PRODUCT_CONSULT'

@pytest.mark.parametrize('text,expected',[
 ('最多三千五百',{'min_price':None,'max_price':3500}),
 ('两千五上下',{'min_price':None,'max_price':2500}),
 ('预算三千到四千',{'min_price':3000,'max_price':4000}),
 ('一百零五元',{'min_price':None,'max_price':105}),
 ('预算一万二',{'min_price':None,'max_price':12000}),
 ('最多三千台',{}),('几千元',{}),('第二款',{}),
])
def test_explicit_chinese_yuan_budgets_are_literal_not_model_guesses(text,expected):
    assert nodes.budget_from_text(text)==expected


@pytest.mark.asyncio
async def test_chinese_budget_continuation_reaches_the_actual_read_only_filter(monkeypatch):
    monkeypatch.setattr(nodes,'get_chat_llm',lambda:pytest.fail('Explicit budget filtering must not wait for model tool selection'))
    state={'intent':'PRODUCT_CONSULT','request_decision':{'intent':'PRODUCT_CONSULT','next_step':'assist'},
        'messages':[HumanMessage(content='想挑电脑'),AIMessage(content='您的预算多少？'),HumanMessage(content='最多三千五百')],
        'active_entities':{'last_category':'COMPUTER','last_products':[{'id':1,'name':'电脑','price':5000}]},'tool_loop_count':0}
    result=await nodes.agent_node(state)
    call=result['messages'][0].tool_calls[0]
    assert call['name']=='product_search' and call['args']['max_price']==3500

@pytest.mark.asyncio
async def test_order_amount_is_not_a_new_shopping_budget():
    state={'intent':'ORDER_QUERY','request_decision':{'intent':'ORDER_QUERY','next_step':'assist'},
        'messages':[HumanMessage(content='请查我那笔两千元的订单')],
        'active_entities':{'last_category':'COMPUTER','budget':{'max_price':3500}},'tool_loop_count':0}
    result=await nodes.agent_node(state)
    assert result['messages'][0].tool_calls[0]['name']=='order_query'
    assert result['active_entities']['budget']=={'max_price':3500}
