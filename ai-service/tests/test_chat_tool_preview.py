import json

import pytest
from langchain_core.messages import ToolMessage

from app.api.chat import _tool_result_preview


def tool_message(name: str, content: object) -> ToolMessage:
    return ToolMessage(
        content=json.dumps(content, ensure_ascii=False),
        name=name,
        tool_call_id="call_123",
    )


@pytest.mark.parametrize(
    ("name", "content", "expected"),
    [
        (
            "product_search",
            {"products": [
                {"name": "星云手机", "price": 2999},
                {"name": "轻羽手机", "price": 3999},
            ], "total": 2},
            "找到 2 件商品：星云手机（¥2999）、轻羽手机（¥3999）",
        ),
        (
            "product_detail",
            {"name": "星云手机", "price": 2999, "stock": 12, "sellingPoints": "夜景拍摄"},
            "星云手机 · ¥2999 · 库存 12 件\n卖点：夜景拍摄",
        ),
        (
            "order_create",
            {"actionId": "act_1", "receiverPhone": "13800000000", "status": "PENDING_CONFIRMATION"},
            "已生成待确认订单，请在下方确认卡片中核对信息",
        ),
        (
            "order_query",
            {"orders": [{"orderNo": "ORD-88", "statusText": "待发货"}]},
            "找到 1 个订单：ORD-88 · 待发货",
        ),
        (
            "kb_search",
            {"hits": [{"source": "退换货条款"}, {"source": "退换货条款"}]},
            "找到 2 条相关资料：退换货条款",
        ),
        (
            "web_search",
            {"results": [{"title": "新品发布"}]},
            "找到 1 条网络结果：新品发布",
        ),
        (
            "escalate_to_human",
            {"success": True},
            "已提交人工客服转接请求",
        ),
    ],
)
def test_tool_result_preview_unwraps_tool_messages_and_formats_business_results(name, content, expected):
    assert _tool_result_preview(tool_message(name, content)) == {"preview": expected}


def test_tool_result_preview_does_not_leak_unknown_tool_protocol_metadata():
    result = _tool_result_preview(tool_message("future_tool", {"secret": "internal", "ok": True}))

    assert result == {"preview": "工具执行完成"}
    assert "tool_call_id" not in result["preview"]
    assert "future_tool" not in result["preview"]


def test_tool_result_preview_keeps_plain_human_readable_results():
    message = ToolMessage(content="已成功转接人工客服", name="escalate_to_human", tool_call_id="call_456")

    assert _tool_result_preview(message) == {"preview": "已成功转接人工客服"}
