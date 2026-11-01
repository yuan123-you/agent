import asyncio,json
import httpx,pytest
from fastapi import FastAPI
from starlette.responses import StreamingResponse
from app.request_budget import RequestBudgetMiddleware
from app.resilience import budget_headers,current_budget

@pytest.mark.asyncio
async def test_ingress_clips_untrusted_extension_and_keeps_zero_retry_budget():
    app=FastAPI();app.add_middleware(RequestBudgetMiddleware,timeout_s=.1,action_timeout_s=.05,retry_tokens=2)
    @app.post('/v1/test')
    async def endpoint():return budget_headers()
    async with httpx.AsyncClient(base_url='http://test',transport=httpx.ASGITransport(app=app)) as c:
        response=await c.post('/v1/test',headers={'X-Request-Timeout-Ms':'999999','X-Request-Retry-Budget':'99'})
        assert 0<int(response.json()['X-Request-Timeout-Ms'])<=100
        assert response.json()['X-Request-Retry-Budget']=='2'
        response=await c.post('/v1/test',headers={'X-Request-Retry-Budget':'0'})
        assert response.json()['X-Request-Retry-Budget']=='0'
    assert current_budget() is None

@pytest.mark.asyncio
async def test_expired_or_invalid_ingress_never_reaches_business_code():
    calls=[];app=FastAPI();app.add_middleware(RequestBudgetMiddleware)
    @app.post('/v1/test')
    async def endpoint():calls.append(1);return {}
    async with httpx.AsyncClient(base_url='http://test',transport=httpx.ASGITransport(app=app)) as c:
        assert (await c.post('/v1/test',headers={'X-Request-Timeout-Ms':'0'})).status_code==503
        assert (await c.post('/v1/test',headers={'X-Request-Timeout-Ms':'NaN'})).status_code==400
        assert (await c.post('/v1/test',headers={'X-Request-Retry-Budget':'-1'})).status_code==400
    assert calls==[]

@pytest.mark.asyncio
async def test_stream_deadline_does_not_reset_when_tokens_keep_arriving():
    calls=[];app=FastAPI();app.add_middleware(RequestBudgetMiddleware,timeout_s=.04)
    @app.post('/v1/stream')
    async def endpoint():
        calls.append(1)
        async def body():
            while True:
                yield b'event: token\ndata: partial\n\n';await asyncio.sleep(.01)
        return StreamingResponse(body(),media_type='text/event-stream')
    async with httpx.AsyncClient(base_url='http://test',transport=httpx.ASGITransport(app=app)) as c:
        response=await asyncio.wait_for(c.post('/v1/stream'),timeout=.5)
    assert response.status_code==200 and 'event: error' in response.text
    assert 'event: done' not in response.text and calls==[1]

@pytest.mark.asyncio
async def test_regular_deadline_returns_failure_instead_of_late_success():
    app=FastAPI();app.add_middleware(RequestBudgetMiddleware,timeout_s=.02)
    @app.post('/v1/test')
    async def endpoint():await asyncio.sleep(1);return {'success':True}
    async with httpx.AsyncClient(base_url='http://test',transport=httpx.ASGITransport(app=app)) as c:
        response=await c.post('/v1/test')
    assert response.status_code==503 and 'success' not in response.json()

@pytest.mark.asyncio
async def test_finished_response_does_not_cancel_a_separately_budgeted_background_job():
    from starlette.background import BackgroundTask
    from starlette.responses import JSONResponse
    from app.resilience import budget_scope
    completed=[];app=FastAPI();app.add_middleware(RequestBudgetMiddleware,timeout_s=.03)
    async def job():
        with budget_scope(.2,inherit=False):
            await asyncio.sleep(.06);completed.append(1)
    @app.post('/v1/test')
    async def endpoint():return JSONResponse({'accepted':True},background=BackgroundTask(job))
    async with httpx.AsyncClient(base_url='http://test',transport=httpx.ASGITransport(app=app)) as c:
        response=await c.post('/v1/test')
    assert response.json()=={'accepted':True} and completed==[1]

@pytest.mark.asyncio
async def test_cancellation_suppression_cannot_turn_expired_request_into_success():
    app=FastAPI();app.add_middleware(RequestBudgetMiddleware,timeout_s=.02)
    @app.post('/v1/test')
    async def endpoint():
        try:await asyncio.sleep(1)
        except asyncio.CancelledError:pass
        return {'late_success':True}
    async with httpx.AsyncClient(base_url='http://test',transport=httpx.ASGITransport(app=app)) as c:
        response=await c.post('/v1/test')
    assert response.status_code==503 and 'late_success' not in response.json()
