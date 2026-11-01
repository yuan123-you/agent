"""Retry engineering contracts; deterministic faults, never live model accuracy."""
import asyncio
from email.utils import formatdate
import httpx
import pytest
from app import resilience as r

@pytest.mark.asyncio
@pytest.mark.parametrize('status,retry',[ (400,False),(401,False),(403,False),(404,False),(409,False),(422,False),(408,True),(429,True),(500,True),(501,False),(502,True),(503,True),(504,True)])
async def test_http_failure_classification_and_one_owner(monkeypatch,status,retry):
    calls=[]
    monkeypatch.setattr(r.random,'uniform',lambda low,high:0)
    async def call(timeout):
        calls.append(timeout)
        response=httpx.Response(status,request=httpx.Request('GET','http://fixture'))
        response.raise_for_status()
    with pytest.raises(httpx.HTTPStatusError):
        await r.run('fixture.read',call,replay_safe=True,attempt_timeout_s=1)
    assert len(calls)==(3 if retry else 1)

@pytest.mark.asyncio
async def test_full_jitter_uses_capped_exponential_upper_bound(monkeypatch):
    bounds=[];waits=[]
    def uniform(low,high):bounds.append((low,high));return high/2
    async def sleep(delay):waits.append(delay)
    monkeypatch.setattr(r.random,'uniform',uniform);monkeypatch.setattr(r,'_sleep',sleep)
    async def fail(timeout):raise r.TransientFailure('transient')
    with pytest.raises(r.TransientFailure):
        await r.run('fixture',fail,replay_safe=True,max_attempts=5,attempt_timeout_s=10,
                    base_delay_s=.5,max_delay_s=1,total_timeout_s=10)
    assert bounds==[(0,.5),(0,1),(0,1),(0,1)]
    assert waits==[.25,.5,.5,.5]

@pytest.mark.asyncio
async def test_deadline_clips_timeout_and_prevents_retry_after_budget_is_spent(monkeypatch):
    now=[10.0];calls=[]
    monkeypatch.setattr(r,'monotonic',lambda:now[0])
    async def call(timeout):calls.append(timeout);now[0]+=2;raise r.TransientFailure('fail')
    with r.budget_scope(1):
        with pytest.raises(r.DeadlineExceeded):await r.run('deadline',call,replay_safe=True,attempt_timeout_s=30)
    assert calls==[1]

@pytest.mark.asyncio
async def test_retry_after_never_retries_early_and_oversized_delay_is_refused(monkeypatch):
    waits=[];calls=[]
    async def sleep(delay):waits.append(delay)
    monkeypatch.setattr(r,'_sleep',sleep);monkeypatch.setattr(r.random,'uniform',lambda a,b:.1)
    async def call(timeout):
        calls.append(timeout)
        if len(calls)==1:
            response=httpx.Response(429,headers={'Retry-After':'1'},request=httpx.Request('POST','http://fixture'))
            response.raise_for_status()
        return 'ok'
    assert await r.run('throttled',call,replay_safe=True,attempt_timeout_s=5)=='ok'
    assert len(waits)==1 and 1 <= waits[0] <= 2
    calls.clear();waits.clear()
    async def long_wait(timeout):calls.append(timeout);raise r.TransientFailure('busy',retry_after_s=100)
    with pytest.raises(r.TransientFailure):await r.run('over-cap',long_wait,replay_safe=True)
    assert len(calls)==1 and waits==[]

@pytest.mark.asyncio
async def test_parallel_and_nested_operations_share_permits_without_multiplication(monkeypatch):
    monkeypatch.setattr(r.random,'uniform',lambda a,b:0)
    calls=[]
    async def failure(timeout):calls.append('wire');raise r.TransientFailure('fail')
    async def outer(timeout):return await r.run('inner',failure,replay_safe=True)
    with r.budget_scope(5,retry_tokens=2) as budget:
        results=await asyncio.gather(*(r.run('outer',outer,replay_safe=True) for _ in range(3)),return_exceptions=True)
        assert len(calls)==5  # three initial attempts + two shared retry permits
        assert budget.retry_tokens_remaining==0
        assert all(isinstance(x,(r.TransientFailure,r.RetryBudgetExhausted)) for x in results)

@pytest.mark.asyncio
async def test_unsafe_effect_and_validation_and_cancellation_are_never_retried():
    for error in [r.TransientFailure('lost ack'),ValueError('bad model answer'),asyncio.CancelledError()]:
        calls=[]
        async def fail(timeout):calls.append('call');raise error
        with pytest.raises(type(error)):
            await r.run('unsafe.write',fail,replay_safe=False)
        assert calls==['call']

