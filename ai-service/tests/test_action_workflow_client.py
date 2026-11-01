import httpx,pytest
from app.clients.action_workflows import ActionWorkflowBackend
from app.agent.action_workflow import WorkflowRejected,WorkflowRetryable

@pytest.mark.asyncio
async def test_domain_error_has_no_hidden_retry_and_transient_failures_are_classified():
    calls=[]
    async def handler(request):
        calls.append(request)
        assert request.headers['X-Internal-Token']=='test-only'
        return httpx.Response(200,json={'code':2015,'message':'quote changed'})
    async with httpx.AsyncClient(base_url='http://backend',headers={'X-Internal-Token':'test-only'},transport=httpx.MockTransport(handler)) as c:
        backend=ActionWorkflowBackend(c)
        with pytest.raises(WorkflowRejected) as e:await backend.execute(11,'act_x',None)
        assert e.value.code==2015 and len(calls)==1
    async with httpx.AsyncClient(base_url='http://backend',transport=httpx.MockTransport(lambda request:httpx.Response(503))) as c:
        with pytest.raises(WorkflowRetryable):await ActionWorkflowBackend(c).execute(11,'act_x',None)

@pytest.mark.asyncio
async def test_snapshot_and_cancel_use_fixed_internal_routes():
    seen=[]
    async def handler(request):
        seen.append(request.url.path)
        return httpx.Response(200,json={'code':0,'data':{'status':'PENDING'}})
    async with httpx.AsyncClient(base_url='http://backend',transport=httpx.MockTransport(handler)) as c:
        b=ActionWorkflowBackend(c)
        await b.snapshot(11,'act_x');await b.cancel(11,'act_x')
    assert seen==['/internal/tools/action-workflows/snapshot','/internal/tools/action-workflows/cancel']

@pytest.mark.asyncio
async def test_backend_http_business_rejection_preserves_expiry_code():
    async with httpx.AsyncClient(base_url='http://backend',transport=httpx.MockTransport(
        lambda request:httpx.Response(400,json={'code':2011,'message':'action expired'}))) as c:
        with pytest.raises(WorkflowRejected) as error:
            await ActionWorkflowBackend(c).execute(11,'act_x',None)
        assert error.value.code==2011
