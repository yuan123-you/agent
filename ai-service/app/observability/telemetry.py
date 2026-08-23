"""Langfuse 全链路追踪封装：意图 / 工具 / RAG / 生成四类节点打点。

- 默认不开启（settings.langfuse_enabled=False），此时全部 API 为 no-op，零开销、不影响测试。
- 开启后每个会话请求形成一条 trace（session_id=conversation_id，user_id 绑定到人），
  其中按 ```意图(generation) → [工具(span) → RAG(retrieval) 嵌套] × N → 生成(generation)``` 形成观察树。
- 通过 contextvars 维护当前 parent observation，保证异步工具/检索能正确嵌套在所属工具 span 之下。
"""
from __future__ import annotations

import contextvars
import logging
from functools import wraps

from app.config import settings

logger = logging.getLogger("ai-service.telemetry")

# 当前请求的 trace 与当前 observation 上下文（仅开启时使用）
_trace_ctx: contextvars.ContextVar[dict | None] = contextvars.ContextVar("lf_trace", default=None)
_parent_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("lf_parent", default=None)


def tracing_enabled() -> bool:
    return settings.langfuse_enabled


def _client():
    from langfuse import Langfuse

    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
        release=settings.langfuse_release,
    )


def start_trace(*, conversation_id, user_id, metadata=None) -> bool:
    """请求级 trace：一个会话的一轮对话 = 一条 trace。返回是否开启。"""
    if not tracing_enabled():
        return False
    try:
        trace = _client().start_trace(
            name="chat_turn",
            session_id=str(conversation_id),
            user_id=str(user_id),
            input=metadata or {},
        )
        _trace_ctx.set({"trace": trace, "client": _client()})
        _parent_ctx.set(None)
        return True
    except Exception as e:  # 打点失败绝不影响主流程
        _reset()
        logger.warning("langfuse start_trace failed: %s", e)
        return False


def end_trace(output=None) -> None:
    if not tracing_enabled():
        return
    ctx = _trace_ctx.get()
    if not ctx:
        return
    try:
        ctx["trace"].end(output=output)
        ctx["client"].flush()
    except Exception as e:
        logger.warning("langfuse end_trace failed: %s", e)
    finally:
        _reset()


def _reset() -> None:
    _trace_ctx.set(None)
    _parent_ctx.set(None)


def _trace():
    ctx = _trace_ctx.get()
    return ctx["trace"] if ctx else None


def _current_parent() -> str | None:
    return _parent_ctx.get()


# ---------------------------------------------------------------- 生成打点
async def generation(name: str, *, model: str, input_data=None, usage=None, tags=None) -> None:
    """生成节点（意图/回复）打点：span 级别 generation，附带 token 用量。"""
    if not tracing_enabled():
        return
    trace = _trace()
    if not trace:
        return
    try:
        span = trace.observation(
            name=name,
            type="GENERATION",
            model=model,
            input=input_data,
            metadata={"tags": tags or []},
            parent_observation_id=_current_parent(),
        )
        span.end(output=usage or {})
    except Exception as e:
        logger.warning("langfuse generation failed: %s", e)


# ---------------------------------------------------------------- 工具打点
def tool_span(name: str, input_data=None) -> _ToolSpan:
    """工具节点打点：chat 流的 on_tool_start/on_tool_end 之间创建 span。"""
    return _ToolSpan(name, input_data)


class _ToolSpan:
    def __init__(self, name: str, input_data=None):
        self.name = name
        self.input = input_data
        self.span = None
        self.output = None

    def __enter__(self) -> _ToolSpan:
        trace = _trace()
        if trace:
            try:
                self.span = trace.span(name=f"tool::{self.name}", input=self.input,
                                       parent_observation_id=_current_parent())
            except Exception as e:
                logger.warning("langfuse tool_span start failed: %s", e)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.span is not None:
            try:
                self.span.end(output={"error": str(exc)} if exc else self.output)
            except Exception:
                pass
        return False

    def complete(self, output=None):
        self.output = output


# ---------------------------------------------------------------- RAG 打点
def observe_retrieval(name: str = "rag::search"):
    """检索函数装饰器：按 ```RAG``` 观察类型打点，输出命中统计。"""
    def deco(fn):
        if not tracing_enabled():
            return fn

        @wraps(fn)
        async def wrapper(*args, **kwargs):
            trace = _trace()
            if not trace:
                return await fn(*args, **kwargs)
            span = None
            try:
                span = trace.observation(
                    name=name,
                    type="SPAN",
                    input={"query": kwargs.get("query") or (args[0] if args else None)},
                    parent_observation_id=_current_parent(),
                )
                result = await fn(*args, **kwargs)
                if isinstance(result, dict):
                    span.end(output={
                        "total": result.get("total", 0),
                        "hits": result.get("hits", []),
                        "metric": "hits",
                    })
                else:
                    span.end(output={"result": result})
                return result
            except Exception as e:
                if span is not None:
                    try:
                        span.end(output={"error": str(e)})
                    except Exception:
                        pass
                raise
        return wrapper
    return deco


def span_ctx(name: str, **kw):
    """普通 span 上下文管理器（装饰器无法覆盖处兜底）。"""
    class _Ctx:
        def __enter__(self):
            trace = _trace()
            self.span = trace.span(name=name, **kw) if trace else None
            return self

        def __exit__(self, exc_type, exc, tb):
            if self.span is not None:
                try:
                    self.span.end(output={"error": str(exc)} if exc else kw.get("output"))
                except Exception:
                    pass
            return False

    return _Ctx()


def get_trace_id() -> str | None:
    trace = _trace()
    return getattr(trace, "id", None) if trace else None