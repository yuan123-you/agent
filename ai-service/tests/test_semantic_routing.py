"""Semantic business decisions must not depend on enumerating surface words."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agent import nodes
from app.api.chat import ChatRequest, build_state
from app.tools.tools import get_tool_ctx, set_tool_ctx


@pytest.fixture(autouse=True)
def context():
    set_tool_ctx({})
    yield
    set_tool_ctx({})


def planner(monkeypatch, decision):
    model=SimpleNamespace(ainvoke=AsyncMock(return_value=AIMessage(content=json.dumps(decision))))
    monkeypatch.setattr(nodes,"get_intent_llm",lambda:model)
    router=SimpleNamespace(classify=AsyncMock(return_value=None))
    monkeypatch.setattr(nodes,"get_semantic_router",lambda:router,raising=False)
    return model,router


@pytest.mark.asyncio
@pytest.mark.parametrize("question",[
    "到货后不满意怎么办", "实物和期待差了一截，能给我出个主意吗", "拿在手上总觉得不是那么回事",
    "这件穿上身总觉得别扭，咋办呀", "包裹刚拆，和我想象的有出入，该怎么弄"])
async def test_semantic_decision_clarifies_unenumerated_postpurchase_language(monkeypatch,question):
    model,_=planner(monkeypatch,{"intent":"AFTER_SALE_FAQ","next_step":"clarify","missing":"after_sale_goal"})
    state={"messages":[HumanMessage(content=question)]}
    decision=await nodes.intent_router_node(state)
    assert decision.get("request_decision",{}).get("missing")=="after_sale_goal"
    model.ainvoke.assert_awaited_once()
    monkeypatch.setattr(nodes,"get_chat_llm",lambda:pytest.fail("Controlled clarification needs no generation"))
    answer=await nodes.agent_node({**state,**decision})
    assert answer["messages"][0].content=="您是想退换货，还是商品存在质量问题？"
    assert not answer["messages"][0].tool_calls and not get_tool_ctx().get("rag_used")


@pytest.mark.asyncio
async def test_contextual_goal_is_not_overridden_by_latest_dissatisfaction_words(monkeypatch):
    model,_=planner(monkeypatch,{"intent":"ORDER_QUERY","next_step":"assist"})
    state={"messages":[HumanMessage(content="我想把昨天那件退掉"),AIMessage(content="我来核实订单。"),
                       HumanMessage(content="这东西收到以后看着就不喜欢")]}
    decision=await nodes.intent_router_node(state)
    assert decision["intent"]=="ORDER_QUERY"
    assert decision.get("request_decision",{}).get("next_step")=="assist"
    model.ainvoke.assert_awaited_once()
    prompt="\n".join(str(m.content) for m in model.ainvoke.call_args.args[0])
    assert "我想把昨天那件退掉" in prompt


@pytest.mark.asyncio
async def test_failed_semantic_understanding_asks_instead_of_keyword_guessing(monkeypatch):
    model,_=planner(monkeypatch,{})
    model.ainvoke.side_effect=RuntimeError("PRIVATE_PROVIDER_ERROR")
    state={"messages":[HumanMessage(content="这事儿该咋整")]}
    decision=await nodes.intent_router_node(state)
    assert decision.get("request_decision",{}).get("next_step")=="clarify"
    assert decision.get("request_decision",{}).get("missing")=="request"
    answer=await nodes.agent_node({**state,**decision})
    assert "PRIVATE" not in answer["messages"][0].content
    assert not answer["messages"][0].tool_calls


def test_checkpoint_assembly_explicitly_clears_previous_turn_decision():
    checkpoint=SimpleNamespace(get=lambda _: {"channel_values":{"request_decision":{
        "intent":"AFTER_SALE_FAQ","next_step":"clarify","missing":"after_sale_goal"}}})
    state=build_state(ChatRequest(user_id=1,conversation_id=1,message="退货运费由谁承担？"),checkpoint)
    assert "request_decision" in state and state["request_decision"] is None


@pytest.mark.parametrize("data",[
    {}, {"intent":"AFTER_SALE_FAQ"}, {"intent":"UNKNOWN","next_step":"assist"},
    {"intent":"AFTER_SALE_FAQ","next_step":"clarify","missing":"arbitrary policy text"},
    {"intent":"ORDER_CREATE","next_step":"retrieve"},
    {"intent":"AFTER_SALE_FAQ","next_step":"assist"},
    {"intent":"PRODUCT_CONSULT","next_step":"assist","confidence":False},
    {"intent":"PRODUCT_CONSULT","next_step":"assist","confidence":float("nan")},
    {"intent":"PRODUCT_CONSULT","next_step":"assist","confidence":.2},
])
def test_decision_schema_rejects_unknown_or_ambiguous_execution(data):
    from app.agent.request_decision import RequestDecision
    assert RequestDecision.from_model(data) is None


def vector_fixture(monkeypatch, target=("AFTER_SALE_FAQ","clarify","after_sale_goal")):
    from app.agent.request_decision import ROUTE_EXAMPLES,SemanticRouter
    keys=list(dict.fromkeys((e.intent,e.next_step,e.missing) for e in ROUTE_EXAMPLES))
    vectors={key:[float(i==keys.index(key)) for i in range(len(keys))] for key in keys}
    embedding=SimpleNamespace(
        aembed_documents=AsyncMock(return_value=[vectors[(e.intent,e.next_step,e.missing)] for e in ROUTE_EXAMPLES]),
        aembed_query=AsyncMock(return_value=vectors[target]))
    router=SemanticRouter(lambda:embedding,dimensions=len(keys),min_score=.75,min_margin=.05,timeout_s=1)
    return router,embedding,keys


@pytest.mark.asyncio
async def test_semantic_vectors_route_unseen_words_and_cache_examples_once(monkeypatch):
    router,embedding,_=vector_fixture(monkeypatch)
    for text in ("实物让我有点失落，咋整", "I received something that does not feel right"):
        decision=await router.classify(text)
        assert decision and decision.missing=="after_sale_goal" and decision.source=="embedding"
    embedding.aembed_documents.assert_awaited_once()
    assert embedding.aembed_query.await_count==2


@pytest.mark.asyncio
async def test_contextual_turn_abstains_to_dialogue_model_without_embedding_isolated_reply(monkeypatch):
    router,embedding,_=vector_fixture(monkeypatch)
    assert await router.classify("就是这个",contextual=True) is None
    embedding.aembed_documents.assert_not_awaited()
    embedding.aembed_query.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [[],[0.0],[float("nan")],[float("inf")],[True]])
async def test_invalid_embedding_vectors_abstain(monkeypatch,bad):
    router,embedding,_=vector_fixture(monkeypatch)
    embedding.aembed_query.return_value=bad
    assert await router.classify("任意语义问题") is None


@pytest.mark.asyncio
async def test_low_margin_never_pretends_a_confident_intent(monkeypatch):
    router,embedding,keys=vector_fixture(monkeypatch)
    embedding.aembed_query.return_value=[1.0]*len(keys)
    assert await router.classify("无法确定的诉求") is None


@pytest.mark.asyncio
async def test_concurrent_routes_share_one_example_embedding_job(monkeypatch):
    import asyncio
    router,embedding,_=vector_fixture(monkeypatch)
    answers=await asyncio.gather(*(router.classify(str(i)) for i in range(8)))
    assert all(answer is not None for answer in answers)
    embedding.aembed_documents.assert_awaited_once()


@pytest.mark.asyncio
async def test_embedding_provider_failure_abstains_without_exposing_error(monkeypatch,caplog):
    router,embedding,_=vector_fixture(monkeypatch)
    embedding.aembed_documents.side_effect=RuntimeError("PRIVATE_EMBEDDING_ERROR")
    assert await router.classify("问题") is None
    assert "PRIVATE_EMBEDDING_ERROR" not in caplog.text


@pytest.mark.asyncio
async def test_similarity_human_label_cannot_override_negative_authorization(monkeypatch):
    from app.agent.request_decision import RequestDecision
    model,router=planner(monkeypatch,{"intent":"AFTER_SALE_FAQ","next_step":"retrieve"})
    router.classify.return_value=RequestDecision("HUMAN_REQUEST","assist",source="embedding",score=.9,margin=.2)
    result=await nodes.intent_router_node({"messages":[HumanMessage(content="不要找人，先说明规则")]})
    assert result["intent"]=="AFTER_SALE_FAQ"
    model.ainvoke.assert_awaited_once()


@pytest.mark.parametrize("data",[
    {"intent":[],"next_step":"assist"}, {"intent":"PRODUCT_CONSULT","next_step":[]},
    {"intent":"AFTER_SALE_FAQ","next_step":"clarify","missing":{}},
])
def test_malformed_container_fields_never_raise_or_create_a_decision(data):
    from app.agent.request_decision import RequestDecision
    assert RequestDecision.from_model(data) is None


@pytest.mark.parametrize("card,intent,step,missing",[
    ("HELP","AFTER_SALE_FAQ","clarify","after_sale_goal"),
    ("RULE","AFTER_SALE_FAQ","retrieve",None), ("ORDER","ORDER_QUERY","assist",None),
    ("SHOP","PRODUCT_CONSULT","assist",None), ("MIXED","PRODUCT_CONSULT","retrieve",None),
    ("BUY","ORDER_CREATE","assist",None), ("CHAT","SMALL_TALK","assist",None),
    ("IDENTITY","ASSISTANT_META","assist",None), ("HUMAN","HUMAN_REQUEST","assist",None),
    ("UNKNOWN","SMALL_TALK","clarify","request"),
])
def test_compact_model_cards_expand_to_controlled_execution(card,intent,step,missing):
    from app.agent.request_decision import RequestDecision
    decision=RequestDecision.from_model({"route":card})
    assert decision and (decision.intent,decision.next_step,decision.missing)==(intent,step,missing)


@pytest.mark.asyncio
async def test_known_refund_goal_proceeds_to_read_only_orders_not_repeat_clarification(monkeypatch):
    model,_=planner(monkeypatch,{"route":"ORDER"})
    state={"messages":[HumanMessage(content="想把这件退回去"),AIMessage(content="您是想退换货，还是商品存在质量问题？"),
                       HumanMessage(content="我已经说了，就是不想要它了，把款退给我")],"tool_loop_count":0}
    decision=await nodes.intent_router_node(state)
    monkeypatch.setattr(nodes,"get_chat_llm",lambda:pytest.fail("Real order evidence must precede generation"))
    answer=await nodes.agent_node({**state,**decision})
    assert [call["name"] for call in answer["messages"][0].tool_calls]==["order_query"]
    model.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_conditional_human_mention_is_not_an_explicit_transfer_command(monkeypatch):
    from app.agent.request_decision import RequestDecision
    model,router=planner(monkeypatch,{"route":"CHAT"})
    router.classify.return_value=RequestDecision("HUMAN_REQUEST","assist",source="embedding",score=.99,margin=.3)
    result=await nodes.intent_router_node({"messages":[HumanMessage(content="如果以后我要找人工，会另行告诉你") ]})
    assert result["intent"]=="SMALL_TALK" and result["reply_route"]!="escalate_node"
    model.ainvoke.assert_awaited_once()






@pytest.mark.asyncio
async def test_purchase_selection_guard_preserves_a_valid_clarification(monkeypatch):
    planner(monkeypatch,{"intent":"ORDER_CREATE","next_step":"clarify","missing":"product"})
    state={"messages":[HumanMessage(content="帮我下单一部手机")],"active_entities":{}}
    decision=await nodes.intent_router_node(state)
    assert decision["request_decision"]["next_step"]=="clarify"
    assert decision["request_decision"]["missing"]=="product"
    monkeypatch.setattr(nodes,"get_chat_llm",lambda:pytest.fail("No shopping tools before clarification"))
    result=await nodes.agent_node({**state,**decision})
    assert result["messages"][0].content=="您咨询的是哪款商品？"
    assert not result["messages"][0].tool_calls


@pytest.mark.asyncio
async def test_example_cache_initialization_does_not_capture_request_identity(monkeypatch):
    router,embedding,keys=vector_fixture(monkeypatch)
    vectors=embedding.aembed_documents.return_value
    async def load(_):
        assert get_tool_ctx().get("user_id") is None
        return vectors
    embedding.aembed_documents.side_effect=load
    set_tool_ctx({"user_id":"private-request-user"})
    assert await router.classify("一个商品问题") is not None
    assert get_tool_ctx()["user_id"]=="private-request-user"


@pytest.mark.parametrize("text",[
    "如果以后我要找人工，会另行告诉你", "假如我说转人工，你会怎样处理", "例如用户写我要找真人，系统应该怎么办",
    "我可能会找人工，现在先不用", "除非之后我明确要求，否则不要转人工",
])
def test_hypothetical_or_quoted_transfer_is_not_authorization(text):
    from app.request_policy import requests_human
    assert requests_human(text) is False


def test_direct_transfer_after_feasibility_clause_remains_authorized():
    from app.request_policy import requests_human
    assert requests_human("如果可以，请帮我转人工") is True


@pytest.mark.parametrize("text",['“转人工”这三个字是什么含义', '例子里写"我要找人工"，是什么意思', "假设消息是'转人工'，应该路由到哪里"])
def test_quoted_command_does_not_authorize_a_real_transfer(text):
    from app.request_policy import requests_human
    assert not requests_human(text)


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy",[False,True])
async def test_intent_factory_budget_reaches_the_actual_sdk_wire(monkeypatch,legacy):
    import httpx
    from langchain_openai import ChatOpenAI
    from app.clients import llm
    seen=[]
    def handle(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200,json={"id":"qa","object":"chat.completion","created":0,"model":"unit-model",
            "choices":[{"index":0,"message":{"role":"assistant","content":'{"route":"RULE"}'},"finish_reason":"stop"}]})
    config={**llm.settings.model_dump(),"llm_api_base":"http://ollama.test/v1","llm_api_key":"unit-only",
            "llm_intent_model":"unit-model","llm_intent_max_tokens":128,"llm_legacy_max_tokens":legacy}
    monkeypatch.setattr(llm,"settings",SimpleNamespace(**config))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        monkeypatch.setattr(llm,"ChatOpenAI",lambda **kwargs:ChatOpenAI(**kwargs,http_async_client=client,http_socket_options=()))
        result=await llm.get_intent_llm().ainvoke([HumanMessage(content="a policy question")])
    assert json.loads(result.content)["route"]=="RULE"
    assert seen[0]["max_completion_tokens"]==128
    assert seen[0].get("max_tokens")==128 if legacy else "max_tokens" not in seen[0]


@pytest.mark.asyncio
async def test_embedding_query_timeout_abstains_and_cancels_only_the_query(monkeypatch):
    import asyncio
    router,embedding,_=vector_fixture(monkeypatch)
    router.timeout_s=.02
    cancelled=[]
    async def wait(_):
        try:await asyncio.sleep(1)
        finally:cancelled.append(True)
    embedding.aembed_query.side_effect=wait
    assert await router.classify("one query") is None
    assert cancelled==[True]
    embedding.aembed_documents.assert_awaited_once()


@pytest.mark.asyncio
async def test_request_cancellation_is_not_swallowed_as_semantic_abstention(monkeypatch):
    import asyncio
    router,embedding,_=vector_fixture(monkeypatch)
    embedding.aembed_query.side_effect=asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):await router.classify("one query")


@pytest.mark.asyncio
async def test_unseen_assistant_criticism_is_not_sent_to_web_when_enabled(monkeypatch):
    planner(monkeypatch,{"route":"CHAT"})
    result=await nodes.intent_router_node({"messages":[HumanMessage(content="你说得前后对不上呀")],"web_search_enabled":True})
    assert result["reply_route"]=="small_talk" and result["web_query"] is None


@pytest.mark.asyncio
async def test_semantic_external_query_reuses_resolved_web_search_without_second_guess(monkeypatch):
    planner(monkeypatch,{"route":"WEB","web_query":"北京明天天气"})
    result=await nodes.intent_router_node({"messages":[HumanMessage(content="明天在北京"),AIMessage(content="您想了解天气吗？"),
        HumanMessage(content="会不会下雨")],"web_search_enabled":True})
    assert result["reply_route"]=="agent" and result["web_query"]=="北京明天天气"


@pytest.mark.asyncio
async def test_semantic_web_card_never_enables_disabled_capability(monkeypatch):
    planner(monkeypatch,{"route":"WEB","web_query":"外部信息"})
    result=await nodes.intent_router_node({"messages":[HumanMessage(content="帮我看看外面的消息")],"web_search_enabled":False})
    assert result["web_query"] is None and result["reply_route"]=="small_talk"
    assert "web_search" not in {t.name for t in nodes.get_tools_for_intent(result["intent"],False)}


@pytest.mark.asyncio
async def test_long_request_is_not_decided_from_a_truncated_embedding(monkeypatch):
    router,embedding,_=vector_fixture(monkeypatch)
    assert await router.classify("完整需求不能裁掉"*100) is None
    embedding.aembed_documents.assert_not_awaited()
    embedding.aembed_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_continuation_reuses_validated_business_focus_without_reasking_goal(monkeypatch):
    planner(monkeypatch,{"route":"CONTINUE"})
    focus={"intent":"ORDER_QUERY","next_step":"assist","topic":"我想退还昨天买的鞋"}
    state={"messages":[HumanMessage(content="我想退还昨天买的鞋"),AIMessage(content="我来协助处理。"),
        HumanMessage(content="就是试了下感觉不合脚")],"conversation_focus":focus}
    result=await nodes.intent_router_node(state)
    assert result["intent"]=="ORDER_QUERY" and result["request_decision"]["next_step"]=="assist"
    assert result["conversation_focus"]["topic"]==focus["topic"]


@pytest.mark.asyncio
@pytest.mark.parametrize("intent",["HUMAN_REQUEST","ORDER_CREATE"])
async def test_continuation_cannot_inherit_sensitive_action_authorization(monkeypatch,intent):
    planner(monkeypatch,{"route":"CONTINUE"})
    result=await nodes.intent_router_node({"messages":[HumanMessage(content="继续")],
        "conversation_focus":{"intent":intent,"next_step":"assist","topic":"previous action"}})
    assert result["request_decision"]["next_step"]=="clarify" and result["request_decision"]["missing"]=="request"
    assert result["reply_route"]!="escalate_node"


@pytest.mark.asyncio
async def test_resolved_contextual_policy_query_reaches_lookup_without_losing_scope(monkeypatch):
    planner(monkeypatch,{"route":"RULE","kb_query":"平台退货运费的承担规则"})
    state={"messages":[HumanMessage(content="退货运费谁负责"),AIMessage(content="要根据原因核实。"),
        HumanMessage(content="那商家会承担吗")],"tool_loop_count":0}
    result=await nodes.intent_router_node(state)
    assert result["knowledge_query"]=="平台退货运费的承担规则"
    answer=await nodes.agent_node({**state,**result})
    call=answer["messages"][0].tool_calls[0]
    assert call["name"]=="kb_search" and call["args"]["query"]==result["knowledge_query"]
    assert call["args"]["product_id"]==-1


@pytest.mark.asyncio
async def test_policy_question_during_order_handling_keeps_the_business_focus(monkeypatch):
    planner(monkeypatch,{"route":"RULE","kb_query":"退货运费由谁承担"})
    focus={"intent":"ORDER_QUERY","next_step":"assist","topic":"申请退还商品"}
    result=await nodes.intent_router_node({"messages":[HumanMessage(content="谁付退回的运费")],"conversation_focus":focus})
    assert result["request_decision"]["next_step"]=="retrieve"
    assert result["conversation_focus"]["intent"]=="ORDER_QUERY"


def test_focus_persists_but_decision_and_resolved_query_reset_each_turn():
    focus={"intent":"ORDER_QUERY","next_step":"assist","topic":"申请退货"}
    cp=SimpleNamespace(get=lambda _: {"channel_values":{"conversation_focus":focus,"knowledge_query":"stale", "request_decision":{"next_step":"retrieve"}}})
    state=build_state(ChatRequest(user_id=1,conversation_id=1,message="继续处理"),cp)
    assert state["conversation_focus"]==focus
    assert state["knowledge_query"] is None and state["request_decision"] is None


@pytest.mark.asyncio
async def test_conversational_aside_does_not_drop_a_valid_business_focus(monkeypatch):
    planner(monkeypatch,{"route":"CHAT"})
    focus={"intent":"ORDER_QUERY","next_step":"assist","topic":"申请退货"}
    result=await nodes.intent_router_node({"messages":[HumanMessage(content="先谢谢你刚才帮忙了")],"conversation_focus":focus})
    assert result["reply_route"]=="small_talk"
    assert result["conversation_focus"]==focus


@pytest.mark.asyncio
async def test_query_rewrite_cannot_change_the_committed_decision(monkeypatch):
    model,_=planner(monkeypatch,{})
    model.ainvoke.side_effect=[AIMessage(content='{"route":"RULE"}'),AIMessage(content='{"route":"BUY"}')]
    focus={"intent":"AFTER_SALE_FAQ","next_step":"retrieve","topic":"退货运费承担规则"}
    result=await nodes.intent_router_node({"messages":[HumanMessage(content="退货运费谁承担"),AIMessage(content="要核实原因。"),HumanMessage(content="那商家会出吗")],"conversation_focus":focus})
    assert result["request_decision"]["next_step"]=="retrieve"
    assert result["knowledge_query"] and "退货运费" in result["knowledge_query"]
    assert model.ainvoke.await_count==2


@pytest.mark.asyncio
@pytest.mark.parametrize("confidence",[.1,False,[]])
async def test_continue_never_bypasses_rejected_planner_confidence(monkeypatch,confidence):
    planner(monkeypatch,{"route":"CONTINUE","confidence":confidence})
    result=await nodes.intent_router_node({"messages":[HumanMessage(content="继续")],
        "conversation_focus":{"intent":"ORDER_QUERY","next_step":"assist","topic":"办理退货"}})
    assert result["request_decision"]["next_step"]=="clarify"
    assert result["request_decision"]["missing"]=="request"
    answer=await nodes.agent_node({"messages":[HumanMessage(content="继续")],**result})
    assert not answer["messages"][0].tool_calls


def test_regeneration_does_not_reuse_focus_from_the_failed_turn():
    cp=SimpleNamespace(get=lambda _: {"channel_values":{"conversation_focus":{
        "intent":"ORDER_QUERY","next_step":"assist","topic":"wrong failed-turn interpretation"}}})
    state=build_state(ChatRequest(user_id=1,conversation_id=1,message="original message",options={"regenerate":True}),cp)
    assert state["conversation_focus"] is None
