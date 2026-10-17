"""AgentState：请求级与会话级状态（支持 Checkpointer 持久化与跨轮次记忆）"""
from typing import Annotated, Any, TypedDict

from langgraph.graph import add_messages


class AgentState(TypedDict):
    # ── 会话上下文（网关传入）──
    user_id: str
    conversation_id: str
    history: list[dict]          # [{"role": "USER"|"AI", "content": ...}]
    summary: str | None          # 网关维护的历史摘要
    web_search_enabled: bool     # 联网搜索开关（前端）

    # ── 图运行时与会话记忆状态 ──
    messages: Annotated[list[Any], add_messages]   # 会话级消息通道（含工具调用与结果，自动追加）
    intent: str | None
    tool_loop_count: int
    escalated: bool
    active_entities: dict | None  # 会话级实体记忆（品类偏好、最近推荐商品列表、最近订单号等）
