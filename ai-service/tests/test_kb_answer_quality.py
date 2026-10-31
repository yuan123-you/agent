"""Regression for customer-facing knowledge dumps and safe bounded synthesis."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from app.agent import nodes
from app.agent.output import OutputPolicy
from app.agent.routing import RequestPolicy
from app.agent.request_decision import RequestDecision
from app.tools.tools import get_tool_ctx, set_tool_ctx

QUESTION = "平台无理由退货规则是什么？"
SOURCE = "# AI Mall 平台服务规则知识库\n## 退换货\n签收之日起7自然日内，商品完好可申请无理由退货；定制商品不适用。"
ANSWER = "商品完好时，可在签收之日起7自然日内申请无理由退货；定制商品不适用。[S1]"
ALLOWED = {"S1": {"id": "S1", "chunk_id": 7, "title": "平台规则"}}

@pytest.fixture(autouse=True)
def isolated_context():
    set_tool_ctx({})
    yield
    set_tool_ctx({})

def setup(monkeypatch, *, mode="generate", payload=None):
    monkeypatch.setattr(nodes, "settings", SimpleNamespace(**{**nodes.settings.model_dump(),
        "kb_response_mode": mode, "kb_answer_timeout_s": .02,
        "kb_answer_max_tokens": 512, "kb_context_max_chars": 3600}))
    model = SimpleNamespace(ainvoke=AsyncMock(return_value=AIMessage(content=ANSWER)))
    model.bind_tools = lambda *_: pytest.fail("Synthesis must not bind tools")
    monkeypatch.setattr(nodes, "get_chat_llm", lambda: model)
    get_tool_ctx().update(rag_used=True, rag_answerable=True, rag_reason="high_confidence",
        rag_allowed_citations=ALLOWED.copy(), rag_source_contents={"S1": SOURCE})
    if payload is None:
        payload = {"answerable": True, "citations": list(ALLOWED.values()),
            "hits": [{"chunk_id": 7, "content": SOURCE}], "context": "DO_NOT_DUPLICATE_CONTEXT"}
    state = {"intent": "AFTER_SALE_FAQ", "tool_loop_count": 1, "messages": [HumanMessage(content=QUESTION),
        ToolMessage(name="kb_search", tool_call_id="kb", content=json.dumps(payload))]}
    return model, state

@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["generate", "extractive"])
async def test_current_and_legacy_modes_synthesize_not_dump(monkeypatch, mode):
    model, state = setup(monkeypatch, mode=mode)
    result = await nodes.agent_node(state)
    assert result["messages"][0].content == ANSWER
    model.ainvoke.assert_awaited_once()
    prompt = "\n".join(str(m.content) for m in model.ainvoke.call_args.args[0])
    assert "定制商品不适用" in prompt
    assert "DO_NOT_DUPLICATE_CONTEXT" not in prompt and "sources" in prompt and "JSON" in prompt
    assert model.ainvoke.call_args.kwargs["max_tokens"] == 512

@pytest.mark.asyncio
async def test_only_approved_sources_enter_prompt(monkeypatch):
    payload = {"answerable": True, "citations": [*ALLOWED.values(), {"id": "S9", "chunk_id": 9}],
        "hits": [{"chunk_id": 7, "content": SOURCE}, {"chunk_id": 9, "content": "FORGED_EVIDENCE"}],
        "context": "FORGED_CONTEXT"}
    model, state = setup(monkeypatch, payload=payload)
    await nodes.agent_node(state)
    prompt = "\n".join(str(m.content) for m in model.ainvoke.call_args.args[0])
    assert "FORGED" not in prompt and "定制商品不适用" in prompt

@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"answerable": False, "reason": "insufficient_evidence"},
    {"answerable": True, "citations": [{"id": "S9", "chunk_id": 7}], "hits": [{"chunk_id": 7, "content": SOURCE}]},
    {"answerable": True, "citations": [{"id": "S1", "chunk_id": 8}], "hits": [{"chunk_id": 8, "content": SOURCE}]},
    {"answerable": True, "citations": list(ALLOWED.values()), "hits": [{"chunk_id": 7, "content": "x" * 4000}]}, []])
async def test_bad_evidence_does_not_call_model(monkeypatch, payload):
    model, state = setup(monkeypatch, payload=payload)
    result = await nodes.agent_node(state)
    assert SOURCE not in result["messages"][0].content
    model.ainvoke.assert_not_awaited()

@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "exception", "empty", "uncited", "forged", "dump", "cutoff"])
async def test_failed_synthesis_never_falls_back_to_raw_text(monkeypatch, failure):
    model, state = setup(monkeypatch)
    if failure == "timeout":
        async def slow(*a, **k):
            await asyncio.sleep(1)
        model.ainvoke.side_effect = slow
    elif failure == "exception":
        model.ainvoke.side_effect = RuntimeError("PRIVATE_PROVIDER_ERROR")
    else:
        text = {"empty": "", "uncited": "可以无条件退货。", "forged": "可以退货。[S9]",
                "dump": SOURCE + "\n[S1]", "cutoff": ANSWER}[failure]
        model.ainvoke.return_value = AIMessage(content=text,
            response_metadata={"finish_reason": "length"} if failure == "cutoff" else {})
    result = await nodes.agent_node(state)
    final = OutputPolicy(QUESTION).finalize(result["messages"][0].content, get_tool_ctx())
    assert "暂时" in final.content or "超时" in final.content
    assert "原文" not in final.content and "PRIVATE" not in final.content and "无条件" not in final.content
    assert SOURCE not in final.content and final.citations == ()
    assert get_tool_ctx()["rag_reason"].startswith("generation_")

def test_shared_boundary_rejects_dump_with_valid_citation():
    source = SOURCE + "\n" + "适用范围及详细条款。" * 35
    ctx = {"rag_used": True, "rag_answerable": True, "rag_allowed_citations": ALLOWED,
           "rag_source_contents": {"S1": source}}
    answer = OutputPolicy(QUESTION).finalize(source + "\n[S1]", ctx)
    assert source not in answer.content and answer.citations == ()

@pytest.mark.asyncio
@pytest.mark.parametrize("question", ["商品购买后不满意怎么办", "买到的东西不合适怎么办", "收到商品不喜欢怎么办",
    "到货后不满意怎么办", "货到了不满意怎么办", "签收后不满意怎么办", "拿到手不满意怎么办"])
async def test_vague_dissatisfaction_asks_one_safe_question(monkeypatch, question):
    assert RequestPolicy(question).fast_intent() is None
    semantic = RequestDecision("AFTER_SALE_FAQ", "clarify", "after_sale_goal", source="embedding")
    monkeypatch.setattr(nodes, "get_semantic_router", lambda: SimpleNamespace(classify=AsyncMock(return_value=semantic)))
    monkeypatch.setattr(nodes, "get_chat_llm", lambda: pytest.fail("Clarification needs no generation"))
    state = {"messages": [HumanMessage(content=question)]}
    decision = await nodes.intent_router_node(state)
    result = await nodes.agent_node({**state, **decision})
    message = result["messages"][0]
    assert not message.tool_calls and "退换货" in message.content and "质量" in message.content
    assert message.content.count("？") == 1 and "投诉" not in message.content
    assert OutputPolicy(question).finalize(message.content, get_tool_ctx()).content == message.content

def test_production_cannot_reenable_raw_mode():
    compose = (Path(__file__).resolve().parents[2] / "deploy/compose.production.yml").read_text(encoding="utf-8")
    assert "KB_RESPONSE_MODE: extractive" not in compose
    assert "KB_ANSWER_TIMEOUT_S:" in compose

@pytest.mark.asyncio
async def test_cancellation_is_not_swallowed_as_provider_failure(monkeypatch):
    model, state = setup(monkeypatch)
    model.ainvoke.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await nodes.agent_node(state)

@pytest.mark.parametrize("question", [
    "商品不满意，想退货怎么办", "收到商品不满意，有质量问题", "买的东西不合适，我要换货",
    "购买前不喜欢这个商品", "商品不满意，请转人工", "不满意你的回复", "帮我推荐不合适就能退的衣服",
    "到货后不满意想退货", "到货后不满意，请转人工", "还没买，到货后不满意能不能退"])
def test_clarification_is_no_longer_selected_from_words(question):
    # Business-word patterns cannot supersede the semantic decision contract.
    assert RequestPolicy(question).fast_intent() in {None, "HUMAN_REQUEST"}

@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["answer", "dump", "timeout", "clarification", "clarification-arrival"])
async def test_real_graph_sse_only_publishes_safe_final_answer(monkeypatch, kind):
    from langgraph.checkpoint.memory import MemorySaver
    from app.agent.graph import build_graph
    from app.api import chat
    from app.rag import retrieval
    model, _ = setup(monkeypatch)
    if kind == "dump":
        model.ainvoke.return_value = AIMessage(content=SOURCE + "\n[S1]")
    if kind == "timeout":
        async def slow(*a, **k):
            await asyncio.sleep(1)
        model.ainvoke.side_effect = slow
    hit = retrieval.RetrievalCandidate(7, 1, None, "POLICY", SOURCE, "平台规则", vector_score=.95)
    sources = retrieval.build_source_context([hit])
    result = retrieval.RetrievalResult(True, "high_confidence", (hit,), sources.context, sources.citations, False, ())
    search = AsyncMock(return_value=result)
    monkeypatch.setattr(retrieval, "get_retrieval_pipeline", lambda: SimpleNamespace(search=search))
    monkeypatch.setattr(chat, "graph", build_graph(MemorySaver()))
    monkeypatch.setattr(chat, "checkpointer", None)
    monkeypatch.setattr(chat, "start_trace", lambda **k: False)
    monkeypatch.setattr(chat, "end_trace", lambda **k: None)
    monkeypatch.setattr(chat, "background_memory_extraction", AsyncMock())
    semantic = RequestDecision("AFTER_SALE_FAQ", "clarify", "after_sale_goal", source="embedding") if kind.startswith("clarification") else RequestDecision("AFTER_SALE_FAQ", "retrieve", source="embedding")
    monkeypatch.setattr(nodes, "get_semantic_router", lambda: SimpleNamespace(classify=AsyncMock(return_value=semantic)))
    monkeypatch.setattr(nodes, "get_intent_llm", lambda: pytest.fail("Confident semantic route needs no fallback"))
    class Request:
        async def is_disconnected(self):
            return False
    question = "到货后不满意怎么办" if kind == "clarification-arrival" else ("商品购买后不满意怎么办" if kind == "clarification" else QUESTION)
    response = await chat.chat_stream(chat.ChatRequest(user_id=1, conversation_id=1, message=question), Request())
    events = []
    async for raw in response.body_iterator:
        if isinstance(raw, bytes):
            raw = raw.decode()
        lines = raw.strip().splitlines()
        events.append((lines[0][7:], json.loads(lines[1][6:])))
    done = next(data for event, data in events if event == "done")
    rendered = "".join(data["content"] for event, data in events if event == "token")
    assert rendered == done["content"] and SOURCE not in rendered and "# AI Mall" not in rendered
    if kind == "answer":
        assert done["content"] == ANSWER and done["citations"][0]["chunk_id"] == 7
    else:
        assert done.get("citations", []) == []
    if kind.startswith("clarification"):
        assert "退换货" in rendered and "质量" in rendered
        search.assert_not_awaited()
        model.ainvoke.assert_not_awaited()

def test_mixed_turn_prompt_deduplicates_policy_evidence_without_mutating_trace():
    from app.agent.prompt_context import compact_prompt_messages
    context = '<source id="S1" chunk_id="7" title="规则">完整规则及所有例外。</source>'
    payload = {"answerable": True, "reason": "high_confidence", "context": context,
               "citations": list(ALLOWED.values()), "hits": [{"chunk_id": 7, "content": "重复原文"}]}
    original = ToolMessage(name="kb_search", tool_call_id="kb", content=json.dumps(payload))
    copied = compact_prompt_messages([HumanMessage(content="推荐支持退货的手机"), original])[-1]
    assert json.loads(copied.content)["context"] == context
    assert "hits" not in json.loads(copied.content)
    assert "重复原文" not in copied.content
    assert json.loads(original.content) == payload and copied.tool_call_id == original.tool_call_id

@pytest.mark.asyncio
async def test_malformed_unanswerable_reason_remains_safe(monkeypatch):
    model, state = setup(monkeypatch, payload={"answerable": False, "reason": []})
    result = await nodes.agent_node(state)
    assert "暂时" in result["messages"][0].content
    model.ainvoke.assert_not_awaited()

@pytest.mark.asyncio
@pytest.mark.parametrize("limit", ["characters", "source_count"])
async def test_budget_never_drops_a_separate_applicable_exception(monkeypatch, limit):
    count = 2 if limit == "characters" else 5
    texts = ["平台规定满足条件可退货。" + "其他相关条件。" * 140] * count if limit == "characters" else ["完整规则。"] * count
    texts[-1] += "此款耳机拆封后不适用无理由退货。"
    citations = [{"id": f"S{i}", "chunk_id": i, "title": "适用规则"} for i in range(1, count + 1)]
    payload = {"answerable": True, "citations": citations,
               "hits": [{"chunk_id": i, "content": text} for i, text in enumerate(texts, 1)]}
    model, state = setup(monkeypatch, payload=payload)
    nodes.settings.kb_context_max_chars = sum(map(len, texts)) - 1 if limit == "characters" else 3600
    get_tool_ctx().update(rag_allowed_citations={s["id"]: s for s in citations},
                         rag_source_contents={f"S{i}": text for i, text in enumerate(texts, 1)})
    result = await nodes.agent_node(state)
    model.ainvoke.assert_not_awaited()
    assert "[S1]" not in result["messages"][0].content
    assert get_tool_ctx()["rag_reason"].startswith("generation_")


def test_per_paragraph_citations_cannot_disguise_a_document_dump():
    source = "# 平台服务规则\n" + "\n".join(f"第{i}项条款：" + "这是完整规则条件和例外，必须结合实际情况判断。" * 4 for i in range(6))
    dump = "\n".join(line + " [S1]" for line in source.splitlines())
    context = {"rag_used": True, "rag_answerable": True, "rag_allowed_citations": ALLOWED,
               "rag_source_contents": {"S1": source}}
    final = OutputPolicy(QUESTION).finalize(dump, context)
    assert "第0项条款" not in final.content and final.citations == ()

@pytest.mark.asyncio
async def test_structured_answer_gets_program_owned_per_point_citations(monkeypatch):
    model, state = setup(monkeypatch)
    model.ainvoke.return_value = AIMessage(content=json.dumps({"points":[
        {"text":"商品完好时，可在签收之日起7自然日内申请无理由退货；定制商品不适用。", "sources":["S1"]}]}))
    result = await nodes.agent_node(state)
    assert result["messages"][0].content == ANSWER
    assert result["messages"][0].additional_kwargs["knowledge_answer_final"] is True
    assert "response_format" not in model.ainvoke.call_args.kwargs
    assert model.ainvoke.call_args.kwargs["temperature"] == 0

@pytest.mark.asyncio
@pytest.mark.parametrize("structured", [
    {"points":[]}, {"points":[{"text":"支持退货", "sources":["S9"]}]},
    {"points":[{"text":"支持退货", "sources":[]}]}, {"points":[{"text":"支持退货", "sources":"S1"}]},
    {"points":[{"text":42, "sources":["S1"]}]}, {"points":[None]}, {"points":"规则"}, {}])
async def test_malformed_structured_answer_cannot_bypass_citation_guard(monkeypatch, structured):
    model, state = setup(monkeypatch)
    model.ainvoke.return_value = AIMessage(content=json.dumps(structured))
    result = await nodes.agent_node(state)
    final = OutputPolicy(QUESTION).finalize(result["messages"][0].content,get_tool_ctx())
    assert final.citations == () and "支持退货" not in final.content

@pytest.mark.asyncio
async def test_structured_source_body_still_cannot_be_dumped(monkeypatch):
    model, state = setup(monkeypatch)
    model.ainvoke.return_value = AIMessage(content=json.dumps({"points":[{"text":SOURCE, "sources":["S1"]}]}))
    result = await nodes.agent_node(state)
    assert SOURCE not in result["messages"][0].content
    assert get_tool_ctx()["rag_reason"] == "generation_invalid"

@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [True, False])
async def test_legacy_ollama_receives_real_wire_output_budget(monkeypatch, legacy):
    import httpx
    from langchain_openai import ChatOpenAI
    seen=[]
    def handle(request):
        seen.append(json.loads(request.content))
        content=json.dumps({"points":[{"text":ANSWER.removesuffix("[S1]"),"sources":["S1"]}]})
        return httpx.Response(200,json={"id":"qa","object":"chat.completion","created":0,"model":"existing-model",
            "choices":[{"index":0,"message":{"role":"assistant","content":content},"finish_reason":"stop"}]})
    _,state=setup(monkeypatch)
    nodes.settings.kb_answer_timeout_s=2
    nodes.settings.kb_legacy_max_tokens=legacy
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        model=ChatOpenAI(api_key="test-only",base_url="http://ollama.test/v1",model="existing-model",
                        streaming=False,http_async_client=client)
        monkeypatch.setattr(nodes,"get_chat_llm",lambda:model)
        result=await nodes.agent_node(state)
    assert seen and seen[0].get("max_completion_tokens")==512
    assert seen[0].get("max_tokens")==512 if legacy else "max_tokens" not in seen[0]
    assert result["messages"][0].content==ANSWER

@pytest.mark.asyncio
@pytest.mark.parametrize("text", ['{"points":[{"text":"支持退货。[S1]"', '```json\n{"text":"支持退货。[S1]"}\n```'])
async def test_malformed_or_fenced_structures_never_leak_as_plaintext(monkeypatch, text):
    model, state=setup(monkeypatch)
    model.ainvoke.return_value=AIMessage(content=text)
    result=await nodes.agent_node(state)
    assert '"text"' not in result["messages"][0].content
    assert get_tool_ctx()["rag_reason"]=="generation_invalid"

@pytest.mark.asyncio
@pytest.mark.parametrize("claim", ["商品拆封后不支持7天无理由退货。[S1]", "必须是未拆封且未使用过的商品才能退货。[S1]"])
async def test_generated_blanket_refusal_cannot_reverse_explicit_source_exception(monkeypatch, claim):
    source="需核实商品性质、完好和合理查验情况，不能把拆封一概作为拒绝理由。"
    payload={"answerable":True,"citations":list(ALLOWED.values()),"hits":[{"chunk_id":7,"content":source}]}
    model,state=setup(monkeypatch,payload=payload)
    get_tool_ctx()["rag_source_contents"]={"S1":source}
    model.ainvoke.return_value=AIMessage(content=claim)
    result=await nodes.agent_node(state)
    final=OutputPolicy(QUESTION).finalize(result["messages"][0].content,get_tool_ctx())
    assert final.citations==() and "商品名称" in final.content
    assert get_tool_ctx()["rag_reason"]=="generation_conflict"

@pytest.mark.asyncio
async def test_conditional_opened_product_explanation_remains_allowed(monkeypatch):
    source="需核实商品性质、完好和合理查验情况，不能把拆封一概作为拒绝理由。"
    payload={"answerable":True,"citations":list(ALLOWED.values()),"hits":[{"chunk_id":7,"content":source}]}
    model,state=setup(monkeypatch,payload=payload)
    get_tool_ctx()["rag_source_contents"]={"S1":source}
    text="不能把拆封一概作为拒绝理由，需要结合商品性质和合理查验情况核实。[S1]"
    model.ainvoke.return_value=AIMessage(content=text)
    result=await nodes.agent_node(state)
    assert result["messages"][0].content==text

@pytest.mark.asyncio
async def test_streamed_internal_json_is_replaced_by_rendered_terminal_answer(monkeypatch):
    from app.api import chat
    from langchain_core.messages import AIMessageChunk
    class Graph:
        async def astream_events(self,*args,**kwargs):
            get_tool_ctx().update(rag_used=True,rag_answerable=True,rag_reason="high_confidence",
                rag_allowed_citations=ALLOWED,rag_source_contents={"S1":SOURCE})
            raw=json.dumps({"points":[{"text":ANSWER.removesuffix("[S1]"),"sources":["S1"]}]})
            for part in (raw[:30],raw[30:]):
                yield {"event":"on_chat_model_stream","metadata":{"langgraph_node":"agent"},
                       "data":{"chunk":AIMessageChunk(content=part)}}
            yield {"event":"on_chain_end","name":"LangGraph","data":{"output":{"messages":[
                AIMessage(content=ANSWER,additional_kwargs={"knowledge_answer_final":True})]}}}
    class Request:
        async def is_disconnected(self):return False
    monkeypatch.setattr(chat,"graph",Graph())
    monkeypatch.setattr(chat,"checkpointer",None)
    monkeypatch.setattr(chat,"start_trace",lambda **k:False)
    monkeypatch.setattr(chat,"end_trace",lambda **k:None)
    monkeypatch.setattr(chat,"background_memory_extraction",AsyncMock())
    response=await chat.chat_stream(chat.ChatRequest(user_id=1,conversation_id=1,message=QUESTION),Request())
    events=[]
    async for raw in response.body_iterator:
        if isinstance(raw,bytes):raw=raw.decode()
        lines=raw.strip().splitlines()
        events.append((lines[0][7:],json.loads(lines[1][6:])))
    done=next(data for event,data in events if event=="done")
    tokens="".join(data["content"] for event,data in events if event=="token")
    assert tokens==done["content"]==ANSWER
    assert done["citations"][0]["chunk_id"]==7
    assert '"points"' not in tokens
