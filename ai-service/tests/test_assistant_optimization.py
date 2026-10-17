import pytest
from app.agent.nodes import parse_intent_json, fallback_intent_by_rules, get_tools_for_intent
from app.tools.tools import normalize_category, clean_search_keyword


def test_parse_intent_json_handles_thinking_and_markdown():
    raw_with_think = "<think>思考中：用户在查询订单物流状态</think>```json\n{\"intent\": \"ORDER_QUERY\", \"confidence\": 0.95}\n```"
    parsed = parse_intent_json(raw_with_think)
    assert parsed.get("intent") == "ORDER_QUERY"
    assert parsed.get("confidence") == 0.95


def test_parse_intent_json_handles_surrounding_text():
    raw_with_text = "意图判断结果如下：\n{\"intent\": \"AFTER_SALE_FAQ\", \"confidence\": 0.88}\n希望对你有帮助"
    parsed = parse_intent_json(raw_with_text)
    assert parsed.get("intent") == "AFTER_SALE_FAQ"


def test_fallback_intent_by_rules():
    assert fallback_intent_by_rules("你好呀") == "SMALL_TALK"
    assert fallback_intent_by_rules("谢谢你啦") == "SMALL_TALK"
    assert fallback_intent_by_rules("你是谁") == "ASSISTANT_META"
    assert fallback_intent_by_rules("我的订单到哪了") == "ORDER_QUERY"
    assert fallback_intent_by_rules("发货没有呢") == "ORDER_QUERY"
    assert fallback_intent_by_rules("七天无理由退货运费谁出") == "AFTER_SALE_FAQ"
    assert fallback_intent_by_rules("保修期多久") == "AFTER_SALE_FAQ"
    assert fallback_intent_by_rules("转人工客服") == "HUMAN_REQUEST"
    assert fallback_intent_by_rules("我要下单买这个") == "ORDER_CREATE"
    assert fallback_intent_by_rules("推荐一款电脑") == "PRODUCT_CONSULT"


def test_normalize_category():
    assert normalize_category("手机") == "PHONE"
    assert normalize_category("手机数码") == "PHONE"
    assert normalize_category("电脑") == "COMPUTER"
    assert normalize_category("laptop") == "COMPUTER"
    assert normalize_category("笔记本") == "COMPUTER"
    assert normalize_category("数码配件") == "DIGITAL"
    assert normalize_category("衣服") == "CLOTHING"
    assert normalize_category("鞋子") == "SHOES"
    assert normalize_category("背包") == "BAGS"
    assert normalize_category("运动户外") == "SPORTS"
    assert normalize_category("首饰") == "JEWELRY"


def test_clean_search_keyword():
    assert clean_search_keyword("推荐一款拍照手机") == "拍照手机"
    assert clean_search_keyword("帮我找性价比高的轻薄本") == "轻薄本"
    assert clean_search_keyword("我想看便宜好用的蓝牙耳机") == "蓝牙耳机"


def test_intent_tools_pruning():
    order_tools = [t.name for t in get_tools_for_intent("ORDER_QUERY")]
    assert "order_query" in order_tools
    assert "product_search" not in order_tools

    faq_tools = [t.name for t in get_tools_for_intent("AFTER_SALE_FAQ")]
    assert "kb_search" in faq_tools
    assert "order_create" not in faq_tools

    product_tools = [t.name for t in get_tools_for_intent("PRODUCT_CONSULT")]
    assert "product_search" in product_tools
    assert "order_cancel_prepare" not in product_tools


def test_clean_search_keyword_pronouns_return_none():
    assert clean_search_keyword("这款") is None
    assert clean_search_keyword("它") is None
    assert clean_search_keyword("刚才那个") is None

from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from app.api.chat import ChatRequest, ChatMessage, build_state
from app.agent.nodes import get_trimmed_messages
from app.tools.tools import set_tool_ctx, get_tool_ctx, clean_kb_query


def test_build_state_checkpointer_integration():
    from langgraph.graph import StateGraph, START, END
    from app.agent.state import AgentState

    builder = StateGraph(AgentState)
    builder.add_node("echo", lambda s: {"messages": [AIMessage(content="echo")]})
    builder.add_edge(START, "echo")
    builder.add_edge("echo", END)

    cp = MemorySaver()
    test_graph = builder.compile(checkpointer=cp)

    req1 = ChatRequest(
        conversation_id=999,
        user_id=1,
        message="第一句",
        history=[],
    )
    # First turn: no checkpoint -> includes history + message
    state1 = build_state(req1, checkpointer=cp)
    assert len(state1["messages"]) == 1

    cfg = {"configurable": {"thread_id": "conv_999"}}
    test_graph.invoke(state1, cfg)

    # Second turn: checkpoint exists -> returns only new message, avoids duplicate history
    req2 = ChatRequest(
        conversation_id=999,
        user_id=1,
        message="第二句",
        history=[ChatMessage(role="USER", content="第一句"), ChatMessage(role="AI", content="echo")],
    )
    state2 = build_state(req2, checkpointer=cp)
    assert len(state2["messages"]) == 1
    assert state2["messages"][0].content == "第二句"


def test_get_trimmed_messages_avoids_orphaned_tool_message():
    messages = [
        HumanMessage(content="推荐电脑"),
        AIMessage(content="", tool_calls=[{"name": "search", "args": {}, "id": "1"}]),
        ToolMessage(content="电脑结果", tool_call_id="1"),
        AIMessage(content="推荐了MacBook"),
        HumanMessage(content="第二款多少钱？"),
    ]
    # Slicing with max_messages=3 would land on ToolMessage. It must safely drop the ToolMessage to start with AIMessage or HumanMessage.
    trimmed = get_trimmed_messages(messages, max_messages=3)
    assert getattr(trimmed[0], "type", "") != "tool"


