"""Exercise framework-injected ToolCall IDs in preparation-tool unit tests."""
import json

async def invoke_preparation(tool, args):
    result = await tool.ainvoke({"name": tool.name, "args": args,
                                "id": "unit-call-id", "type": "tool_call"})
    return json.loads(result.content)
