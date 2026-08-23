import pytest

from app.clients.backend_client import backend_client
from app.tools.tools import order_create, set_tool_ctx


@pytest.mark.asyncio
async def test_order_create_prepares_pending_action_without_confirming(monkeypatch):
    calls = []

    async def fake_prepare(**kwargs):
        calls.append(kwargs)
        return {
            "actionId": "act_123",
            "productName": "云感枕",
            "quantity": 2,
            "unitPrice": 49.9,
            "amount": 99.8,
            "receiverName": "张三",
            "receiverPhone": "13800138000",
            "receiverAddress": "浙江省杭州市西湖区文三路90号",
            "expiresAt": "2026-08-23T09:10:00Z",
        }

    monkeypatch.setattr(backend_client, "order_prepare", fake_prepare, raising=False)
    async def forbidden(*args, **kwargs):
        raise AssertionError("order confirmation must not be called by the model tool")
    monkeypatch.setattr(backend_client, "order_confirm", forbidden, raising=False)
    set_tool_ctx({"user_id": 7, "conversation_id": 9})

    result = await order_create.ainvoke({"product_id": 11, "quantity": 2})

    assert result["actionId"] == "act_123"
    assert result["status"] == "PENDING_CONFIRMATION"
    assert calls == [{
        "user_id": 7,
        "conversation_id": 9,
        "product_id": 11,
        "quantity": 2,
        "receiver_name": "",
        "receiver_phone": "",
        "receiver_address": "",
    }]

@pytest.mark.asyncio
async def test_prepared_order_is_queued_for_standalone_action_event(monkeypatch):
    action = {
        "actionId": "act_456", "productName": "云感枕", "quantity": 1,
        "unitPrice": 49.9, "amount": 49.9, "receiverName": "张三",
        "receiverPhone": "13800138000", "receiverAddress": "浙江省杭州市西湖区文三路90号",
        "expiresAt": "2026-08-23T09:10:00Z",
    }

    async def fake_prepare(**kwargs):
        return dict(action)

    monkeypatch.setattr(backend_client, "order_prepare", fake_prepare)
    context = {"user_id": 7, "conversation_id": 9}
    set_tool_ctx(context)

    await order_create.ainvoke({"product_id": 11})

    assert context["actions"] == [{"type": "ORDER_CREATE", **action}]


def test_action_sse_is_a_named_structured_event():
    import json
    from app.sse import sse

    raw = sse("action", {"type": "ORDER_CREATE", "actionId": "act_456", "amount": 49.9})

    assert raw.startswith("event: action\n")
    payload = json.loads(raw.split("data: ", 1)[1])
    assert payload == {"type": "ORDER_CREATE", "actionId": "act_456", "amount": 49.9}
