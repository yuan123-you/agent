"""LangGraph 图节点：意图路由 → 购物助理(工具循环) / 闲聊 / 转人工"""
import json
import logging
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent.prompts import (
    ESCALATE_FAIL_TEXT,
    ESCALATE_OK_TEXT,
    FINALIZE_SYSTEM_PROMPT,
    INTENT_SYSTEM_PROMPT,
    SHOP_SYSTEM_PROMPT,
    SMALL_TALK_PROMPT,
)
from app.agent.state import AgentState
from app.clients.backend_client import backend_client
from app.clients.llm import get_chat_llm, get_intent_llm
from app.config import settings
from app.observability.telemetry import generation
from app.tools.tools import (
    ALL_TOOLS,
    after_sale_prepare,
    escalate_to_human,
    kb_search,
    order_cancel_prepare,
    order_create,
    order_query,
    product_detail,
    product_search,
    web_search,
)

logger = logging.getLogger("ai-service.agent")

KNOWN_INTENTS = {
    "PRODUCT_CONSULT", "ORDER_QUERY", "ORDER_CREATE",
    "AFTER_SALE_FAQ", "SMALL_TALK", "ASSISTANT_META", "HUMAN_REQUEST"
}


def parse_intent_json(content: str) -> dict:
    """健壮解析模型输出的意图 JSON，容忍 think 标签、Markdown 及前后缀解释文本"""
    if not content:
        return {}
    cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    match = re.search(r"\{[^{}]*\"intent\"[^{}]*\}", cleaned)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    if cleaned.startswith("```"):
        stripped = cleaned.strip("`").removeprefix("json").strip()
        try:
            return json.loads(stripped)
        except Exception:
            pass
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    return {}


def fallback_intent_by_rules(user_text: str) -> str:
    """当模型未能输出标准 JSON 时，基于规则启发式兜底，避免全部误判为 PRODUCT_CONSULT"""
    t = (user_text or "").strip().lower()
    if any(w in t for w in ["转人工", "人工客服", "找人工", "投诉", "人工服务", "找真人", "联系人工"]):
        return "HUMAN_REQUEST"
    if any(w in t for w in ["你是谁", "你能做什么", "介绍你自己", "你有什么功能", "你叫什么", "介绍下你自己"]):
        return "ASSISTANT_META"
    if any(w in t for w in ["你好", "您好", "早上好", "晚上好", "嗨", "hello", "hi", "谢谢", "多谢", "再见", "在吗"]):
        return "SMALL_TALK"
    if any(w in t for w in ["订单", "物流", "发货没", "发货没有", "快递", "到哪了", "待支付"]):
        return "ORDER_QUERY"
    if any(w in t for w in ["退货", "退换", "退款", "保修", "售后", "运费", "三包", "坏了", "换货", "发票", "送货", "自提", "七天"]):
        return "AFTER_SALE_FAQ"
    if any(w in t for w in ["帮我买", "下单", "拍下", "立刻购买", "我要买", "买第", "买这个", "买它", "帮我下单", "确认购买"]):
        return "ORDER_CREATE"
    return "PRODUCT_CONSULT"


async def intent_router_node(state: AgentState) -> dict:
    """意图识别（结构化 JSON 输出，失败规则启发式兜底）"""
    llm = get_intent_llm()
    last = state["messages"][-1] if state["messages"] else None
    user_text = getattr(last, "content", "") if last else ""
    history_text = "\n".join(
        f'{m.get("role", "USER")}: {m.get("content", "")}' for m in (state.get("history") or [])[-6:]
    )
    prompt = f"历史对话:\n{history_text or '(无)'}\n\n用户最新消息: {user_text}"
    try:
        result = await llm.ainvoke([SystemMessage(content=INTENT_SYSTEM_PROMPT), HumanMessage(content=prompt)])
        content = getattr(result, "content", "") or ""
        data = parse_intent_json(content)
        intent = data.get("intent")
        if intent not in KNOWN_INTENTS:
            intent = fallback_intent_by_rules(user_text)
        confidence = data.get("confidence")
        logger.info("intent=%s confidence=%s", intent, confidence)
        # 可观测：意图节点打点
        await generation(
            "intent", model=settings.llm_intent_model,
            input_data={"user_text": user_text, "history": history_text[:500]},
            usage={"intent": intent, "confidence": confidence}, tags=["intent"],
        )
    except Exception as e:
        intent = fallback_intent_by_rules(user_text)
        logger.warning("intent parse failed, fallback by rules %s: %s", intent, e)
        await generation(
            "intent", model=settings.llm_intent_model,
            input_data={"user_text": user_text}, usage={"intent": intent, "error": str(e)},
            tags=["intent"],
        )
    return {"intent": intent}


