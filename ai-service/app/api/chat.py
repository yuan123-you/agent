"""对话流接口：POST /v1/chat/stream（含独立 action 事件）+ 会话摘要压缩"""
import asyncio
from contextlib import aclosing
import json
import logging
import re
import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, RemoveMessage
from pydantic import BaseModel

from app.agent.graph import checkpointer, graph
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from app.agent.memory import background_memory_extraction, persist_naming_memory, should_extract_memory
from app.agent.identity import resolve_profile
from app.agent.link_guard import GuardedLinkBuffer
from app.agent.output import OutputPolicy
from app.agent.request_decision import validated_focus
from app.agent.prompts import SUMMARY_PROMPT
from app.agent.state import AgentState
from app.clients.llm import get_chat_llm
from app.config import settings
from app.observability.execution_trace import TraceRecorder, activate_trace, trace_span
from app.clients.backend_client import backend_client
from app.observability.telemetry import end_trace, get_trace_id, start_trace, tool_span
from app.sse import sse
from app.request_policy import budget_from_text
from app.tools.tools import category_from_user_text, set_tool_ctx

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
    long_term_memory: list[dict] = []
    web_search_enabled: bool = False
    options: dict = {}


class SummarizeRequest(BaseModel):
    old_summary: str | None = None
    messages: list[ChatMessage]


