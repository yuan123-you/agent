"""LangGraph 图节点：意图路由 → 购物助理(工具循环) / 闲聊 / 转人工"""
import json
import logging

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
from app.tools.tools import ALL_TOOLS

logger = logging.getLogger("ai-service.agent")


async def intent_router_node(state: AgentState) -> dict:
    """意图识别（结构化 JSON 输出，失败兜底 PRODUCT_CONSULT）"""
    llm = get_intent_llm()
    last = state["messages"][-1]
    user_text = last.content if last else ""
    history_text = "\n".join(
        f'{m.get("role", "USER")}: {m.get("content", "")}' for m in (state.get("history") or [])[-6:]
    )
    prompt = f"历史对话:\n{history_text or '(无)'}\n\n用户最新消息: {user_text}"
    try:
        result = await llm.ainvoke([SystemMessage(content=INTENT_SYSTEM_PROMPT), HumanMessage(content=prompt)])
        content = result.content.strip()
        if content.startswith("```"):
            content = content.strip("`").removeprefix("json").strip()
        data = json.loads(content)
        intent = data.get("intent", "PRODUCT_CONSULT")
        confidence = data.get("confidence")
        logger.info("intent=%s confidence=%s", intent, confidence)
        # 可观测：意图节点打点
        await generation(
            "intent", model=settings.llm_intent_model,
            input_data={"user_text": user_text, "history": history_text[:500]},
            usage={"intent": intent, "confidence": confidence}, tags=["intent"],
        )
    except Exception as e:
        logger.warning("intent parse failed, fallback PRODUCT_CONSULT: %s", e)
        intent = "PRODUCT_CONSULT"
        await generation(
            "intent", model=settings.llm_intent_model,
            input_data={"user_text": user_text}, usage={"intent": intent, "error": str(e)},
            tags=["intent"],
        )
    return {"intent": intent}


def route_by_intent(state: AgentState) -> str:
    intent = state.get("intent")
    if intent == "SMALL_TALK":
        return "small_talk"
    if intent == "HUMAN_REQUEST":
        return "escalate_node"
    return "agent"  # PRODUCT_CONSULT / ORDER_QUERY / ORDER_CREATE / AFTER_SALE_FAQ / 兜底


async def agent_node(state: AgentState) -> dict:
    """购物助理：LLM + 工具循环（ReAct）"""
    llm = get_chat_llm().bind_tools(ALL_TOOLS)
    # 联网开关：开启时在 system prompt 追加"优先联网"指令
    system_text = SHOP_SYSTEM_PROMPT.format(summary=state.get("summary") or "无")
    if state.get("web_search_enabled"):
        system_text += "\n\n## 当前模式：联网搜索已开启\n涉及资讯/新品/价格/平台外问题时，优先调用 web_search 搜索网络内容，再结合站内商品一起回答。"
    system = SystemMessage(content=system_text)
    response = await llm.ainvoke([system] + state["messages"])
    if getattr(response, "tool_calls", None):
        return {"messages": [response], "tool_loop_count": state.get("tool_loop_count", 0) + 1}
    await generation(
        "generate", model=settings.llm_chat_model,
        input_data={"tool_calls": False, "node": "agent"},
        usage={"content": str(getattr(response, "content", ""))[:500], "tokens": 
               getattr(getattr(response, "usage_metadata", None), "total_tokens", None)},
        tags=["generate", "agent"],
    )
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    """有工具调用且未超循环上限 → tools；打满 → 强制收敛节点；否则结束"""
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None) and state.get("tool_loop_count", 0) < settings.max_tool_loops:
        return "tools"
    if getattr(last, "tool_calls", None):
        logger.warning("tool loop limit reached, routing to %s", FINALIZE_FLAG)
        return FINALIZE_FLAG
    return END_FLAG


async def finalize_without_tools(state: AgentState) -> dict:
    """工具循环打满后强制收敛：用不绑定工具的 LLM，基于已有 ToolMessage 给出最终结论"""
    llm = get_chat_llm(streaming=False)
    # 提取本轮决策轨迹，丢弃仅含 tool_calls、无正文的悬空 AI 消息，避免把"未执行的调用"当结论
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
    resp = await llm.ainvoke([
        SystemMessage(content=FINALIZE_SYSTEM_PROMPT),
        HumanMessage(content="以下是本轮对话及工具返回的原始数据，请基于这些内容给用户最终结论：\n\n" + ctx_text),
    ])
    await generation(
        "generate", model=settings.llm_chat_model,
        input_data={"tool_calls": False, "node": "finalize_without_tools"},
        usage={"content": str(getattr(resp, "content", ""))[:500]}, tags=["generate", "finalize"],
    )
    return {"messages": [resp]}


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
