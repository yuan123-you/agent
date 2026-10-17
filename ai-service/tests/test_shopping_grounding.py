import json
import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from app.agent import nodes
from app.api import chat
from app.tools import tools

@pytest.fixture(autouse=True)
def isolated_context():
    tools.set_tool_ctx({})
    yield
    tools.set_tool_ctx({})

class LLM:
    def bind_tools(self, bound_tools, **kwargs):
        self.choice = kwargs.get('tool_choice')
        return self
    async def ainvoke(self, messages):
        return AIMessage(content='', tool_calls=[{'name': 'product_search', 'args': {'category': 'COMPUTER'}, 'id': 's1'}])

@pytest.mark.asyncio
async def test_phone_request_overrides_computer_memory_and_requires_search(monkeypatch):
    llm = LLM()
    monkeypatch.setattr(nodes, 'get_chat_llm', lambda: llm)
    result = await nodes.agent_node({
        'intent': 'ORDER_CREATE',
        'messages': [HumanMessage(content='推荐笔记本电脑'), AIMessage(content='游戏本、轻薄本'), HumanMessage(content='帮我买一个拍照好看的手机')],
        'active_entities': {'last_category': 'COMPUTER', 'last_products': [{'id': 9, 'name': '游戏本'}]},
    })
    assert result['messages'][0].tool_calls[0]['name'] == 'product_search'
    assert result['active_entities']['last_category'] == 'PHONE'
    assert not result['active_entities'].get('last_products')

@pytest.mark.asyncio
async def test_budget_followup_keeps_phone_despite_wrong_model_category(monkeypatch):
    monkeypatch.setattr(nodes, 'get_chat_llm', lambda: LLM())
    await nodes.agent_node({'intent': 'PRODUCT_CONSULT', 'messages': [
        HumanMessage(content='帮我买一个拍照好看的手机'), AIMessage(content='比如游戏本、轻薄本？'),
        HumanMessage(content='性价比高的'), HumanMessage(content='3000左右')],
    })
    async def search(**kwargs):
        return {'products': [], 'category_used': kwargs['category']}
    monkeypatch.setattr(tools, '_observe_product', search)
    result = await tools.product_search.ainvoke({'category': 'COMPUTER', 'max_price': 3000})
    assert result['category_used'] == 'PHONE'

@pytest.mark.asyncio
async def test_product_detail_is_not_forced_back_to_search(monkeypatch):
    llm = LLM()
    monkeypatch.setattr(nodes, 'get_chat_llm', lambda: llm)
    await nodes.agent_node({'intent': 'PRODUCT_CONSULT', 'messages': [HumanMessage(content='这款手机的参数呢')],
        'active_entities': {'last_category': 'PHONE', 'last_products': [{'id': 1, 'name': '手机'}]}})
    assert llm.choice is None

class Request:
    async def is_disconnected(self):
        return False

async def stream_search_answer(monkeypatch, products, answer):
    class Graph:
        async def astream_events(self, *args, **kwargs):
            yield {'event': 'on_tool_end', 'name': 'product_search', 'run_id': 's1',
                'data': {'output': ToolMessage(content=json.dumps({'products': products}), tool_call_id='s1', name='product_search')}}
            yield {'event': 'on_chat_model_stream', 'metadata': {'langgraph_node': 'agent'}, 'data': {'chunk': AIMessageChunk(content=answer)}}
            yield {'event': 'on_chain_end', 'name': 'LangGraph', 'data': {'output': {}}}
    monkeypatch.setattr(chat, 'graph', Graph())
    monkeypatch.setattr(chat, 'checkpointer', None)
    monkeypatch.setattr(chat, 'start_trace', lambda **kwargs: False)
    monkeypatch.setattr(chat, 'end_trace', lambda **kwargs: None)
    response = await chat.chat_stream(chat.ChatRequest(conversation_id=12, user_id=1, message='3000左右'), Request())
    events = []
    async for raw in response.body_iterator:
        if isinstance(raw, bytes):
            raw = raw.decode()
        lines = raw.strip().splitlines()
        events.append((lines[0].removeprefix('event: '), json.loads(lines[1].removeprefix('data: '))))
    return events

@pytest.mark.asyncio
@pytest.mark.parametrize('answer', ['为您找到了几款手机。[产品链接]。', '为您找到了几款手机。'])
async def test_stream_repairs_missing_links_from_actual_products(monkeypatch, answer):
    events = await stream_search_answer(monkeypatch, [{'productId': 101, 'name': '拍照手机', 'price': 2899, 'link': 'mall://product/101'}], answer)
    done = next(data for event, data in events if event == 'done')
    assert '[拍照手机](mall://product/101)' in done['content']
    assert '[产品链接]' not in done['content']
    assert ''.join(data['content'] for event, data in events if event == 'token') == done['content']

@pytest.mark.asyncio
async def test_empty_search_cannot_claim_products_were_found(monkeypatch):
    events = await stream_search_answer(monkeypatch, [], '为您找到了几款手机。[产品链接]。')
    text = next(data for event, data in events if event == 'done')['content']
    assert '未找到' in text
    assert '为您找到了' not in text
    assert 'mall://' not in text

@pytest.mark.asyncio
async def test_valid_linked_answer_is_preserved(monkeypatch):
    answer = '推荐 [拍照手机](mall://product/101)，售价2899元。'
    events = await stream_search_answer(monkeypatch, [{'productId': 101, 'name': '拍照手机', 'link': 'mall://product/101'}], answer)
    assert next(data for event, data in events if event == 'done')['content'] == answer

