"""Latency regressions for actual semantic classification and evidence-backed web turns."""
import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from app.agent import nodes
from app.tools.tools import set_tool_ctx

@pytest.fixture(autouse=True)
def isolated_ctx():
    set_tool_ctx({}); yield; set_tool_ctx({})

def web_state(intent='SMALL_TALK'):
    return {'intent':intent,'web_search_enabled':True,'messages':[
        HumanMessage(content='最近人工智能领域有哪些新闻？'),
        AIMessage(content='',tool_calls=[{'name':'web_search','args':{'query':'人工智能新闻'},'id':'web1'}]),
        ToolMessage(content=json.dumps({'results':[{'title':'真实资料','snippet':'已检索到的信息','url':'https://example.com/source'}]},ensure_ascii=False),name='web_search',tool_call_id='web1'),
    ],'tool_loop_count':1}

def test_general_web_questions_do_not_bind_commerce_mutation_tools():
    assert [t.name for t in nodes.get_tools_for_intent('SMALL_TALK',True)] == ['web_search']
    assert nodes.get_tools_for_intent('SMALL_TALK',False) == []

def test_only_general_web_evidence_enters_the_terminal_web_answer():
    assert nodes.route_after_tools(web_state()) == 'web_answer'
    for intent in ['PRODUCT_CONSULT','ORDER_QUERY','ORDER_CREATE','AFTER_SALE_FAQ','HUMAN_REQUEST']:
        assert nodes.route_after_tools(web_state(intent)) == 'agent'
    mixed=web_state(); mixed['messages'].append(ToolMessage(content='{}',name='kb_search',tool_call_id='kb1'))
    assert nodes.route_after_tools(mixed) == 'agent'

async def test_terminal_web_answer_has_no_tool_schema_and_a_compact_grounding_prompt(monkeypatch):
    llm=MagicMock(); llm.ainvoke=AsyncMock(return_value=AIMessage(content='【联网搜索】依据真实资料回答'))
    monkeypatch.setattr(nodes,'get_chat_llm',lambda:llm)
    result=await nodes.web_answer_node(web_state())
    llm.bind_tools.assert_not_called()
    messages=llm.ainvoke.call_args.args[0]
    assert len(messages[0].content) < 1200
    assert '【联网搜索】' in messages[0].content
    assert '不设固定句数、字数' in messages[0].content
    assert any('真实资料' in str(m.content) for m in messages)
    assert result['messages'][0].content.startswith('【联网搜索】')

async def test_classifier_ignores_verbose_assistant_prose_but_keeps_user_requirements_and_clarifying_tail(monkeypatch):
    llm=MagicMock();llm.ainvoke=AsyncMock(return_value=AIMessage(content='{"intent":"PRODUCT_CONSULT"}'))
    monkeypatch.setattr(nodes,'get_intent_llm',lambda:llm)
    user='预算三千，主要玩游戏。'+('必须保留用户条件。'*100)
    assistant='手机推荐背景：'+('大量商品介绍。'*2000)+'你希望优先拍照还是游戏？'
    result=await nodes.intent_router_node({'messages':[HumanMessage(content=user),AIMessage(content=assistant),HumanMessage(content='优先考虑后者') ]})
    llm.ainvoke.assert_awaited_once()
    prompt=llm.ainvoke.call_args.args[0][-1].content
    assert user in prompt and '你希望优先拍照还是游戏？' in prompt and '优先考虑后者' in prompt
    assert len(prompt) < len(user)+1800
    assert result['intent']=='PRODUCT_CONSULT'

