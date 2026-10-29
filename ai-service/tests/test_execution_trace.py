from unittest.mock import AsyncMock
import json
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from app.observability.execution_trace import TraceRecorder, trace_span, activate_trace


def test_model_events_capture_usage_and_public_content_not_hidden_reasoning():
    record = TraceRecorder("run-1")
    record.observe({"event":"on_chat_model_start", "run_id":"m1", "name":"ChatModel",
                    "metadata":{"ls_model_name":"qwen"}, "data":{"input":{"messages":[[HumanMessage(content="你好")]]}}})
    record.observe({"event":"on_chat_model_end", "run_id":"m1", "data":{"output":AIMessage(
        content="您好", additional_kwargs={"reasoning_content":"private thoughts"},
        usage_metadata={"input_tokens":10,"output_tokens":5,"total_tokens":15})}})
    payload = record.snapshot("SUCCESS")
    step = payload["stages"][0]
    assert step["model"] == "qwen"
    assert step["usage"]["total_tokens"] == 15
    assert step["durationMs"] >= 0
    assert "private thoughts" not in json.dumps(payload)
    assert step["status"] == "SUCCESS"


def test_masking_and_size_limits():
    record = TraceRecorder("run-1")
    with activate_trace(record):
        with trace_span("input", input={"api_key":"secret", "phone":"13800138000", "authorization":"Bearer private"}) as span:
            span.complete({"text":"联系 test@example.com，手机号13800138000，Bearer very-secret-token", "long":"x"*100000})
    text = json.dumps(record.snapshot("SUCCESS"))
    assert "very-secret-token" not in text and "13800138000" not in text
    assert "test@example.com" not in text and '"api_key": "secret"' not in text
    assert len(text) < 32000


async def test_parallel_spans_keep_request_isolation_and_parentage():
    import asyncio
    async def work(name):
        record = TraceRecorder(name)
        with activate_trace(record):
            with trace_span("parent"):
                await asyncio.sleep(0)
                with trace_span("child", input={"request":name}):
                    pass
        return record.snapshot("SUCCESS")
    a,b = await asyncio.gather(work("A"),work("B"))
    assert a["stages"][1]["parentId"] == a["stages"][0]["id"]
    assert b["stages"][1]["input"]["request"] == "B"
    assert '"A"' not in json.dumps(b)


def test_unfinished_stages_are_marked_failed_and_unknown_usage_is_absent():
    record = TraceRecorder("run-1")
    record.observe({"event":"on_chain_start","name":"agent","run_id":"n1","data":{"input":{}}})
    data=record.snapshot("FAILED", error="timeout")
    assert data["stages"][0]["status"] == "FAILED"
    assert data["stages"][0].get("usage") is None


def test_span_limit_is_explicit_not_unbounded():
    record = TraceRecorder("run-1")
    with activate_trace(record):
        for _ in range(200):
            with trace_span("stage"): pass
    data=record.snapshot("SUCCESS")
    assert len(data["stages"]) <= 96
    assert data["omittedStages"] > 0


async def test_trace_snapshot_is_opt_in_internal_event_and_precedes_done(monkeypatch):
    from app.api import chat
    class Graph:
        async def astream_events(self, *_args, **_kwargs):
            yield {"event":"on_chain_start","name":"small_talk","run_id":"n1","data":{"input":{"question":"你好"}}}
            output={"messages":[AIMessage(content="您好")],"intent":"SMALL_TALK"}
            yield {"event":"on_chain_end","name":"small_talk","run_id":"n1","data":{"output":output}}
            yield {"event":"on_chain_end","name":"LangGraph","data":{"output":output}}
    class Request:
        async def is_disconnected(self): return False
    monkeypatch.setattr(chat,"graph",Graph())
    monkeypatch.setattr(chat,"checkpointer",None)
    monkeypatch.setattr(chat,"start_trace",lambda **kwargs:False)
    monkeypatch.setattr(chat,"end_trace",lambda **kwargs:None)
    req=chat.ChatRequest(user_id=0, conversation_id=1, message="你好", options={"trace_id":"server-run-1"})
    response=await chat.chat_stream(req,Request())
    events=[]
    async for raw in response.body_iterator:
        lines=raw.strip().splitlines(); events.append((lines[0][7:],json.loads(lines[1][6:])))
    trace=next(data for event,data in events if event=="trace")
    assert trace["traceId"]=="server-run-1"
    assert any(s["name"]=="small_talk" for s in trace["stages"])
    assert [event for event,_ in events][-2:] == ["trace","done"]


async def test_rag_trace_reports_both_recall_legs_fusion_scores_and_skipped_rerank():
    from app.rag.retrieval import RetrievalPipeline
    hit={"chunk_id":1,"doc_id":10,"product_id":-1,"docType":"POLICY","content":"退款按原渠道退回", "source":"平台规则","score":.9}
    vector=AsyncMock(return_value={"hits":[hit]})
    bm25=AsyncMock(return_value={"hits":[{**hit,"score":9.0}]})
    record=TraceRecorder("rag-run")
    with activate_trace(record):
        await RetrievalPipeline(vector_search=vector,bm25_search=bm25,reranker=None).search("退款规则",doc_type="POLICY",product_id=-1)
    stages={s["name"]:s for s in record.snapshot("SUCCESS")["stages"]}
    assert {"rag.dense","rag.bm25","rag.metadata_filter","rag.rrf","rag.rerank","rag.answerability"} <= stages.keys()
    assert stages["rag.rerank"]["status"]=="SKIPPED"
    assert stages["rag.rrf"]["output"][0]["rrf_score"] > 0
    assert stages["rag.answerability"]["output"]["decision"]["answerable"] is True