def build_state(req: ChatRequest, checkpointer: Any = None) -> AgentState:
    """history（后端传入）+ 本轮用户消息 → 初始 messages。
    若 checkpointer 中已有该会话的历史快照，则本轮只传入新增的 HumanMessage，
    由 LangGraph 的 add_messages 自动做流式累加，避免会话记忆重复；
    同时继承已有快照中的 active_entities 与 user_profile，保持跨轮次记忆连续。"""
    config = {"configurable": {"thread_id": f"conv_{req.conversation_id}"}}
    existing_ckpt = checkpointer.get(config) if checkpointer else None

    saved_entities = {}
    ckpt_profile = {}

    if existing_ckpt:
        if req.options.get("regenerate") is True:
            # The backend has validated the failed reply and supplied history before its USER turn.
            msgs = [RemoveMessage(id=REMOVE_ALL_MESSAGES)]
            msgs.extend(HumanMessage(content=h.content) if h.role == "USER" else AIMessage(content=h.content)
                        for h in req.history[-10:])
            msgs.append(HumanMessage(content=req.message))
        else:
            msgs = [HumanMessage(content=req.message)]
        saved_entities = existing_ckpt.get("channel_values", {}).get("active_entities") or {}
        if not req.options.get("regenerate"):
            ckpt_profile = existing_ckpt.get("channel_values", {}).get("user_profile") or {}
    else:
        msgs = []
        for h in req.history[-10:]:
            msgs.append(HumanMessage(content=h.content) if h.role == "USER" else AIMessage(content=h.content))
        msgs.append(HumanMessage(content=req.message))
        for h in reversed(req.history[-6:]):
            if h.role == "USER" and not saved_entities.get("last_category"):
                cat = category_from_user_text(h.content)
                if cat:
                    saved_entities["last_category"] = cat
            if h.role == "USER" and not saved_entities.get("budget"):
                b = budget_from_text(h.content)
                if b:
                    saved_entities["budget"] = b

    profile = resolve_profile(
        req.user_profile, ckpt_profile,
        user_history=(h.content for h in req.history if h.role == "USER"),
        current_text=req.message,
    )

    return AgentState(
        messages=msgs,
        intent=None,
        reply_route=None,
        request_decision=None,
        knowledge_query=None,
        conversation_focus=None if req.options.get("regenerate") else validated_focus(
            (existing_ckpt or {}).get("channel_values", {}).get("conversation_focus")),
        web_query=None,
        tool_loop_count=0,
        escalated=False,
        user_id=str(req.user_id),
        conversation_id=str(req.conversation_id),
        history=[h.model_dump() for h in req.history],
        summary=req.summary,
        user_profile=profile,
        long_term_memory=list(req.long_term_memory or []),
        web_search_enabled=req.web_search_enabled,
        active_entities=dict(saved_entities),
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
    background = BackgroundTasks()
    trace_id = req.options.get("trace_id")
    record = TraceRecorder(trace_id) if isinstance(trace_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", trace_id) else None

    async def extract_preferences(answer_text, status):
        with activate_trace(record):
            with trace_span("memory.preference", kind="memory", input={"message":req.message}) as span:
                await background_memory_extraction(req.user_id, req.message, answer_text)
                span.complete({"completed":True})
        if record:
            try:
                await backend_client.record_ai_trace(trace_id, record.snapshot(status))
            except Exception:
                logger.warning("failed to update background memory trace")

    async def gen():
        with activate_trace(record):
            try:
                async for item in generate():
                    yield item
            except Exception as exc:
                # Initialization can fail before the graph's own error handler starts.
                logger.warning("chat initialization failed: %s", type(exc).__name__)
                if record:
                    yield sse("trace", record.snapshot("FAILED", error=type(exc).__name__))
                yield sse("error", {"code":5001, "message":"AI 服务内部错误，请稍后重试"})

    async def generate():
        start = time.time()
        eval_enabled = req.options.get("include_eval_metadata") is True
        # 工具上下文：身份由服务端注入（越权防护红线），同时注入会话级实体记忆
        with trace_span("context.assemble", kind="context", input={"message":req.message, "history":[h.model_dump() for h in req.history],
                                                                    "summary":req.summary}) as span:
            initial_state = build_state(req, checkpointer=checkpointer)
            span.complete({"profile":initial_state.get("user_profile"), "messageCount":len(initial_state["messages"]),
                           "longTermMemory":initial_state.get("long_term_memory"), "entities":initial_state.get("active_entities")})
        ctx = {"latest_user_text": req.message, "user_id": str(req.user_id), "conversation_id": str(req.conversation_id),
               "degraded": False, "escalated": False,
               "active_entities": dict(initial_state.get("active_entities") or {})}
        set_tool_ctx(ctx)
        parts: list[str] = []
        usage: dict = {}
        output = OutputPolicy(req.message, link_guard_enabled=settings.link_guard_enabled)
        live_buffer: GuardedLinkBuffer | None = None
        streamed_length = 0
        web_prefix_pending = ""
        web_prefix_done = False
        web_source_footer = ""
        # 可观测：开启本会话 trace（session=conversation_id）
        traced = start_trace(conversation_id=req.conversation_id, user_id=req.user_id,
                             metadata={"message": _short(req.message, 200), "trace_id": trace_id or ""})
        timed_out = False
        try:
            final_state: dict | None = None
            tool_spans: dict[str, object] = {}
            try:
                # 总请求超时保护：超过 chat_timeout_s 秒强制终止图运行；recursion_limit 限制图递归深度
                async with (
                    asyncio.timeout(settings.chat_timeout_s),
                    aclosing(graph.astream_events(
                        initial_state,
                        config={
                            "recursion_limit": settings.agent_recursion_limit,
                            "configurable": {"thread_id": f"conv_{req.conversation_id}"},
                        },
                        version="v2",
                    )) as events,
                ):
                    async for ev in events:
                        # 客户端断连：取消剩余图执行，停止产出
                        if await request.is_disconnected():
                            logger.info("client disconnected, cancelling graph")
                            end_trace(output={"cancelled": True})
                            return
                        if record:
                            try:
                                record.observe(ev)
                            except Exception:
                                logger.warning("execution trace event omitted")
                        kind = ev["event"]
                        if kind == "on_chat_model_stream":
                            # 意图识别节点的输出不面向用户，跳过
                            if (ev.get("metadata") or {}).get("langgraph_node") == "intent_router":
                                continue
                            chunk = ev["data"].get("chunk")
                            content = getattr(chunk, "content", "")
                            tool_chunks = getattr(chunk, "tool_call_chunks", None)
                            if isinstance(content, str) and content and not tool_chunks:
                                node = (ev.get("metadata") or {}).get("langgraph_node")
                                if (node == "web_answer" and not web_prefix_done and not output.policy_required
                                        and not output.rag_started and not ctx.get("rag_used")):
                                    web_prefix_pending += content
                                    candidate = re.sub(r"^\s*#{1,6}\s*", "", web_prefix_pending.lstrip())
                                    if "【联网搜索】".startswith(candidate.strip()):
                                        # Hold a possible model-supplied label until substantive output arrives.
                                        continue
                                    body = candidate[len("【联网搜索】"):].lstrip() if candidate.startswith("【联网搜索】") else web_prefix_pending
                                    content = "【联网搜索】\n" + body
                                    web_prefix_done = True
                                parts.append(content)
                                if output.can_stream(node, ctx):
                                    if live_buffer is None:
                                        live_buffer = GuardedLinkBuffer(output.known_ids, settings.link_guard_enabled)
                                        safe_text = live_buffer.push("".join(parts))
                                    else:
                                        safe_text = live_buffer.push(content)
                                    if safe_text:
                                        streamed_length += len(safe_text)
                                        yield sse("token", {"content": safe_text})
                            um = getattr(chunk, "usage_metadata", None)
                            if um:
                                usage = {"promptTokens": um.get("input_tokens", 0),
                                         "completionTokens": um.get("output_tokens", 0)}
                        elif kind == "on_tool_start":
                            if ev.get("name") in {"kb_search", "web_search"}:
                                parts.clear()
                            output.tool_started(ev["name"])
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
                            if ev.get("name") == "kb_search" and not output.rag_started:
                                parts.clear()
                            out = ev["data"].get("output")
                            raw_result = getattr(out, "content", out)
                            if isinstance(raw_result, str):
                                try:
                                    raw_result = json.loads(raw_result)
                                except (ValueError, TypeError):
                                    raw_result = None
                            output.tool_completed(ev["name"], raw_result)
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
                        elif (kind == "on_chain_end" and ev.get("name") == "web_answer"
                              and not output.policy_required and not output.rag_started and not ctx.get("rag_used")):
                            node_output = ev["data"].get("output")
                            messages = node_output.get("messages") if isinstance(node_output, dict) else None
                            if messages:
                                footer = (getattr(messages[-1], "additional_kwargs", {}) or {}).get("web_source_footer")
                                if isinstance(footer, str):
                                    web_source_footer = footer
                        elif kind == "on_chain_end" and ev.get("name") == "LangGraph":
                            # 捕获图最终状态（非流式节点如 escalate_node 的回复兜底）
                            final_state = ev["data"].get("output")
            except TimeoutError:
                logger.warning("chat stream timed out after %ss, forcing finish", settings.chat_timeout_s)
                timed_out = True

            if timed_out:
                # A timeout is a failed turn, not a successful generated answer containing error copy.
                for action in ctx.get("actions", []):
                    yield sse("action", action)
                end_trace(output={"error": "timeout", "latencyMs": int((time.time() - start) * 1000)})
                if record:
                    yield sse("trace", record.snapshot("FAILED", error="request timeout"))
                yield sse("error", {"code": 5002, "message": "回复等待超时"})
                return

            # 知识节点使用整理后的终稿；其他非流式节点仅在无 token 时兜底。
            final_text = "".join(parts)
            if final_state:
                msgs = final_state.get("messages") if isinstance(final_state, dict) else None
                if msgs:
                    for m in reversed(msgs):
                        content = getattr(m, "content", "")
                        if getattr(m, "type", "") == "ai" and isinstance(content, str) and content:
                            # A knowledge node renders structured model output and owns its
                            # citations. Never substitute its internal streamed JSON draft.
                            rendered = (getattr(m, "additional_kwargs", {}) or {}).get("knowledge_answer_final")
                            if not final_text or rendered is True:
                                final_text = content
                            break
            final_text = _timeout_fallback(final_text, timed_out)
            with trace_span("output.validate", kind="guard", input={"draft":final_text,
                            "policyRequired":output.policy_required, "allowedCitations":ctx.get("rag_allowed_citations")}) as span:
                answer = output.finalize(final_text, ctx, web_footer=web_source_footer)
                span.complete({"content":answer.content, "citationRequired":answer.citation_required,
                               "citations":answer.citations, "changed":answer.content != final_text})
            guarded = answer.content
            end_trace(output={"content": _short(guarded, 300), "latencyMs": int((time.time() - start) * 1000),
                              "traceId": get_trace_id()})
            for action in ctx.get("actions", []):
                yield sse("action", action)
            if live_buffer is not None:
                # Already emitted the safe prefix; only flush the held link/text suffix.
                remainder = guarded[streamed_length:]
                if remainder:
                    yield sse("token", {"content": remainder})
            elif answer.rag_used:
                yield sse("token", {"content": guarded})
            else:
                streamed_parts = parts if "".join(parts) == guarded else [guarded]
                for part in streamed_parts:
                    yield sse("token", {"content": part})
            done = {
                "content": guarded,
                "tokenUsage": usage,
                "latencyMs": int((time.time() - start) * 1000),
                "degraded": bool(ctx.get("degraded")),
                "timedOut": timed_out,
                **_done_eval_metadata(final_state, eval_enabled),
            }
            if answer.citation_required:
                done["citations"] = list(answer.citations)
            with trace_span("memory.identity", kind="memory") as span:
                memory_saved = await persist_naming_memory(req.user_id, req.message)
                span.complete({"saved":memory_saved}, status="SKIPPED" if memory_saved is None else "SUCCESS" if memory_saved else "FAILED")
            if memory_saved is not None:
                done["memorySaved"] = memory_saved
            elif req.user_id > 0 and should_extract_memory(req.message):
                background.add_task(extract_preferences, guarded, "DEGRADED" if ctx.get("degraded") else "SUCCESS")
            done["latencyMs"] = int((time.time() - start) * 1000)
            if record:
                yield sse("trace", record.snapshot("DEGRADED" if ctx.get("degraded") else "SUCCESS"))
            yield sse("done", done)
        except Exception as e:
            logger.exception("chat stream error: %s", e)
            end_trace(output={"error": str(e)})
            if record:
                yield sse("trace", record.snapshot("FAILED", error=type(e).__name__))
            yield sse("error", {"code": 5001, "message": "AI 服务内部错误，请稍后重试"})

    return StreamingResponse(
        gen(),
        background=background,
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