async def test_real_graph_classifies_then_searches_once_then_answers_without_another_planning_call(monkeypatch):
    from app.agent.graph import build_graph
    from langgraph.checkpoint.memory import MemorySaver
    from app.tools import web_search as search
    classifier=MagicMock(); classifier.ainvoke=AsyncMock(return_value=AIMessage(content='{"intent":"SMALL_TALK"}'))
    answer=MagicMock(); answer.ainvoke=AsyncMock(return_value=AIMessage(content='【联网搜索】据检索资料回答。'))
    monkeypatch.setattr(nodes,'get_intent_llm',lambda:classifier)
    monkeypatch.setattr(nodes,'get_chat_llm',lambda:answer)
    provider=AsyncMock(return_value=([{'title':'资料','snippet':'检索证据','url':'https://example.com/source'}],'searxng'))
    monkeypatch.setattr(search,'_search',provider)
    result=await build_graph(MemorySaver()).ainvoke(
        {'messages':[HumanMessage(content='最近人工智能领域有哪些新闻？')],'web_search_enabled':True,'user_id':'0','conversation_id':'0'},
        {'configurable':{'thread_id':'latency-test'}})
    classifier.ainvoke.assert_awaited_once()
    provider.assert_awaited_once()
    answer.ainvoke.assert_awaited_once()
    answer.bind_tools.assert_not_called()
    assert result['messages'][-1].content.startswith('【联网搜索】')

async def test_terminal_web_answer_preserves_the_subject_of_a_contextual_followup(monkeypatch):
    llm=MagicMock();llm.ainvoke=AsyncMock(return_value=AIMessage(content='【联网搜索】依据资料'))
    monkeypatch.setattr(nodes,'get_chat_llm',lambda:llm)
    state=web_state()
    state['messages']=[HumanMessage(content='我关注的是可控核聚变'),AIMessage(content='你想了解哪个方面？')]+state['messages']
    await nodes.web_answer_node(state)
    assert any('可控核聚变' in str(m.content) for m in llm.ainvoke.call_args.args[0])

async def test_classifier_generates_a_contextual_web_query_in_the_same_model_call(monkeypatch):
    classifier=MagicMock();classifier.ainvoke=AsyncMock(return_value=AIMessage(content='{"intent":"SMALL_TALK","web_query":"北京明天天气"}'))
    monkeypatch.setattr(nodes,'get_intent_llm',lambda:classifier)
    result=await nodes.intent_router_node({'messages':[HumanMessage(content='我明天在北京'),AIMessage(content='想了解天气吗？'),HumanMessage(content='那里会下雨吗')],'web_search_enabled':True})
    classifier.ainvoke.assert_awaited_once()
    assert result['intent']=='SMALL_TALK' and result.get('web_query')=='北京明天天气'

async def test_semantic_web_query_skips_a_separate_tool_planning_model_call(monkeypatch):
    model=MagicMock(side_effect=AssertionError('A classified web query needs no second model to select web_search'))
    monkeypatch.setattr(nodes,'get_chat_llm',model)
    result=await nodes.agent_node({'messages':[HumanMessage(content='那里会下雨吗')],'intent':'SMALL_TALK','web_search_enabled':True,'web_query':'北京明天天气','tool_loop_count':0})
    assert result['messages'][-1].tool_calls[0]['args']['query']=='北京明天天气'
    model.assert_not_called()

async def test_search_failure_is_reported_without_waiting_for_another_model_call(monkeypatch):
    model=MagicMock(side_effect=AssertionError('No model should explain a failed search'))
    monkeypatch.setattr(nodes,'get_chat_llm',model)
    state=web_state();state['messages'][-1]=ToolMessage(content='{"results":[],"error":"search unavailable"}',name='web_search',tool_call_id='web1')
    with pytest.raises(RuntimeError,match='联网搜索'):
        await nodes.web_answer_node(state)
    model.assert_not_called()

async def test_empty_search_results_are_truthful_without_another_model_call(monkeypatch):
    model=MagicMock(side_effect=AssertionError('An empty search has no evidence to synthesize'))
    monkeypatch.setattr(nodes,'get_chat_llm',model)
    state=web_state();state['messages'][-1]=ToolMessage(content='{"results":[],"total":0}',name='web_search',tool_call_id='web1')
    result=await nodes.web_answer_node(state)
    assert '未检索到' in result['messages'][0].content
    model.assert_not_called()
