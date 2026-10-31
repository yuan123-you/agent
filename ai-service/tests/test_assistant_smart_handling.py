import pytest
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver

from app.request_policy import is_negative_sentiment, is_out_of_scope
from app.agent.nodes import intent_router_node, small_talk_node
from app.agent.graph import build_graph
from app.agent.state import AgentState


def test_negative_sentiment_detection():
    negatives = [
        "SB", "sb", "你太笨了", "太笨了", "好笨", "真笨", "太差劲了",
        "真差劲", "垃圾", "这AI真蠢", "听不懂人话", "傻逼", "笨蛋"
    ]
    for text in negatives:
        assert is_negative_sentiment(text) is True, f"Failed for {text}"

    normals = [
        "推荐手机", "好的", "不用了", "谢谢", "拍照好的手机", "我想买个电脑"
    ]
    for text in normals:
        assert is_negative_sentiment(text) is False, f"False positive for {text}"


def test_out_of_scope_detection():
    out_of_scopes = [
        "帮我写一个冒泡排序代码",
        "写个贪吃蛇代码",
        "用python写一个快速排序算法",
        "帮我做一道数学题",
        "帮我写一首关于春天的诗",
        "写一段代码实现二叉树遍历",
    ]
    for text in out_of_scopes:
        assert is_out_of_scope(text) is True, f"Failed for {text}"

    shopping_texts = [
        "推荐一款适合写代码的笔记本电脑",
        "写代码用什么机械键盘好",
        "推荐一本python编程书",
        "我想买个能跑代码的主机",
    ]
    for text in shopping_texts:
        assert is_out_of_scope(text) is False, f"False positive for {text}"


@pytest.mark.asyncio
async def test_semantic_negative_and_out_of_scope_requests_do_not_become_shopping(semantic_route):
    semantic_route("SMALL_TALK")
    for text in ("SB","你太笨了","帮我写一个冒泡排序代码"):
        result=await intent_router_node({"messages":[HumanMessage(content=text)]})
        assert result["intent"]=="SMALL_TALK"


@pytest.mark.asyncio
async def test_intent_router_node_handles_negative_and_out_of_scope(semantic_route):
    semantic_route("SMALL_TALK")
    for text in ["SB", "你太笨了", "帮我写一个冒泡排序代码"]:
        state = AgentState(
            messages=[HumanMessage(content=text)],
            intent=None,
            tool_loop_count=0,
            escalated=False,
            user_id="1",
            conversation_id="1",
            history=[],
            summary=None,
            web_search_enabled=False,
        )
        res = await intent_router_node(state)
        assert res["intent"] == "SMALL_TALK", f"Expected SMALL_TALK for {text}, got {res['intent']}"


@pytest.mark.asyncio
async def test_multi_turn_history_does_not_hijack_negative_or_out_of_scope():
    history_messages = [
        HumanMessage(content="推荐几款拍照好的手机"),
        AIMessage(content="好的，为您推荐这几款手机：1. 华为Pura70..."),
    ]
    for text in ["SB", "你太笨了", "帮我写一个冒泡排序代码"]:
        state = AgentState(
            messages=history_messages + [HumanMessage(content=text)],
            intent=None,
            tool_loop_count=0,
            escalated=False,
            user_id="1",
            conversation_id="1",
            history=[],
            summary=None,
            web_search_enabled=False,
            active_entities={"last_category": "PHONE"},
        )
        res = await intent_router_node(state)
        assert res["intent"] == "SMALL_TALK", f"Expected SMALL_TALK for {text} even with phone history, got {res['intent']}"


@pytest.mark.asyncio
async def test_small_talk_node_apologizes_on_negative_sentiment():
    for text in ["你太笨了", "SB"]:
        state = AgentState(
            messages=[HumanMessage(content=text)],
            intent="SMALL_TALK",
            tool_loop_count=0,
            escalated=False,
            user_id="1",
            conversation_id="1",
            history=[],
            summary=None,
            web_search_enabled=False,
        )
        res = await small_talk_node(state)
        reply = res["messages"][0].content
        assert any(w in reply for w in ["抱歉", "对不起"]), f"Expected apology in reply: {reply}"
        assert any(w in reply for w in ["人工", "客服"]), f"Expected offering human service in reply: {reply}"
        assert "预算" not in reply, f"Should not ask for budget: {reply}"
        assert "商品类型" not in reply, f"Should not ask for product type: {reply}"


@pytest.mark.asyncio
async def test_small_talk_node_declines_out_of_scope_politely():
    state = AgentState(
        messages=[HumanMessage(content="帮我写一个冒泡排序代码")],
        intent="SMALL_TALK",
        tool_loop_count=0,
        escalated=False,
        user_id="1",
        conversation_id="1",
        history=[],
        summary=None,
        web_search_enabled=False,
    )
    res = await small_talk_node(state)
    reply = res["messages"][0].content
    assert any(w in reply for w in ["购物", "电商", "选购"]), f"Expected stating shopping assistant identity: {reply}"
    assert any(w in reply for w in ["代码", "技术", "无法", "非电商"]), f"Expected declining code generation: {reply}"
    assert "请告诉我你想要购买的商品类型" not in reply


@pytest.mark.asyncio
async def test_end_to_end_graph_reproduces_and_fixes_screenshot_dialogue(semantic_route):
    semantic_route("SMALL_TALK")
    cp = MemorySaver()
    app = build_graph(cp)
    thread_config = {"configurable": {"thread_id": "test_screenshot_thread"}}

    # Turn 1: User says SB
    out1 = await app.ainvoke(
        {"messages": [HumanMessage(content="SB")], "user_id": "1", "conversation_id": "100"},
        thread_config,
    )
    reply1 = out1["messages"][-1].content
    assert "请告诉我你想要购买的商品类型" not in reply1
    assert any(w in reply1 for w in ["抱歉", "对不起"])

    # Turn 2: User says 你太笨了
    out2 = await app.ainvoke(
        {"messages": [HumanMessage(content="你太笨了")], "user_id": "1", "conversation_id": "100"},
        thread_config,
    )
    reply2 = out2["messages"][-1].content
    assert "请告诉我你想要购买的商品类型" not in reply2
    assert any(w in reply2 for w in ["抱歉", "对不起"])

    # Turn 3: User says 帮我写一个冒泡排序代码
    out3 = await app.ainvoke(
        {"messages": [HumanMessage(content="帮我写一个冒泡排序代码")], "user_id": "1", "conversation_id": "100"},
        thread_config,
    )
    reply3 = out3["messages"][-1].content
    assert "请告诉我你想要购买的商品类型" not in reply3
    assert any(w in reply3 for w in ["代码", "无法", "购物助手", "非电商"])
