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


TIMEOUT_FALLBACK_TEXT = "本次查询耗时较长，暂未能生成完整结果。请稍后重试，或转接人工客服。"


def _timeout_fallback(content: str, timed_out: bool) -> str:
    """仅在超时且没有任何可用内容时提供非空降级回复。"""
    return content or (TIMEOUT_FALLBACK_TEXT if timed_out else "")


def _short(obj, limit: int = 500) -> str:
    try:
        s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        s = str(obj)
    return s[:limit]


def _tool_result_preview(out) -> dict:
    """将 ToolMessage 解包成面向买家的简短结果，绝不暴露协议元数据。"""
    if out is None:
        return {}

    tool_name = getattr(out, "name", "") or ""
    value = getattr(out, "content", out)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {"preview": _short(value)}
    if not isinstance(value, dict):
        return {"preview": "工具执行完成"}
    if value.get("error"):
        return {"preview": f"执行失败：{_short(value['error'], 200)}"}

    if tool_name == "product_search":
        products = value.get("products") or []
        if not products:
            return {"preview": "未找到符合条件的商品"}
        items = [
            f"{p.get('name', '未命名商品')}（¥{p['price']}）" if p.get("price") is not None else
            str(p.get("name", "未命名商品"))
            for p in products[:5]
        ]
        return {"preview": f"找到 {len(products)} 件商品：{'、'.join(items)}"}

    if tool_name == "product_detail":
        parts = [str(value.get("name") or "商品详情")]
        if value.get("price") is not None:
            parts.append(f"¥{value['price']}")
        if value.get("stock") is not None:
            parts.append(f"库存 {value['stock']} 件")
        preview = " · ".join(parts)
        if value.get("sellingPoints"):
            preview += f"\n卖点：{_short(value['sellingPoints'], 160)}"
        return {"preview": preview}

    if tool_name == "order_query":
        orders = value.get("orders") or []
        if not orders:
            return {"preview": "暂无符合条件的订单"}
        items = [
            " · ".join(str(v) for v in (o.get("orderNo"), o.get("statusText")) if v)
            for o in orders[:5]
        ]
        return {"preview": f"找到 {len(orders)} 个订单：{'、'.join(items)}"}

    if tool_name == "order_create":
        return {"preview": "已生成待确认订单，请在下方确认卡片中核对信息"}

    if tool_name == "order_cancel_prepare":
        return {"preview": "已生成待确认的订单取消请求，请在下方卡片中核对"}

    if tool_name == "after_sale_prepare":
        return {"preview": "已生成待确认的售后申请，请在下方卡片中核对"}

    if tool_name == "kb_search":
        hits = value.get("hits") or []
        sources = list(dict.fromkeys(str(h.get("source")) for h in hits if h.get("source")))
        return {"preview": f"找到 {len(hits)} 条相关资料" + (f"：{'、'.join(sources[:5])}" if sources else "")}

    if tool_name == "web_search":
        results = value.get("results") or []
        titles = [str(item.get("title")) for item in results[:5] if item.get("title")]
        return {"preview": f"找到 {len(results)} 条网络结果" + (f"：{'、'.join(titles)}" if titles else "")}

    if tool_name == "escalate_to_human":
        return {"preview": "已提交人工客服转接请求"}

    return {"preview": "工具执行完成"}


def _eval_tool_metadata(out) -> dict:
    """Return only ranked identities/citations needed by opt-in live evaluation."""
    name = getattr(out, "name", "") or ""
    value = getattr(out, "content", out)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}
    if not isinstance(value, dict):
        return {}
    if name == "product_search":
        return {"products": [
            {"productId": item.get("productId"), "name": item.get("name", ""),
             "category": item.get("category", ""), "rank": rank}
            for rank, item in enumerate(value.get("products") or [], 1)
        ]}
    if name == "kb_search":
        return {"hits": [
            {"chunkId": item.get("chunk_id"), "docId": item.get("doc_id"),
             "source": item.get("source", ""), "score": item.get("score"), "rank": rank}
            for rank, item in enumerate(value.get("hits") or [], 1)
        ]}
    return {}


def _done_eval_metadata(final_state, enabled: bool) -> dict:
    if not enabled or not isinstance(final_state, dict):
        return {}
    return {"intent": final_state.get("intent")}


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    async def gen():
        start = time.time()
        eval_enabled = req.options.get("include_eval_metadata") is True
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
                            tool_payload = {
                                "callId": ev["run_id"], "tool": ev["name"],
                                "result": _tool_result_preview(out),
                            }
                            if eval_enabled:
                                eval_data = _eval_tool_metadata(out)
                                if eval_data:
                                    tool_payload["eval"] = eval_data
                            yield sse("tool_result", tool_payload)
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
            final_text = _timeout_fallback(final_text, timed_out)
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
                **_done_eval_metadata(final_state, eval_enabled),
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

