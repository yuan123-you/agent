"""AgentState：请求级内存状态（服务无状态，上下文由后端每轮传入）"""
from typing import Annotated, Any, TypedDict

from langgraph.graph import add_messages


class AgentState(TypedDict):
    # ── 会话上下文（网关传入）──
    user_id: str
    conversation_id: str
    history: list[dict]          # [{"role": "USER"|"AI", "content": ...}]
    summary: str | None          # 网关维护的历史摘要
    web_search_enabled: bool     # 联网搜索开关（前端）

    # ── 图运行时状态 ──
    messages: Annotated[list[Any], add_messages]   # 本轮消息通道（含工具消息）
    intent: str | None
    tool_loop_count: int
    escalated: bool
