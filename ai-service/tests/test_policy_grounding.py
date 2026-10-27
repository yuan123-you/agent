"""Real-release regression: a model may ignore knowledge tools or misclassify policy requests."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from app.agent import nodes
from app.api import chat
from app import request_policy
from app.tools.tools import set_tool_ctx

QUESTION='平台无理由退货规则是什么？'

@pytest.fixture(autouse=True)
def isolated_context():
    set_tool_ctx({})
    yield
    set_tool_ctx({})

@pytest.mark.parametrize('text,expected',[(QUESTION,True),('保修多久？',True),('退货运费谁承担',True),
    ('怎么申请退款',True),('发票的开具规则',True),('帮我申请退款',False),('取消我的订单',False),
    ('你好',False),('推荐手机',False),('请转人工客服，售后规则我想问真人',False)])
def test_explicit_policy_question_requires_grounding(text,expected):
    assert request_policy.requires_kb(text) is expected

@pytest.mark.asyncio
async def test_small_talk_classifier_cannot_bypass_explicit_policy_retrieval(monkeypatch):
    monkeypatch.setattr(nodes,'get_intent_llm',lambda:SimpleNamespace(ainvoke=AsyncMock(return_value=AIMessage(content='{"intent":"SMALL_TALK"}'))))
    result=await nodes.intent_router_node({'messages':[HumanMessage(content=QUESTION)]})
    assert result['intent']=='AFTER_SALE_FAQ'

@pytest.mark.asyncio
async def test_policy_agent_schedules_real_lookup_before_a_tool_ignoring_model(monkeypatch):
    model=SimpleNamespace(ainvoke=AsyncMock(return_value=AIMessage(content='可14天内退货')))
    model.bind_tools=lambda *a,**k:model
    monkeypatch.setattr(nodes,'get_chat_llm',lambda:model)
    result=await nodes.agent_node({'intent':'AFTER_SALE_FAQ','messages':[HumanMessage(content=QUESTION)],'tool_loop_count':0})
    assert result['messages'][0].tool_calls[0]['name']=='kb_search'
    assert result['messages'][0].tool_calls[0]['args']['query']==QUESTION
    model.ainvoke.assert_not_awaited()

@pytest.mark.asyncio
async def test_policy_lookup_is_not_rescheduled_after_tool_result(monkeypatch):
    model=SimpleNamespace(ainvoke=AsyncMock(return_value=AIMessage(content='依据资料。[S1]')))
    model.bind_tools=lambda *a,**k:model
    monkeypatch.setattr(nodes,'get_chat_llm',lambda:model)
    result=await nodes.agent_node({'intent':'AFTER_SALE_FAQ','messages':[HumanMessage(content=QUESTION),
        AIMessage(content='',tool_calls=[{'name':'kb_search','args':{'query':QUESTION},'id':'k1'}]),
        ToolMessage(content='verified source',name='kb_search',tool_call_id='k1')], 'tool_loop_count':1})
    assert result['messages'][0].content=='依据资料。[S1]'

@pytest.mark.asyncio
@pytest.mark.parametrize('node',['agent','small_talk','finalize_without_tools'])
async def test_policy_stream_never_leaks_unsourced_claim_even_if_graph_skips_kb(monkeypatch,node):
    class Graph:
        async def astream_events(self,*a,**k):
            yield {'event':'on_chat_model_stream','metadata':{'langgraph_node':node},'data':{'chunk':AIMessageChunk(content='UNVERIFIED 可14天内退货')}}
            yield {'event':'on_chain_end','name':'LangGraph','data':{'output':{}}}
    class Request:
        async def is_disconnected(self):return False
    monkeypatch.setattr(chat,'graph',Graph())
    monkeypatch.setattr(chat,'checkpointer',None)
    monkeypatch.setattr(chat,'start_trace',lambda **k:False)
    monkeypatch.setattr(chat,'end_trace',lambda **k:None)
    monkeypatch.setattr(chat,'background_memory_extraction',AsyncMock())
    response=await chat.chat_stream(chat.ChatRequest(user_id=1,conversation_id=1,message=QUESTION),Request())
    events=[]
    async for raw in response.body_iterator:
        if isinstance(raw,bytes):raw=raw.decode()
        lines=raw.strip().splitlines();events.append((lines[0][7:],json.loads(lines[1][6:])))
    rendered=''.join(data['content'] for event,data in events if event=='token')
    done=next(data for event,data in events if event=='done')
    assert 'UNVERIFIED' not in rendered and '14天' not in rendered
    assert done['content']=='当前知识库证据不足，暂时无法可靠回答该问题。'
    assert done['citations']==[]

@pytest.mark.asyncio
async def test_mixed_shopping_and_policy_schedules_both_grounding_tools(monkeypatch):
    model=SimpleNamespace(ainvoke=AsyncMock(return_value=AIMessage(content='unverified')))
    model.bind_tools=lambda *a,**k:model
    monkeypatch.setattr(nodes,'get_chat_llm',lambda:model)
    result=await nodes.agent_node({'intent':'PRODUCT_CONSULT','messages':[HumanMessage(content='推荐手机，支持七天退货吗')],'tool_loop_count':0})
    assert {x['name'] for x in result['messages'][0].tool_calls}=={'product_search','kb_search'}
