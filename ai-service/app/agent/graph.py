"""主图构建：StateGraph（LangGraph 1.x）+ 会话级 Checkpointer 持久化（支持 SQLite 本地持久化与 MemorySaver 自动回退）
START → intent_router → (agent ⇄ tools 循环 | small_talk | escalate_node) → END
"""
import logging
import sqlite3
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.agent.nodes import (
    END_FLAG,
    FINALIZE_FLAG,
    agent_node,
    escalate_node,
    finalize_without_tools,
    intent_router_node,
    route_by_intent,
    route_after_tools,
    web_answer_node,
    should_continue,
    small_talk_node,
)
from app.agent.state import AgentState
from app.config import settings
from app.tools.tools import ALL_TOOLS

logger = logging.getLogger("ai-service.agent")

import asyncio

try:
    from langgraph.checkpoint.sqlite import SqliteSaver

    class HybridSqliteSaver(SqliteSaver):
        """异步与同步双兼容的 SQLite Checkpointer：桥接 aget_tuple/aput/aput_writes，
        支持 async astream_events 与同步 get 调用，并在本地 SQLite 文件中持久化会话。"""
        async def aget_tuple(self, config):
            return await asyncio.to_thread(self.get_tuple, config)

        async def aput(self, config, checkpoint, metadata, new_versions):
            return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

        async def aput_writes(self, config, writes, task_id, task_path=""):
            return await asyncio.to_thread(self.put_writes, config, writes, task_id, task_path)

        async def alist(self, config=None, *, filter=None, before=None, limit=None):
            def _get_list():
                return list(self.list(config, filter=filter, before=before, limit=limit))
            items = await asyncio.to_thread(_get_list)
            for item in items:
                yield item

        async def adelete_thread(self, thread_id: str):
            return await asyncio.to_thread(self.delete_thread, thread_id)

    _HAS_SQLITE_SAVER = True
except ImportError:
    _HAS_SQLITE_SAVER = False


def init_checkpointer():
    """初始化会话 Checkpointer：优先使用本地 SQLite 数据库持久化，异常或未安装时平滑降级为 MemorySaver"""
    path = settings.checkpoint_sqlite_path
    if not path or path == ":memory:" or not _HAS_SQLITE_SAVER:
        if path and not _HAS_SQLITE_SAVER:
            logger.warning("langgraph-checkpoint-sqlite not available, using MemorySaver")
        return MemorySaver()
    try:
        db_path = Path(path)
        if not db_path.is_absolute():
            root = Path(__file__).resolve().parent.parent.parent
            db_path = root / path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        saver = HybridSqliteSaver(conn)
        saver.setup()
        logger.info("Initialized HybridSqliteSaver checkpointer at %s", db_path)
        return saver
    except Exception as e:
        logger.warning("SqliteSaver init failed, fallback to MemorySaver: %s", e)
        return MemorySaver()


# 全局会话 Checkpointer（按 thread_id 持久化会话状态快照）
checkpointer = init_checkpointer()


def build_graph(cp=None):
    if cp is None:
        cp = checkpointer
    builder = StateGraph(AgentState)

    builder.add_node("intent_router", intent_router_node)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(ALL_TOOLS))
    builder.add_node("small_talk", small_talk_node)
    builder.add_node("web_answer", web_answer_node)
    builder.add_node("escalate_node", escalate_node)
    builder.add_node("finalize_without_tools", finalize_without_tools)

    builder.add_edge(START, "intent_router")
    builder.add_conditional_edges(
        "intent_router",
        route_by_intent,
        {"small_talk": "small_talk", "escalate_node": "escalate_node", "agent": "agent"},
    )
    builder.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "finalize_without_tools": "finalize_without_tools", END_FLAG: END},
    )
    builder.add_conditional_edges("tools", route_after_tools, {"agent": "agent", "web_answer": "web_answer"})
    builder.add_edge("web_answer", END)
    builder.add_edge("small_talk", END)
    builder.add_edge("escalate_node", END)
    builder.add_edge("finalize_without_tools", END)

    return builder.compile(checkpointer=cp)


# 编译后的图（模块级单例，挂载 Checkpointer）
graph = build_graph()
