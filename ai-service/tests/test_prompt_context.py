import json
from unittest.mock import AsyncMock,MagicMock
import pytest
from langchain_core.messages import AIMessage,HumanMessage,ToolMessage
from app.agent import nodes
from app.tools.tools import set_tool_ctx

URL='https://example.com/article?tracking='+('very-long-tracking-'*60)
FACT='关键事实必须完整保留。'+('细节证据。'*100)

def web_state():
    return {'intent':'SMALL_TALK','web_search_enabled':True,'messages':[
      HumanMessage(content='解释一下这项技术'),
      AIMessage(content='',tool_calls=[{'name':'web_search','args':{'query':'技术细节'},'id':'web1'}]),
      ToolMessage(name='web_search',tool_call_id='web1',content=json.dumps({'results':[{'title':'真实来源','snippet':FACT,'url':URL}]},ensure_ascii=False)),
    ]}

@pytest.fixture(autouse=True)
def context():
    set_tool_ctx({});yield;set_tool_ctx({})

async def test_web_model_receives_all_facts_without_raw_urls_or_tool_protocol(monkeypatch):
    model=MagicMock();model.ainvoke=AsyncMock(return_value=AIMessage(content='这是基于资料的完整回答。'))
    monkeypatch.setattr(nodes,'get_chat_llm',lambda:model)
    state=web_state();original=state['messages'][-1].content
    result=await nodes.web_answer_node(state)
    supplied=model.ainvoke.call_args.args[0]
    text='\n'.join(str(m.content) for m in supplied)
    assert URL not in text
    assert FACT in text and '真实来源' in text
    assert not any(getattr(m,'type','')=='tool' or getattr(m,'tool_calls',None) for m in supplied)
    assert state['messages'][-1].content==original
    assert URL in result['messages'][0].content
    assert result['messages'][0].content.count(URL)==1
    assert result['messages'][0].additional_kwargs.get('web_source_footer')

async def test_invalid_source_schemes_never_become_program_owned_links(monkeypatch):
    model=MagicMock();model.ainvoke=AsyncMock(return_value=AIMessage(content='基于资料回答。'))
    monkeypatch.setattr(nodes,'get_chat_llm',lambda:model)
    state=web_state();state['messages'][-1].content=json.dumps({'results':[{'title':'数据','snippet':'事实','url':'javascript:alert(1)'},{'title':'另一条','snippet':'事实2','url':'https://user:password@example.com/private'}]})
    result=await nodes.web_answer_node(state)
    assert 'javascript:' not in result['messages'][0].content
    assert 'password@' not in result['messages'][0].content

async def test_product_model_omits_image_transport_fields_but_keeps_all_product_facts(monkeypatch):
    model=MagicMock();model.bind_tools.return_value=model;model.ainvoke=AsyncMock(return_value=AIMessage(content='推荐真实商品。'))
    monkeypatch.setattr(nodes,'get_chat_llm',lambda:model)
    payload={'products':[{'id':7,'name':'真实手机','price':2999,'stock':12,'sellingPoints':FACT,'specs':{'memory':'12GB'},'link':'mall://product/7','imageUrl':URL,'imageSha256':'f'*64,'sourceName':'采集来源'}]}
    tool=ToolMessage(name='product_search',tool_call_id='product1',content=json.dumps(payload,ensure_ascii=False))
    state={'intent':'PRODUCT_CONSULT','messages':[HumanMessage(content='推荐一款3000内的手机'),AIMessage(content='',tool_calls=[{'id':'product1','name':'product_search','args':{'category':'PHONE'}}]),tool],'tool_loop_count':1,'web_search_enabled':False}
    await nodes.agent_node(state)
    supplied=model.ainvoke.call_args.args[0]
    projected=next(m for m in supplied if getattr(m,'type','')=='tool')
    data=json.loads(projected.content)['products'][0]
    assert 'imageUrl' not in data and 'imageSha256' not in data
    assert all(data[key]==payload['products'][0][key] for key in ['id','name','price','stock','sellingPoints','specs','link','sourceName'])
    assert json.loads(tool.content)==payload
    assert projected.tool_call_id=='product1'
    assert len(supplied[0].content)<1800
    assert '[Sx]' in supplied[0].content and '确认卡片' in supplied[0].content

def test_prompt_projection_preserves_human_and_non_text_messages_and_other_tool_protocol():
    from app.agent.prompt_context import compact_prompt_messages
    human=HumanMessage(content='请解释这个原始地址 '+URL)
    block=AIMessage(content=[{'type':'text','text':'保留结构化内容'}])
    policy=ToolMessage(name='kb_search',tool_call_id='kb1',content='{"context":"[S1] 条款", "imageUrl":"属于证据原文"}')
    result=compact_prompt_messages([human,block,policy])
    assert result[0] is human and result[1] is block and result[2] is policy


def test_prior_source_titles_survive_without_reinjecting_their_long_urls():
    from app.agent.prompt_context import compact_prompt_messages
    previous=AIMessage(content='之前的完整结论。\n\n参考来源：\n[1. 前文来源]('+URL+')')
    result=compact_prompt_messages([previous])[0]
    assert URL not in result.content
    assert '之前的完整结论' in result.content and '前文来源' in result.content
    assert URL in previous.content