@pytest.mark.asyncio
async def test_new_budget_forces_fresh_lookup_even_with_previous_products(monkeypatch):
    llm = LLM()
    monkeypatch.setattr(nodes, 'get_chat_llm', lambda: llm)
    result = await nodes.agent_node({'intent': 'PRODUCT_CONSULT', 'messages': [
        HumanMessage(content='拍照好的手机'), AIMessage(content='先看看这款'), HumanMessage(content='3000左右')],
        'active_entities': {'last_category': 'PHONE', 'last_products': [{'id': 1, 'name': '昂贵手机'}]}})
    assert result['messages'][0].tool_calls[0]['name'] == 'product_search'

@pytest.mark.asyncio
async def test_search_does_not_overwrite_order_confirmation(monkeypatch):
    class Graph:
        async def astream_events(self, *args, **kwargs):
            yield {'event': 'on_tool_end', 'name': 'product_search', 'run_id': 's1', 'data': {'output': {
                'products': [{'productId': 101, 'name': '拍照手机', 'link': 'mall://product/101'}]}}}
            yield {'event': 'on_tool_end', 'name': 'order_create', 'run_id': 's2', 'data': {'output': {'prepared': True}}}
            yield {'event': 'on_chat_model_stream', 'metadata': {'langgraph_node': 'agent'},
                'data': {'chunk': AIMessageChunk(content='已生成确认卡片，请确认后下单。')}}
            yield {'event': 'on_chain_end', 'name': 'LangGraph', 'data': {'output': {}}}
    monkeypatch.setattr(chat, 'graph', Graph())
    monkeypatch.setattr(chat, 'checkpointer', None)
    monkeypatch.setattr(chat, 'start_trace', lambda **kwargs: False)
    monkeypatch.setattr(chat, 'end_trace', lambda **kwargs: None)
    response = await chat.chat_stream(chat.ChatRequest(conversation_id=13, user_id=1, message='买这款'), Request())
    output = ''.join([raw.decode() if isinstance(raw, bytes) else raw async for raw in response.body_iterator])
    assert '已生成确认卡片，请确认后下单。' in output
    assert '为您找到以下在售商品' not in output

@pytest.mark.parametrize('result,expected', [
    ({'error': 'backend unavailable'}, '商品检索暂时不可用'),
    ({'products': [{'name': '手机', 'link': 'https://evil.example/product/1'}]}, '商品链接暂时不可用'),
    ({'products': [{'name': '手机'}]}, '商品链接暂时不可用'),
])
def test_link_fallback_never_invents_links(result, expected):
    from app.agent.link_guard import ensure_product_links
    text = ensure_product_links('[产品链接]', result)
    assert expected in text
    assert 'https://' not in text
    assert 'mall://' not in text

@pytest.mark.asyncio
async def test_search_is_not_forced_again_after_current_turn_tool_result(monkeypatch):
    llm = LLM()
    monkeypatch.setattr(nodes, 'get_chat_llm', lambda: llm)
    await nodes.agent_node({'intent': 'PRODUCT_CONSULT', 'messages': [
        HumanMessage(content='3000左右的手机'),
        AIMessage(content='', tool_calls=[{'name': 'product_search', 'args': {'category': 'PHONE'}, 'id': 's1'}]),
        ToolMessage(content='{"products": []}', tool_call_id='s1', name='product_search')], 'tool_loop_count': 1})
    assert llm.choice is None

@pytest.mark.asyncio
@pytest.mark.parametrize('latest,previous_products', [
    ('帮我买一个拍照好看的手机', []),
    ('性价比高的', [{'id': 101, 'name': '旧手机'}]),
])
async def test_required_search_is_executed_even_if_model_ignores_tool_choice(monkeypatch, latest, previous_products):
    class IgnoresTools:
        def bind_tools(self, *args, **kwargs):
            return self
        async def ainvoke(self, messages):
            return AIMessage(content='推荐一款手机：[商品链接]。')
    monkeypatch.setattr(nodes, 'get_chat_llm', lambda: IgnoresTools())
    state = {'intent': 'PRODUCT_CONSULT', 'messages': [HumanMessage(content='拍照好的手机'), HumanMessage(content=latest)],
             'active_entities': {'last_category': 'PHONE', 'last_products': previous_products}}
    result = await nodes.agent_node(state)
    calls = result['messages'][-1].tool_calls
    assert len(calls) == 1
    assert calls[0]['name'] == 'product_search'
    assert calls[0]['args']['category'] == 'PHONE'
    assert '拍照' in calls[0]['args']['keyword']
    assert result['tool_loop_count'] == 1

@pytest.mark.asyncio
async def test_forced_lookup_is_not_repeated_after_real_tool_result(monkeypatch):
    class Answer:
        def bind_tools(self, *args, **kwargs):
            return self
        async def ainvoke(self, messages):
            return AIMessage(content='推荐 [拍照手机](mall://product/101)。')
    monkeypatch.setattr(nodes, 'get_chat_llm', lambda: Answer())
    result = await nodes.agent_node({'intent': 'PRODUCT_CONSULT', 'tool_loop_count': 1,
        'messages': [HumanMessage(content='推荐拍照手机'),
            AIMessage(content='', tool_calls=[{'name': 'product_search', 'args': {'category': 'PHONE'}, 'id': 's1'}]),
            ToolMessage(content='{"products":[]}', tool_call_id='s1', name='product_search')]})
    assert not result['messages'][-1].tool_calls
