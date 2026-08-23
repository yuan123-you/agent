"""主图构建：StateGraph（LangGraph 1.x）
START → intent_router → (agent ⇄ tools 循环 | small_talk | escalate_node) → END
"""
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.agent.nodes import END_FLAG, FINALIZE_FLAG, agent_node, escalate_node, finalize_without_tools, intent_router_node, route_by_intent, should_continue, small_talk_node
from app.agent.state import AgentState
from app.tools.tools import ALL_TOOLS


def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("intent_router", intent_router_node)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(ALL_TOOLS))
    builder.add_node("small_talk", small_talk_node)
    builder.add_node("escalate_node", escalate_node)
    builder.add_node("finalize_without_tools", finalize_without_tools)

    builder.add_edge(START, "intent_router")
    builder.add_conditional_edges(
        "intent_router", route_by_intent,
        {"agent": "agent", "small_talk": "small_talk", "escalate_node": "escalate_node"},
    )
    # 工具循环：agent 需要工具 → tools → 回到 agent；打满 → 强制收敛小结；信息足够 → 结束
    builder.add_conditional_edges(
        "agent", should_continue,
        {"tools": "tools", FINALIZE_FLAG: "finalize_without_tools", END_FLAG: END},
    )
    builder.add_edge("tools", "agent")
    builder.add_edge("small_talk", END)
    builder.add_edge("escalate_node", END)
    builder.add_edge("finalize_without_tools", END)

    return builder.compile()


# 编译后的图（模块级单例）
graph = build_graph()