def route_by_intent(state: AgentState) -> str:
    intent = state.get("intent")
    if intent in {"SMALL_TALK", "ASSISTANT_META"}:
        return "small_talk"
    if intent == "HUMAN_REQUEST":
        return "escalate_node"
    return "agent"  # PRODUCT_CONSULT / ORDER_QUERY / ORDER_CREATE / AFTER_SALE_FAQ / 兜底


def get_trimmed_messages(messages: list, max_messages: int = 14) -> list:
    """保持安全会话窗口：超出上限时保留最新消息，同时确保不截断出孤立悬空的 ToolMessage"""
    if len(messages) <= max_messages:
        return messages
    window = messages[-max_messages:]
    while window and getattr(window[0], "type", "") == "tool":
        window = window[1:]
    return window or messages[-4:]

def get_tools_for_intent(intent: str | None, web_search_enabled: bool = False) -> list:
    """根据意图精简绑定工具，降低模型干扰，提升工具调用准确率与速度"""
    if intent == "ORDER_QUERY":
        return [order_query, order_cancel_prepare, after_sale_prepare, escalate_to_human]
    if intent == "ORDER_CREATE":
        return [order_create, product_search, product_detail, escalate_to_human]
    if intent == "AFTER_SALE_FAQ":
        tools = [kb_search, escalate_to_human]
        if web_search_enabled:
            tools.append(web_search)
        return tools
    if intent == "PRODUCT_CONSULT":
        tools = [product_search, product_detail, kb_search, escalate_to_human]
        if web_search_enabled:
            tools.append(web_search)
        return tools
    return ALL_TOOLS


async def agent_node(state: AgentState) -> dict:
    """购物助理：LLM + 意图聚焦工具循环（ReAct）"""
    intent = state.get("intent")
    tools = get_tools_for_intent(intent, state.get("web_search_enabled", False))
    llm = get_chat_llm().bind_tools(tools)

    system_text = SHOP_SYSTEM_PROMPT.format(summary=state.get("summary") or "无")
    # 动态追加意图强化指令，消除答非所问
    if intent == "ORDER_QUERY":
        system_text += "\n\n## 焦点提示：买家正在查询订单/物流\n请优先调用 order_query 查询买家真实的订单与物流进展，切勿调用商品搜索。"
    elif intent == "AFTER_SALE_FAQ":
        system_text += "\n\n## 焦点提示：买家正在咨询售后/政策/规则\n请优先调用 kb_search 检索知识库，严格依据检索内容并在事实句末标注 [Sx]。"
    elif intent == "ORDER_CREATE":
        system_text += "\n\n## 焦点提示：买家正在发起下单购买\n请核实商品和数量后调用 order_create 生成确认卡片。"
    elif intent == "PRODUCT_CONSULT":
        system_text += "\n\n## 焦点提示：买家正在咨询或挑选商品\n请先调用 product_search 检索在售真实商品后推荐，禁止虚构商品。"

    if state.get("web_search_enabled"):
        system_text += "\n\n## 当前模式：联网搜索已开启\n涉及资讯/新品/价格/平台外问题时，优先调用 web_search 搜索网络内容，再结合站内商品一起回答。"

    # 会话级实体记忆提示（跨轮次商品/订单上下文）
    entities = state.get("active_entities") or {}
    if entities.get("last_products"):
        prods = [f"{p['name']}(ID:{p['id']})" for p in entities["last_products"][:4] if p.get("name")]
        if prods:
            system_text += f"\n\n## 会话实体记忆（前序轮次推荐过的商品）：\n{'、'.join(prods)}\n买家提及“这款”、“第一款”或“第二个”时，请优先关联上述对应商品。"
    if entities.get("last_category"):
        system_text += f"\n当前会话正在关注的品类：{entities['last_category']}"

    system = SystemMessage(content=system_text)
    trimmed_messages = get_trimmed_messages(state["messages"], max_messages=14)
    response = await llm.ainvoke([system] + trimmed_messages)

    ret = {"messages": [response]}
    if getattr(response, "tool_calls", None):
        ret["tool_loop_count"] = state.get("tool_loop_count", 0) + 1
    else:
        await generation(
            "generate", model=settings.llm_chat_model,
            input_data={"tool_calls": False, "node": "agent"},
            usage={"content": str(getattr(response, "content", ""))[:500], "tokens": 
                   getattr(getattr(response, "usage_metadata", None), "total_tokens", None)},
            tags=["generate", "agent"],
        )
    # 同步工具执行中更新的会话实体记忆
    current_entities = get_tool_ctx().get("active_entities")
    if current_entities:
        ret["active_entities"] = current_entities
    return ret


