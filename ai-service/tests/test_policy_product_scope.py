"""SPEC-05: policy evidence must belong to the selected product or platform."""
import json

import pytest
from langchain_core.messages import HumanMessage, ToolMessage

from app.agent import nodes
from app.rag import retrieval
from app.tools.tools import kb_search, set_tool_ctx


PRODUCTS = [{"id": 101, "name": "商品甲"}, {"id": 202, "name": "商品乙"}]


@pytest.fixture(autouse=True)
def isolated_policy_context(monkeypatch):
    set_tool_ctx({})
    monkeypatch.setattr(nodes.settings, "kb_response_mode", "extractive")

    def unexpected_model():
        raise AssertionError("Policy scope must be resolved before any model call")

    monkeypatch.setattr(nodes, "get_chat_llm", unexpected_model)
    yield
    set_tool_ctx({})


def policy_state(question, products):
    return {
        "intent": "AFTER_SALE_FAQ",
        "messages": [HumanMessage(content=question)],
        "tool_loop_count": 0,
        "active_entities": {"last_products": products},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("question,products,expected_id", [
    ("这款商品的退货条件是什么？", PRODUCTS[:1], 101),
    ("第二款的保修期限是多久？", PRODUCTS, 202),
    ("最后一款的退货政策是什么？", PRODUCTS, 202),
    ("商品乙的保修期限是多久？", PRODUCTS, 202),
    ("平台的退货条件是什么？", PRODUCTS[:1], -1),
    ("退货条件是什么？", [], -1),
])
async def test_mandatory_policy_lookup_uses_applicable_product_scope(question, products, expected_id):
    result = await nodes.agent_node(policy_state(question, products))

    calls = result["messages"][0].tool_calls
    assert len(calls) == 1
    assert calls[0]["name"] == "kb_search"
    assert calls[0]["args"]["product_id"] == expected_id


@pytest.mark.asyncio
@pytest.mark.parametrize("question,products", [
    ("这款商品的退货条件是什么？", PRODUCTS),
    ("第五款的退货条件是什么？", PRODUCTS),
    ("第一款和第二款的退货条件是什么？", PRODUCTS),
    ("第二款商品甲的退货条件是什么？", PRODUCTS),
    ("这款商品的退货条件是什么？", []),
])
async def test_ambiguous_product_policy_asks_for_clarification_without_unscoped_lookup(question, products):
    result = await nodes.agent_node(policy_state(question, products))

    answer = result["messages"][0]
    assert not answer.tool_calls
    assert "明确" in answer.content
    assert "商品" in answer.content


@pytest.mark.asyncio
async def test_selected_product_policy_answer_excludes_other_product_evidence(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from langchain_core.messages import AIMessage

    async def synthesize(messages, **kwargs):
        evidence = json.loads(messages[-1].content)["sources"]
        assert all("乙凭证" not in source["text"] for source in evidence)
        return AIMessage(content="\n".join(source["text"] + f'[{source["id"]}]' for source in evidence))

    monkeypatch.setattr(nodes, "get_chat_llm", lambda: SimpleNamespace(ainvoke=AsyncMock(side_effect=synthesize)))
    records = [
        {"chunk_id": 2, "doc_id": 2, "product_id": 202, "docType": "POLICY",
         "content": "商品乙专属规则：乙凭证。", "source": "乙政策", "score": 100.0},
        {"chunk_id": 1, "doc_id": 1, "product_id": 101, "docType": "POLICY",
         "content": "商品甲专属规则：甲凭证。", "source": "甲政策", "score": 100.0},
        {"chunk_id": 3, "doc_id": 3, "product_id": -1, "docType": "POLICY",
         "content": "平台通用规则：按申请记录处理。", "source": "平台政策", "score": 100.0},
    ]

    async def recall(*args, **kwargs):
        # The real pipeline must enforce scope even if an adapter returns extra hits.
        return {"hits": records}

    pipeline = retrieval.RetrievalPipeline(vector_search=recall, bm25_search=recall, reranker=None)
    monkeypatch.setattr(retrieval, "get_retrieval_pipeline", lambda: pipeline)
    state = policy_state("这款商品的退货条件是什么？", PRODUCTS[:1])
    first = await nodes.agent_node(state)
    call = first["messages"][0].tool_calls[0]
    evidence = await kb_search.ainvoke(call["args"])
    final = await nodes.agent_node({
        **state, "tool_loop_count": 1,
        "messages": state["messages"] + [first["messages"][0], ToolMessage(
            name="kb_search", tool_call_id=call["id"], content=json.dumps(evidence, ensure_ascii=False))],
    })

    text = final["messages"][0].content
    assert "甲凭证" in text
    assert "平台通用规则" in text
    assert "乙凭证" not in text
    assert {source["chunk_id"] for source in evidence["citations"]} == {1, 3}


@pytest.mark.asyncio
async def test_ambiguous_policy_clarification_survives_sse_citation_gate(monkeypatch):
    from unittest.mock import AsyncMock
    from langgraph.checkpoint.memory import MemorySaver
    from app.agent.graph import build_graph
    from app.api import chat

    question = "这款商品的退货条件是什么？"
    monkeypatch.setattr(chat, "build_state", lambda *args, **kwargs: policy_state(question, PRODUCTS))
    monkeypatch.setattr(chat, "graph", build_graph(MemorySaver()))
    monkeypatch.setattr(chat, "start_trace", lambda **kwargs: False)
    monkeypatch.setattr(chat, "end_trace", lambda **kwargs: None)
    monkeypatch.setattr(chat, "background_memory_extraction", AsyncMock())

    class Request:
        async def is_disconnected(self):
            return False

    response = await chat.chat_stream(chat.ChatRequest(user_id=1, conversation_id=901, message=question), Request())
    events = []
    async for raw in response.body_iterator:
        if isinstance(raw, bytes):
            raw = raw.decode()
        lines = raw.strip().splitlines()
        events.append((lines[0][7:], json.loads(lines[1][6:])))

    done = next(payload for event, payload in events if event == "done")
    assert "请明确" in done["content"]
    assert done["citations"] == []
    assert "证据不足" not in done["content"]
    assert all(event != "tool_call" for event, _ in events)
    assert "".join(payload["content"] for event, payload in events if event == "token") == done["content"]
