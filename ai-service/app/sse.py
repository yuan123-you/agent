"""SSE 事件构造：事件 token/tool_call/tool_result/action/error/done"""
import json


def sse(event: str, data: dict) -> str:
    """构造一条 SSE 事件（data 为单行 JSON）"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