def test_tool_error_payload_is_a_failed_step_even_when_wrapped_in_a_message():
    from langchain_core.messages import ToolMessage
    record=TraceRecorder("tool-run")
    record.observe({"event":"on_tool_start","name":"order_query","run_id":"t1","data":{"input":{}}})
    record.observe({"event":"on_tool_end","name":"order_query","run_id":"t1","data":{"output":ToolMessage(content='{"error":"service unavailable"}',tool_call_id="t1")}})
    assert record.snapshot("FAILED")["stages"][0]["status"] == "FAILED"


async def test_real_graph_events_are_captured_with_completed_nodes_and_model(monkeypatch):
    from app.api import chat
    from app.agent import nodes
    from app.agent.graph import build_graph
    from langgraph.checkpoint.memory import MemorySaver
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    cp=MemorySaver(); monkeypatch.setattr(chat,"checkpointer",cp);monkeypatch.setattr(chat,"graph",build_graph(cp))
    monkeypatch.setattr(nodes,"get_chat_llm",lambda:FakeListChatModel(responses=["好的，我是派蒙，你是旅行者。"],sleep=0))
    monkeypatch.setattr(chat,"persist_naming_memory",AsyncMock(return_value=True))
    monkeypatch.setattr(chat,"start_trace",lambda **kwargs:False);monkeypatch.setattr(chat,"end_trace",lambda **kwargs:None)
    class Request:
        async def is_disconnected(self): return False
    response=await chat.chat_stream(chat.ChatRequest(user_id=1,conversation_id=987,message="你叫派蒙，我叫旅行者",options={"trace_id":"real-graph"}),Request())
    events=[raw async for raw in response.body_iterator]
    trace=json.loads(next(raw for raw in events if raw.startswith("event: trace")).split("data: ",1)[1])
    names={step["name"] for step in trace["stages"]}
    assert {"intent_router","small_talk","context.assemble","output.validate"} <= names
    assert any(step["kind"]=="model" for step in trace["stages"])
    assert all(step["status"] in {"SUCCESS","SKIPPED"} for step in trace["stages"])


def test_think_tags_are_redacted_even_if_provider_puts_them_in_content():
    from app.observability.execution_trace import safe_data
    assert "private steps" not in safe_data("<think>private steps</think>最终答复")


async def test_context_initialization_failure_still_exports_a_failed_trace(monkeypatch):
    from app.api import chat
    class Broken:
        def get(self,*args): raise RuntimeError("checkpoint offline")
    class Request:
        async def is_disconnected(self): return False
    monkeypatch.setattr(chat,"checkpointer",Broken())
    response=await chat.chat_stream(chat.ChatRequest(user_id=0,conversation_id=1,message="你好",options={"trace_id":"broken-context"}),Request())
    events=[raw async for raw in response.body_iterator]
    assert any(raw.startswith("event: trace") and '"FAILED"' in raw for raw in events)
    assert events[-1].startswith("event: error")


def test_quoted_credentials_in_text_are_also_redacted():
    from app.observability.execution_trace import safe_data
    assert "sensitive-value" not in safe_data('{"password":"sensitive-value"}')


async def test_background_memory_updates_same_server_trace_after_response(monkeypatch):
    from app.api import chat
    class Graph:
        async def astream_events(self,*args,**kwargs):
            yield {"event":"on_chain_end","name":"LangGraph","data":{"output":{"messages":[AIMessage(content="好的") ]}}}
    class Request:
        async def is_disconnected(self): return False
    monkeypatch.setattr(chat,"graph",Graph());monkeypatch.setattr(chat,"checkpointer",None)
    monkeypatch.setattr(chat,"start_trace",lambda **kwargs:False);monkeypatch.setattr(chat,"end_trace",lambda **kwargs:None)
    extract=AsyncMock(); publish=AsyncMock(return_value={"success":True})
    monkeypatch.setattr(chat,"background_memory_extraction",extract)
    monkeypatch.setattr(chat.backend_client,"record_ai_trace",publish)
    response=await chat.chat_stream(chat.ChatRequest(user_id=1,conversation_id=1,message="我更喜欢拍照好的手机",options={"trace_id":"background-run"}),Request())
    events=[raw async for raw in response.body_iterator]
    main=json.loads(next(raw for raw in events if raw.startswith("event: trace")).split("data: ",1)[1])
    extract.assert_not_awaited(); publish.assert_not_awaited()
    await response.background()
    trace_id,updated=publish.await_args.args
    assert trace_id=="background-run" and updated["traceId"]==trace_id
    assert updated["durationMs"]==main["durationMs"]
    assert any(s["name"]=="memory.preference" for s in updated["stages"])
