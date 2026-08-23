"""工具上下文（ContextVar）与可观测性 no-op 行为。"""
import pytest

from app.config import settings
from app.tools.tools import get_tool_ctx, set_tool_ctx
from app.observability import telemetry


def test_tool_ctx_roundtrip():
    set_tool_ctx({"user_id": "42", "conversation_id": "7"})
    ctx = get_tool_ctx()
    assert ctx["user_id"] == "42"
    assert ctx["conversation_id"] == "7"


def test_tool_ctx_default():
    from app.tools.tools import get_tool_ctx, set_tool_ctx
    set_tool_ctx({})  # 复位，避免 ContextVar 跨用例残留
    assert get_tool_ctx() == {}


def test_tracing_disabled_noop():
    from app.config import settings
    from app.observability import telemetry
    telemetry._reset()
    if settings.langfuse_enabled:
        pytest.skip("tracing enabled in env")
    # 关闭时不应触发 langfuse 依赖
    assert telemetry.start_trace(conversation_id=1, user_id=1) is False


def test_tracing_generation_stub_runs_when_disabled():
    # 关闭时各打点函数应静默通过
    import asyncio
    from app.observability import telemetry
    telemetry._reset()
    asyncio.run(telemetry.generation("intent", model="m", input_data=None, usage=None))