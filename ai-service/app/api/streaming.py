"""SSE keepalives with bounded buffering and request-context-safe cancellation."""
import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import aclosing

import anyio
from starlette.responses import StreamingResponse
from starlette.types import Receive, Scope, Send


async def with_heartbeats(source: AsyncGenerator[str, None], *, interval_s: float = 15) -> AsyncIterator[str]:
    if interval_s <= 0:
        raise ValueError('heartbeat interval must be positive')
    queue: asyncio.Queue[object] = asyncio.Queue(maxsize=1)
    finished = object()
    consumed = asyncio.Event()

    async def produce() -> None:
        # One task owns every anext/aclose: ContextVar tokens must never cross tasks.
        try:
            async with aclosing(source):
                async for event in source:
                    consumed.clear()
                    await queue.put(event)
                    await consumed.wait()
        except Exception as error:
            await queue.put(error)
        else:
            await queue.put(finished)

    producer = asyncio.create_task(produce(), name='sse-event-producer')
    try:
        while True:
            if producer.done() and queue.empty():
                await producer  # Preserve source cancellation instead of emitting endless pings.
                return
            try:
                event = await asyncio.wait_for(queue.get(), timeout=interval_s)
            except TimeoutError:
                if producer.done() and queue.empty():
                    await producer
                    return
                yield 'event: ping\ndata: {}\n\n'
                continue
            if event is finished:
                return
            if isinstance(event, Exception):
                raise event
            if not isinstance(event, str):
                raise TypeError("SSE source yielded a non-string event")
            yield event
            consumed.set()
    finally:
        # ASGI 2.3 disconnects use level cancellation; do not cancel awaited
        # graph/provider finalizers a second time while joining their owner.
        with anyio.CancelScope(shield=True):
            producer.cancel()
            await asyncio.gather(producer, return_exceptions=True)


class ClosingStreamingResponse(StreamingResponse):
    """Close an async body even when send() disconnects at a suspended yield."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            with anyio.CancelScope(shield=True):
                await self.body_iterator.aclose()
