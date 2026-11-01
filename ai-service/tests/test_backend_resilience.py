import asyncio
import json
import httpx
import pytest
from app.clients.backend_client import BackendClient
from app import resilience

@pytest.fixture
def no_wait(monkeypatch):
    monkeypatch.setattr(resilience.random,'uniform',lambda a,b:0)

@pytest.mark.asyncio
async def test_unsafe_post_lost_ack_is_not_replayed(no_wait):
    calls=[];effects=[]
    async def handler(request):
        calls.append(request);effects.append('one committed effect')
        raise httpx.ReadTimeout('reply lost',request=request)
    b=BackendClient();await b._client.aclose()
    b._client=httpx.AsyncClient(base_url='http://backend',transport=httpx.MockTransport(handler))
    try:
        result=await b.escalate(7,9,'fixture')
        assert 'error' in result and len(calls)==len(effects)==1
    finally:await b._client.aclose();await b._long_client.aclose()

@pytest.mark.asyncio
async def test_idempotent_preparation_reuses_key_after_lost_ack(no_wait):
    calls=[];ledger={}
    async def handler(request):
        body=json.loads(request.content);calls.append(body)
        ledger.setdefault(body['preparationKey'],{'actionId':'stable_action'})
        if len(calls)==1:raise httpx.ReadTimeout('lost ack',request=request)
        return httpx.Response(200,json={'code':0,'data':ledger[body['preparationKey']]})
    b=BackendClient();await b._client.aclose()
    b._client=httpx.AsyncClient(base_url='http://backend',transport=httpx.MockTransport(handler))
    try:
        result=await b.order_prepare(7,9,11,1,'fixture','10000000000','fixture',preparation_key='stable_call')
        assert result['actionId']=='stable_action' and len(calls)==2 and len(ledger)==1
        assert calls[0]==calls[1]
    finally:await b._client.aclose();await b._long_client.aclose()

@pytest.mark.asyncio
@pytest.mark.parametrize('response',[
    httpx.Response(403,json={'code':2003,'message':'denied'}),
    httpx.Response(200,json={'code':2015,'message':'quote changed'}),
    httpx.Response(200,text='not-json'),
])
async def test_business_auth_and_bad_envelope_are_not_retried(no_wait,response):
    calls=[]
    async def handler(request):calls.append(request);return response
    b=BackendClient();await b._client.aclose()
    b._client=httpx.AsyncClient(base_url='http://backend',transport=httpx.MockTransport(handler))
    try:
        assert 'error' in await b.order_query(7)
        assert len(calls)==1
    finally:await b._client.aclose();await b._long_client.aclose()

@pytest.mark.asyncio
async def test_shared_remaining_budget_is_forwarded_on_internal_reads(no_wait):
    calls=[]
    async def handler(request):calls.append(request);return httpx.Response(200,json={'code':0,'data':{}})
    b=BackendClient();await b._client.aclose()
    b._client=httpx.AsyncClient(base_url='http://backend',transport=httpx.MockTransport(handler))
    try:
        with resilience.budget_scope(.5,retry_tokens=1):await b.order_query(7)
        request=calls[0]
        assert 0<int(request.headers['X-Request-Timeout-Ms'])<=500
        assert request.headers['X-Request-Retry-Budget']=='1'
        assert request.extensions['timeout']['read']<=.5
    finally:await b._client.aclose();await b._long_client.aclose()