@pytest.mark.asyncio
async def test_safe_calls_do_not_retry_protocol_or_answer_errors():
    for error in [ValueError('schema'),httpx.LocalProtocolError('bad request'),r.TransientFailure('schema',retryable=False)]:
        calls=[]
        async def fail(timeout):calls.append(1);raise error
        with pytest.raises(type(error)):await r.run('protocol',fail,replay_safe=True)
        assert len(calls)==1

@pytest.mark.asyncio
async def test_actual_attempt_timeout_and_parent_cancellation_stop_work():
    calls=[]
    async def slow(timeout):calls.append(timeout);await asyncio.sleep(2)
    with r.budget_scope(.03):
        with pytest.raises(r.DeadlineExceeded):await r.run('slow',slow,replay_safe=True,attempt_timeout_s=1)
    assert len(calls)==1
    with r.budget_scope(5):
        task=asyncio.create_task(r.run('cancel',slow,replay_safe=True))
        await asyncio.sleep(.01);task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
    assert len(calls)==2

def test_headers_decrease_and_nested_budget_cannot_extend_parent(monkeypatch):
    now=[1.0];monkeypatch.setattr(r,'monotonic',lambda:now[0])
    with r.budget_scope(3,retry_tokens=2):
        assert r.budget_headers()=={'X-Request-Timeout-Ms':'3000','X-Request-Retry-Budget':'2'}
        now[0]+=1
        with r.budget_scope(50,retry_tokens=20):assert r.remaining_timeout(20)==2
        assert r.current_budget().remaining()==2
    assert r.current_budget() is None

def test_http_date_retry_after_and_invalid_input():
    assert r.parse_retry_after('2',now=100)==2
    assert r.parse_retry_after(formatdate(103,usegmt=True),now=100)==3
    for raw in ['NaN','-1','garbage','Infinity',None]:assert r.parse_retry_after(raw,now=100) is None

@pytest.mark.asyncio
async def test_transport_retries_before_stream_acceptance_but_never_partial_stream(monkeypatch):
    monkeypatch.setattr(r.random,'uniform',lambda a,b:0)
    count=[]
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: first\n\n'
            raise httpx.ReadError('stream disconnected')
    async def handler(request):
        count.append(request)
        if len(count)==1:return httpx.Response(503)
        return httpx.Response(200,headers={'Content-Type':'text/event-stream'},stream=Stream())
    transport=r.ResilientAsyncTransport('llm.stream',replay_safe=True,timeout_s=1,transport=httpx.MockTransport(handler))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(httpx.ReadError):
            async with client.stream('POST','http://fixture') as response:
                async for _ in response.aiter_bytes():pass
    assert len(count)==2

@pytest.mark.asyncio
async def test_outer_safe_wrapper_cannot_replay_an_ambiguous_unsafe_inner_write(monkeypatch):
    monkeypatch.setattr(r.random,'uniform',lambda a,b:0)
    effects=[]
    async def write(timeout):effects.append(1);raise r.TransientFailure('lost acknowledgement')
    async def outer(timeout):return await r.run('unsafe.inner',write,replay_safe=False)
    with pytest.raises(r.TransientFailure):await r.run('outer',outer,replay_safe=True)
    assert len(effects)==1

@pytest.mark.asyncio
async def test_retry_sleep_is_inside_total_deadline(monkeypatch):
    calls=[]
    async def stuck_sleep(delay):await asyncio.sleep(1)
    async def fail(timeout):calls.append(1);raise r.TransientFailure('temporary')
    monkeypatch.setattr(r,'_sleep',stuck_sleep)
    with pytest.raises(r.DeadlineExceeded):
        await asyncio.wait_for(r.run('slow-sleep',fail,replay_safe=True,total_timeout_s=.05,
                                    base_delay_s=.001,max_delay_s=.001),timeout=.3)
    assert calls==[1]

@pytest.mark.asyncio
async def test_opaque_streaming_request_body_is_not_replayed(monkeypatch):
    calls=[]
    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):yield b'opaque bytes'
    async def handler(request):calls.append(1);return httpx.Response(503)
    transport=r.ResilientAsyncTransport('opaque',replay_safe=True,timeout_s=1,transport=httpx.MockTransport(handler))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError):await client.post('http://fixture',content=Body())
    assert calls==[1]

@pytest.mark.asyncio
async def test_retry_after_adds_bounded_jitter_above_the_server_floor(monkeypatch):
    waits=[];calls=[]
    monkeypatch.setattr(r.random,'uniform',lambda a,b:b/2)
    async def sleep(delay):waits.append(delay)
    monkeypatch.setattr(r,'_sleep',sleep)
    async def call(timeout):
        calls.append(1)
        if len(calls)==1:raise r.TransientFailure('busy',retry_after_s=1)
        return True
    assert await r.run('server-floor',call,replay_safe=True,base_delay_s=.25,max_delay_s=2)
    assert waits==[1.125]

