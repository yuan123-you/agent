"""对话流接口：POST /v1/chat/stream（含独立 action 事件）+ 会话摘要压缩"""
import asyncio
import json
import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from app.agent.graph import graph
from app.agent.link_guard import collect_known_ids, guard_links
from app.agent.prompts import SUMMARY_PROMPT
from app.agent.state import AgentState
from app.clients.llm import get_chat_llm
from app.config import settings
from app.observability.telemetry import end_trace, get_trace_id, start_trace, tool_span
from app.sse import sse
from app.tools.tools import set_tool_ctx

router = APIRouter()
logger = logging.getLogger("ai-service.chat")


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    conversation_id: int
    user_id: int
    message: str
    history: list[ChatMessage] = []
    summary: str | None = None
    user_profile: dict = {}
    web_search_enabled: bool = False
    options: dict = {}


class SummarizeRequest(BaseModel):
    old_summary: str | None = None
    messages: list[ChatMessage]


def build_state(req: ChatRequest) -> AgentState:
    """history（后端传入）+ 本轮用户消息 → 初始 messages"""
    msgs = []
    for h in req.history[-10:]:
        msgs.append(HumanMessage(content=h.content) if h.role == "USER" else AIMessage(content=h.content))
    msgs.append(HumanMessage(content=req.message))
    return AgentState(
        messages=msgs,
        intent=None,
        tool_loop_count=0,
        escalated=False,
        user_id=str(req.user_id),
        conversation_id=str(req.conversation_id),
        history=[h.model_dump() for h in req.history],
        summary=req.summary,
        web_search_enabled=req.web_search_enabled,
    )


def _short(obj, limit: int = 500) -> str:
    try:
        s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        s = str(obj)
    return s[:limit]


def _tool_result_preview(out) -> dict:
    """工具结果脱敏摘要（前端过程可视化用）"""
    if out is None:
        return {}
    if isinstance(out, dict):
        r = dict(out)
        if isinstance(r.get("products"), list):
            r["products"] = [p.get("name") for p in r["products"]][:5]
        if isinstance(r.get("orders"), list):
            r["orders"] = [o.get("orderNo") for o in r["orders"]][:5]
        if isinstance(r.get("hits"), list):
            r["hits"] = [h.get("source") for h in r["hits"]][:5]
        return {"preview": _short(r)}
    return {"preview": _short(out)}


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    async def gen():
        start = time.time()
        # 工具上下文：身份由服务端注入（越权防护红线）
        ctx = {"user_id": str(req.user_id), "conversation_id": str(req.conversation_id),
               "degraded": False, "escalated": False}
        set_tool_ctx(ctx)
        parts: list[str] = []
        usage: dict = {}
        known_ids: set[str] = set()
        # 可观测：开启本会话 trace（session=conversation_id）
        traced = start_trace(conversation_id=req.conversation_id, user_id=req.user_id,
                             metadata={"message": _short(req.message, 200), "trace_id": ""})
        timed_out = False
        try:
            final_state: dict | None = None
            tool_spans: dict[str, object] = {}
            try:
                # 总请求超时保护：超过 chat_timeout_s 秒强制终止图运行；recursion_limit 限制图递归深度
                async with asyncio.timeout(settings.chat_timeout_s):
                    async for ev in graph.astream_events(
                        build_state(req),
                        config={"recursion_limit": settings.agent_recursion_limit},
                        version="v2",
                    ):
                        # 客户端断连：取消剩余图执行，停止产出
                        if await request.is_disconnected():
                            logger.info("client disconnected, cancelling graph")
                            break
                        kind = ev["event"]
                        if kind == "on_chat_model_stream":
                            # 意图识别节点的输出不面向用户，跳过
                            if (ev.get("metadata") or {}).get("langgraph_node") == "intent_router":
                                continue
                            chunk = ev["data"].get("chunk")
                            content = getattr(chunk, "content", "")
                            tool_chunks = getattr(chunk, "tool_call_chunks", None)
                            if isinstance(content, str) and content and not tool_chunks:
                                parts.append(content)
                                yield sse("token", {"content": content})
                            um = getattr(chunk, "usage_metadata", None)
                            if um:
                                usage = {"promptTokens": um.get("input_tokens", 0),
                                         "completionTokens": um.get("output_tokens", 0)}
                        elif kind == "on_tool_start":
                            args = ev["data"].get("input")
                            # 可观测：工具开始
                            span = tool_span(ev["name"], input_data=_short(args, 300)) if traced else None
                            if span:
                                span.__enter__()
                                tool_spans[ev["run_id"]] = span
                            yield sse("tool_call", {
                                "callId": ev["run_id"], "tool": ev["name"],
                                "args": {"input": _short(args, 200)} if not isinstance(args, dict) else
                                        {k: _short(v, 100) for k, v in args.items()},
                            })
                        elif kind == "on_tool_end":
                            out = ev["data"].get("output")
                            known_ids.update(collect_known_ids(_short(out, 4000)))
                            # 可观测：工具结束
                            if traced and ev.get("run_id") in tool_spans:
                                span = tool_spans.pop(ev["run_id"])
                                span.complete(_tool_result_preview(out))
                                span.__exit__(None, None, None)
                            yield sse("tool_result", {
                                "callId": ev["run_id"], "tool": ev["name"],
                                "result": _tool_result_preview(out),
                            })
                        elif kind == "on_chain_end" and ev.get("name") == "LangGraph":
                            # 捕获图最终状态（非流式节点如 escalate_node 的回复兜底）
                            final_state = ev["data"].get("output")
            except TimeoutError:
                logger.warning("chat stream timed out after %ss, forcing finish", settings.chat_timeout_s)
                timed_out = True

            # 非流式节点兜底：token 流为空时取最终 state 的最后一条 AI 消息
            final_text = "".join(parts)
            if not final_text and final_state:
                msgs = final_state.get("messages") if isinstance(final_state, dict) else None
                if msgs:
                    for m in reversed(msgs):
                        content = getattr(m, "content", "")
                        if getattr(m, "type", "") == "ai" and isinstance(content, str) and content:
                            final_text = content
                            break
            guarded = guard_links(final_text, known_ids) if settings.link_guard_enabled else final_text
            end_trace(output={"content": _short(guarded, 300), "latencyMs": int((time.time() - start) * 1000),
                              "traceId": get_trace_id()})
            for action in ctx.get("actions", []):
                yield sse("action", action)
            yield sse("done", {
                "content": guarded,
                "tokenUsage": usage,
                "latencyMs": int((time.time() - start) * 1000),
                "degraded": bool(ctx.get("degraded")),
                "timedOut": timed_out,
            })
        except Exception as e:
            logger.exception("chat stream error: %s", e)
            end_trace(output={"error": str(e)})
            yield sse("error", {"code": 5001, "message": "AI 服务内部错误，请稍后重试"})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat/summarize")
async def summarize(req: SummarizeRequest):
    """会话摘要压缩（后端长记忆维护时调用，非流式）"""
    llm = get_chat_llm(streaming=False)
    convo = (req.old_summary or "") + "\n" + "\n".join(
        f"{m.role}: {m.content}" for m in req.messages
    )
    resp = await llm.ainvoke([
        SystemMessage(content=SUMMARY_PROMPT),
        HumanMessage(content=convo[-4000:]),
    ])
    return {"summary": resp.content}

