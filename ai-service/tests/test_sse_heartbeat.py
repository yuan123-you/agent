import asyncio
from contextvars import ContextVar
import pytest
from app.api.streaming import with_heartbeats


async def test_slow_stream_gets_keepalive_without_cancelling_source():
    release=asyncio.Event()
    async def source():
        yield 'first'
        await release.wait()
        yield 'last'
    stream=with_heartbeats(source(),interval_s=.005)
    assert await anext(stream)=='first'
    assert (await anext(stream)).startswith('event: ping\n')
    release.set()
    assert [item async for item in stream]==['last']


async def test_source_context_remains_in_one_task_and_closes_on_disconnect():
    marker=ContextVar('test_sse_owner',default='outside')
    closed=asyncio.Event()
    async def source():
        token=marker.set('inside')
        try:
            yield 'first'
            await asyncio.Event().wait()
        finally:
            marker.reset(token)
            closed.set()
    stream=with_heartbeats(source(),interval_s=.005)
    assert await anext(stream)=='first'
    await stream.aclose()
    assert closed.is_set() and marker.get()=='outside'


async def test_producer_is_backpressured_and_not_buffered_without_bound():
    produced=[]
    async def source():
        for i in range(100):
            produced.append(i)
            yield str(i)
    stream=with_heartbeats(source(),interval_s=.1)
    assert await anext(stream)=='0'
    await asyncio.sleep(.01)
    assert len(produced)<=3
    await stream.aclose()


async def test_source_error_is_propagated_not_serialized_into_customer_events():
    async def source():
        yield 'first'
        raise RuntimeError('PRIVATE_PROVIDER_DETAIL')
    stream=with_heartbeats(source(),interval_s=.005)
    assert await anext(stream)=='first'
    with pytest.raises(RuntimeError,match='PRIVATE_PROVIDER_DETAIL'):
        await anext(stream)


async def test_source_self_cancellation_is_not_turned_into_endless_pings():
    async def source():
        if False:yield ''
        raise asyncio.CancelledError
    stream=with_heartbeats(source(),interval_s=.005)
    with pytest.raises(asyncio.CancelledError):
        await anext(stream)


async def test_heartbeat_interval_must_be_positive():
    async def source():
        yield 'unused'
    with pytest.raises(ValueError):
        await anext(with_heartbeats(source(),interval_s=0))

async def test_chat_disconnect_closes_nested_graph_in_the_owning_context(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.api import chat
    marker=ContextVar('test_graph_owner',default='outside')
    closed=asyncio.Event()
    class Graph:
        async def astream_events(self,*args,**kwargs):
            token=marker.set('graph')
            try:
                yield {'event':'on_tool_end','name':'order_query','run_id':'q','data':{'output':{}}}
                await asyncio.Event().wait()
            finally:
                marker.reset(token)
                closed.set()
    class Request:
        async def is_disconnected(self):return False
    monkeypatch.setattr(chat,'graph',Graph())
    monkeypatch.setattr(chat,'checkpointer',None)
    monkeypatch.setattr(chat,'start_trace',lambda **kw:False)
    monkeypatch.setattr(chat,'end_trace',lambda **kw:None)
    monkeypatch.setattr(chat,'background_memory_extraction',AsyncMock())
    response=await chat.chat_stream(chat.ChatRequest(user_id=1,conversation_id=1,message='查一下订单'),Request())
    await anext(response.body_iterator)
    await response.body_iterator.aclose()
    assert closed.is_set() and marker.get()=='outside'

@pytest.mark.parametrize("asgi_version", ["2.3", "2.4"])
async def test_real_asgi_disconnect_closes_source_even_during_body_send(asgi_version):
    from starlette.requests import ClientDisconnect
    entered_send = asyncio.Event()
    closed = asyncio.Event()
    async def source():
        try:
            yield "first"
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(.02)
            closed.set()
    async def send(message):
        if message["type"] == "http.response.body" and message.get("body"):
            entered_send.set()
            if asgi_version == "2.4":
                raise OSError("disconnected")
            await asyncio.Event().wait()
    async def receive():
        await entered_send.wait()
        return {"type": "http.disconnect"}
    from app.api.streaming import ClosingStreamingResponse
    response = ClosingStreamingResponse(with_heartbeats(source(), interval_s=.01))
    try:
        await response({"type": "http", "asgi": {"spec_version": asgi_version}}, receive, send)
    except ClientDisconnect:
        pass
    try:
        assert closed.is_set()
        assert not [task for task in asyncio.all_tasks()
                    if task.get_name() == "sse-event-producer" and not task.done()]
    finally:
        await response.body_iterator.aclose()

async def test_anyio_disconnect_cancellation_does_not_interrupt_awaited_source_cleanup():
    import anyio
    ready = asyncio.Event()
    closed = asyncio.Event()
    async def source():
        try:
            ready.set()
            await asyncio.Event().wait()
            yield "unused"
        finally:
            await asyncio.sleep(.02)
            closed.set()
    async def consume():
        async for item in with_heartbeats(source(), interval_s=1):
            pass
    async with anyio.create_task_group() as group:
        group.start_soon(consume)
        await ready.wait()
        group.cancel_scope.cancel()
    assert closed.is_set()