def test_overlapping_search_results_keep_every_fact_but_share_one_source_link():
    from app.agent.prompt_context import web_prompt_evidence
    facts,footer=web_prompt_evidence([
        {'results':[{'title':'同一来源','snippet':'第一个事实','url':'https://example.com/same'}]},
        {'results':[{'title':'同一来源另一标题','snippet':'第二个事实','url':'https://example.com/same'},{'title':'其他来源','snippet':'第三个事实','url':'https://example.com/other'}]},
    ])
    assert all(value in facts for value in ['第一个事实','第二个事实','第三个事实','同一来源另一标题'])
    assert footer.count('https://example.com/same')==1
    assert '[1] 同一来源' in facts and '[1] 同一来源另一标题' in facts
    assert '[2] 其他来源' in facts and '[2. 其他来源]' in footer

async def test_pure_product_planning_keeps_both_product_lookups_without_irrelevant_tools(monkeypatch):
    model=MagicMock();model.bind_tools.return_value=model;model.ainvoke=AsyncMock(return_value=AIMessage(content='根据真实商品说明。'))
    monkeypatch.setattr(nodes,'get_chat_llm',lambda:model)
    state={'intent':'PRODUCT_CONSULT','web_search_enabled':False,'tool_loop_count':1,'messages':[HumanMessage(content='这款手机的参数呢')],'active_entities':{'last_category':'PHONE','last_products':[{'id':7,'name':'真实手机'}]}}
    await nodes.agent_node(state)
    assert [tool.name for tool in model.bind_tools.call_args.args[0]]==['product_search','product_detail']

async def test_product_followup_keeps_policy_search_when_the_recent_topic_needs_it(monkeypatch):
    model=MagicMock();model.bind_tools.return_value=model;model.ainvoke=AsyncMock(return_value=AIMessage(content='依据资料说明。'))
    monkeypatch.setattr(nodes,'get_chat_llm',lambda:model)
    state={'intent':'PRODUCT_CONSULT','web_search_enabled':False,'tool_loop_count':1,'messages':[HumanMessage(content='手机保修多久'),AIMessage(content='正在核对政策'),HumanMessage(content='这款参数呢')],'active_entities':{'last_category':'PHONE','last_products':[{'id':7,'name':'真实手机'}]}}
    await nodes.agent_node(state)
    assert 'kb_search' in [tool.name for tool in model.bind_tools.call_args.args[0]]

@pytest.mark.parametrize("question", ["这张图片的来源链接和SHA256是什么？", "请给出这款商品的imageUrl字段"])
def test_explicit_image_link_or_hash_requests_keep_the_requested_evidence_fields(question):
    from app.agent.prompt_context import compact_prompt_messages
    user=HumanMessage(content=question)
    payload={'productId':7,'price':2999,'imageUrl':URL,'imageSha256':'f'*64}
    tool=ToolMessage(name='product_detail',tool_call_id='p7',content=json.dumps(payload))
    result=compact_prompt_messages([user,tool])
    assert json.loads(result[-1].content)==payload


def test_source_domains_remain_in_model_evidence_without_long_url_transport():
    from app.agent.prompt_context import web_prompt_evidence
    facts,footer=web_prompt_evidence([{'results':[{'title':'资料','snippet':FACT,'url':URL}]}])
    assert 'example.com' in facts and FACT in facts and URL not in facts
    assert URL in footer


async def test_explicit_source_link_questions_keep_the_requested_address_available(monkeypatch):
    model=MagicMock();model.ainvoke=AsyncMock(return_value=AIMessage(content='地址说明。'))
    monkeypatch.setattr(nodes,'get_chat_llm',lambda:model)
    state=web_state();state['messages'][0]=HumanMessage(content='解释这条来源链接的结构')
    await nodes.web_answer_node(state)
    assert URL in '\n'.join(str(m.content) for m in model.ainvoke.call_args.args[0])

async def test_product_followup_keeps_policy_tool_when_recent_evidence_is_policy_related(monkeypatch):
    model=MagicMock();model.bind_tools.return_value=model;model.ainvoke=AsyncMock(return_value=AIMessage(content='结合先前资料说明。'))
    monkeypatch.setattr(nodes,'get_chat_llm',lambda:model)
    state={'intent':'PRODUCT_CONSULT','web_search_enabled':False,'tool_loop_count':1,'messages':[
        HumanMessage(content='先了解一下会员权益'),
        AIMessage(content='',tool_calls=[{'name':'kb_search','id':'kb1','args':{'query':'会员权益'}}]),
        ToolMessage(name='kb_search',tool_call_id='kb1',content='{"context":"条款[S1]"}'),
        AIMessage(content='已有相关资料'),HumanMessage(content='再看一下'),AIMessage(content='可以'),
        HumanMessage(content='比较一下'),AIMessage(content='可以'),HumanMessage(content='这款参数呢')],
        'active_entities':{'last_category':'PHONE','last_products':[{'id':7,'name':'真实手机'}]}}
    await nodes.agent_node(state)
    assert 'kb_search' in [tool.name for tool in model.bind_tools.call_args.args[0]]