@pytest.mark.asyncio
async def test_accepted_sse_body_has_its_own_absolute_deadline_without_an_asgi_request():
    calls=[];chunks=[]
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(20):
                yield b'data: token\n\n';await asyncio.sleep(.01)
    async def handler(request):calls.append(1);return httpx.Response(200,headers={'Content-Type':'text/event-stream'},stream=Stream())
    transport=r.ResilientAsyncTransport('direct.sdk.stream',replay_safe=True,timeout_s=.04,transport=httpx.MockTransport(handler))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(r.DeadlineExceeded):
            async with client.stream('POST','http://fixture') as response:
                async for chunk in response.aiter_bytes():chunks.append(chunk)
    assert len(calls)==1 and 0<len(chunks)<20

@pytest.mark.asyncio
@pytest.mark.parametrize('kind',['tls','malformed-http','wrapped-tls'])
async def test_permanent_tls_and_malformed_remote_protocol_never_retry(kind,monkeypatch):
    calls=[];monkeypatch.setattr(r.random,'uniform',lambda a,b:0)
    tls=httpx.ConnectError('TLS configuration failure');tls.__cause__=__import__('ssl').SSLError(1,'WRONG_VERSION_NUMBER')
    error=httpx.RemoteProtocolError('illegal status line') if kind=='malformed-http' else tls
    if kind=='wrapped-tls':
        wrapper=r.TransientFailure('adapter wrapped TLS');wrapper.__cause__=error;error=wrapper
    async def fail(timeout):calls.append(1);raise error
    with pytest.raises(type(error)):await r.run('configuration',fail,replay_safe=True)
    assert calls==[1]

@pytest.mark.asyncio
async def test_only_known_disconnect_before_response_is_transient(monkeypatch):
    calls=[];monkeypatch.setattr(r.random,'uniform',lambda a,b:0)
    async def fail(timeout):calls.append(1);raise httpx.RemoteProtocolError('Server disconnected without sending a response.')
    with pytest.raises(httpx.RemoteProtocolError):await r.run('ambiguous.read',fail,replay_safe=True)
    assert len(calls)==3

@pytest.mark.asyncio
async def test_retry_telemetry_is_visible_and_never_logs_payload_or_provider_message(caplog):
    import logging
    caplog.set_level(logging.INFO,logger='ai-service.resilience')
    async def fail(timeout):raise r.TransientFailure('PRIVATE_PROMPT_AND_KEY')
    with pytest.raises(r.TransientFailure):await r.run('model.telemetry',fail,replay_safe=True,max_attempts=1)
    assert 'PRIVATE_PROMPT_AND_KEY' not in caplog.text
    assert 'model.telemetry' in caplog.text and 'transient' in caplog.text

def test_retry_permit_reservation_is_atomic_across_thread_contexts():
    from concurrent.futures import ThreadPoolExecutor
    with r.budget_scope(1,retry_tokens=7) as budget:
        with ThreadPoolExecutor(max_workers=8) as pool:
            granted=list(pool.map(lambda _:budget.ledger.take_retry(),range(100)))
        assert sum(granted)==7 and budget.retry_tokens_remaining==0

@pytest.mark.asyncio
async def test_late_stream_eof_is_not_accepted_after_cancel_suppression():
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: partial\n\n'
            try:await asyncio.sleep(1)
            except asyncio.CancelledError:
                await asyncio.sleep(.01);return
    transport=r.ResilientAsyncTransport('late.eof',replay_safe=True,timeout_s=.03,
        transport=httpx.MockTransport(lambda req:httpx.Response(200,headers={'Content-Type':'text/event-stream'},stream=Stream())))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(r.DeadlineExceeded):
            async with client.stream('GET','http://fixture') as response:
                async for _ in response.aiter_bytes():pass

@pytest.mark.asyncio
async def test_accepted_sse_vetoes_any_enclosing_automatic_replay(monkeypatch):
    calls=[];chunks=[];monkeypatch.setattr(r.random,'uniform',lambda a,b:0)
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: partial\n\n';raise httpx.ReadError('truncated stream')
    async def handler(request):calls.append(1);return httpx.Response(200,headers={'Content-Type':'text/event-stream'},stream=Stream())
    transport=r.ResilientAsyncTransport('nested.stream',replay_safe=True,timeout_s=1,transport=httpx.MockTransport(handler))
    async with httpx.AsyncClient(transport=transport) as client:
        async def outer(timeout):
            async with client.stream('GET','http://fixture') as response:
                async for piece in response.aiter_bytes():chunks.append(piece)
        with pytest.raises(httpx.ReadError):await r.run('outer.stream',outer,replay_safe=True)
    assert len(calls)==len(chunks)==1