def test_clean_kb_query():
    assert clean_kb_query("请问七天无理由退货运费谁出？") == "七天无理由退货运费谁出？"
    assert clean_kb_query("我想咨询保修期是多久") == "保修期是多久"


def test_build_state_preserves_active_entities_across_turns():
    from langgraph.graph import StateGraph, START, END
    from app.agent.state import AgentState

    builder = StateGraph(AgentState)
    def save_entity_node(s):
        return {
            "messages": [AIMessage(content="推荐了ThinkPad")],
            "active_entities": {"last_category": "COMPUTER", "last_order_id": 12345}
        }
    builder.add_node("save_node", save_entity_node)
    builder.add_edge(START, "save_node")
    builder.add_edge("save_node", END)

    cp = MemorySaver()
    test_graph = builder.compile(checkpointer=cp)

    req1 = ChatRequest(conversation_id=888, user_id=1, message="看下电脑", history=[])
    state1 = build_state(req1, checkpointer=cp)
    cfg = {"configurable": {"thread_id": "conv_888"}}
    test_graph.invoke(state1, cfg)

    # Turn 2: verify build_state loads saved entities
    req2 = ChatRequest(conversation_id=888, user_id=1, message="只要5000以内的", history=[])
    state2 = build_state(req2, checkpointer=cp)
    assert state2.get("active_entities") is not None
    assert state2["active_entities"].get("last_category") == "COMPUTER"
    assert state2["active_entities"].get("last_order_id") == 12345


def test_clean_search_keyword_budget_and_prefixes():
    assert clean_search_keyword("5000以内") is None
    assert clean_search_keyword("3000左右") is None
    assert clean_search_keyword("有没有游戏本") == "游戏本"
    assert clean_search_keyword("给我推荐一款手机") == "手机"


def test_fallback_intent_additional_order_keywords():
    assert fallback_intent_by_rules("买第一个") == "ORDER_CREATE"
    assert fallback_intent_by_rules("买这个") == "ORDER_CREATE"
    assert fallback_intent_by_rules("买它") == "ORDER_CREATE"
    assert fallback_intent_by_rules("帮我下单") == "ORDER_CREATE"


@pytest.mark.asyncio
async def test_order_tools_missing_entity_error():
    from app.tools.tools import order_create, order_cancel_prepare, set_tool_ctx
    set_tool_ctx({"active_entities": {}})
    res_cancel = await order_cancel_prepare.ainvoke({"order_id": 0, "reason": "不想要了"})
    assert "error" in res_cancel
    res_create = await order_create.ainvoke({"product_id": 0, "quantity": 1})
    assert "error" in res_create


def test_sqlite_saver_persistence_across_restart(tmp_path):
    import sqlite3
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import StateGraph, START, END
    from app.agent.state import AgentState

    db_file = tmp_path / "test_persist.db"

    # Stage 1: First "process"
    conn1 = sqlite3.connect(str(db_file), check_same_thread=False)
    saver1 = SqliteSaver(conn1)
    saver1.setup()

    builder1 = StateGraph(AgentState)
    builder1.add_node("n1", lambda s: {"messages": [AIMessage(content="bot1")], "active_entities": {"last_category": "COMPUTER", "last_order_id": 9999}})
    builder1.add_edge(START, "n1")
    builder1.add_edge("n1", END)
    g1 = builder1.compile(checkpointer=saver1)

    req1 = ChatRequest(conversation_id=101, user_id=1, message="看下电脑", history=[])
    cfg = {"configurable": {"thread_id": f"conv_{req1.conversation_id}"}}
    st1 = build_state(req1, checkpointer=saver1)
    g1.invoke(st1, cfg)
    conn1.close()

    # Stage 2: Simulating service restart (fresh process opening the same sqlite file)
    conn2 = sqlite3.connect(str(db_file), check_same_thread=False)
    saver2 = SqliteSaver(conn2)
    saver2.setup()

    req2 = ChatRequest(conversation_id=101, user_id=1, message="只要5000以内的", history=[])
    st2 = build_state(req2, checkpointer=saver2)

    assert len(st2["messages"]) == 1
    assert st2["messages"][0].content == "只要5000以内的"
    assert st2["active_entities"]["last_category"] == "COMPUTER"
    assert st2["active_entities"]["last_order_id"] == 9999
    conn2.close()


@pytest.mark.asyncio
async def test_agent_node_runs_without_name_error(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock
    from app.agent.nodes import agent_node, finalize_without_tools
    from app.tools.tools import set_tool_ctx

    set_tool_ctx({"active_entities": {"last_category": "COMPUTER"}})
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="推荐了商品"))

    monkeypatch.setattr("app.agent.nodes.get_chat_llm", lambda *a, **kw: mock_llm)

    state = {
        "messages": [HumanMessage(content="推荐电脑")],
        "intent": "PRODUCT_CONSULT",
        "tool_loop_count": 0,
        "active_entities": {"last_category": "COMPUTER"},
    }
    ret = await agent_node(state)
    assert ret["messages"][0].tool_calls[0]["name"] == "product_search"
    assert ret["messages"][0].tool_calls[0]["args"]["category"] == "COMPUTER"
    assert ret.get("active_entities") == {"last_category": "COMPUTER"}

    ret_finalize = await finalize_without_tools(state)
    assert ret_finalize["messages"][0].content == "推荐了商品"
    assert ret_finalize.get("active_entities") == {"last_category": "COMPUTER"}