def _tool_call_signature(call: dict) -> str:
    return json.dumps({"name": call.get("name"), "args": call.get("args") or {}},
                      ensure_ascii=False, sort_keys=True, default=str)


def _all_tool_calls_repeated(messages: list) -> bool:
    latest = getattr(messages[-1], "tool_calls", None) or []
    if not latest:
        return False
    previous = {_tool_call_signature(call) for message in messages[:-1]
                for call in (getattr(message, "tool_calls", None) or [])}
    return bool(previous) and all(_tool_call_signature(call) in previous for call in latest)


def should_continue(state: AgentState) -> str:
    """有工具调用且未超循环上限 → tools；打满 → 强制收敛节点；否则结束"""
    last = state["messages"][-1]
    if _all_tool_calls_repeated(state["messages"]):
        logger.warning("duplicate tool call detected, routing to %s", FINALIZE_FLAG)
        return FINALIZE_FLAG
    if getattr(last, "tool_calls", None) and state.get("tool_loop_count", 0) < settings.max_tool_loops:
        return "tools"
    if getattr(last, "tool_calls", None):
        logger.warning("tool loop limit reached, routing to %s", FINALIZE_FLAG)
        return FINALIZE_FLAG
    return END_FLAG


async def finalize_without_tools(state: AgentState) -> dict:
    """工具循环打满后强制收敛：用不绑定工具的 LLM，基于已有 ToolMessage 给出最终结论"""
    llm = get_chat_llm(streaming=False)
    # 提取用户最新提问，防止长决策轨迹截断导致答非所问
    user_query = ""
    for m in reversed(state["messages"]):
        if getattr(m, "type", "") == "human" or isinstance(m, HumanMessage):
            content = getattr(m, "content", "")
            if isinstance(content, str) and content.strip():
                user_query = content.strip()
                break

    trace: list[str] = []
    for m in state["messages"]:
        content = getattr(m, "content", "")
        tool_calls = getattr(m, "tool_calls", None)
        mtype = getattr(m, "type", "")
        if mtype == "tool":
            trace.append(f"工具返回: {content}")
        elif isinstance(content, str) and content.strip():
            if mtype == "ai":
                trace.append(f"AI 中间思考: {content}" if tool_calls else f"AI: {content}")
            else:
                trace.append(f"用户: {content}")
    ctx_text = "\n".join(trace[-8:]) or "(无可用上下文)"
    prompt = f"买家提问：{user_query or '(未记录用户提问)'}\n\n本轮工具调用与返回数据如下：\n{ctx_text}\n\n请直接针对买家的提问给出清晰、专业的最终回答："
    resp = await llm.ainvoke([
        SystemMessage(content=FINALIZE_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])
    await generation(
        "generate", model=settings.llm_chat_model,
        input_data={"tool_calls": False, "node": "finalize_without_tools"},
        usage={"content": str(getattr(resp, "content", ""))[:500]}, tags=["generate", "finalize"],
    )
    ret = {"messages": [resp]}
    current_entities = get_tool_ctx().get("active_entities")
    if current_entities:
        ret["active_entities"] = current_entities
    return ret


async def small_talk_node(state: AgentState) -> dict:
    """闲聊/欢迎语（不调用业务工具）"""
    llm = get_chat_llm()
    resp = await llm.ainvoke([SystemMessage(content=SMALL_TALK_PROMPT)] + state["messages"][-4:])
    await generation(
        "generate", model=settings.llm_chat_model,
        input_data={"node": "small_talk"},
        usage={"content": str(getattr(resp, "content", ""))[:500]}, tags=["generate", "small_talk"],
    )
    return {"messages": [resp]}


async def escalate_node(state: AgentState) -> dict:
    """转人工：直接回调后端，回复固定话术"""
    ctx_user = state.get("user_id", "0")
    ctx_conv = state.get("conversation_id", "0")
    reason = str(state["messages"][-1].content)[:200] if state["messages"] else ""
    try:
        result = await backend_client.escalate(
            user_id=int(ctx_user), conversation_id=int(ctx_conv), reason=reason,
        )
        text = ESCALATE_OK_TEXT if "error" not in result else ESCALATE_FAIL_TEXT
    except Exception:
        text = ESCALATE_FAIL_TEXT
    return {"messages": [AIMessage(content=text)], "escalated": True}


END_FLAG = "__end__"
FINALIZE_FLAG = "finalize_without_tools"
