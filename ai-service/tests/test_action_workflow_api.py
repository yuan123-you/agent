import asyncio
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
import httpx,pytest
from fastapi import FastAPI
from app.api import action_workflows
from app.agent.action_workflow import ActionWorkflows

ACTION="act_22222222-2222-4222-8222-222222222222"
class Backend:
    effects=0
    async def snapshot(self,user_id,action_id):
        return {"actionId":ACTION,"userId":11,"conversationId":22,"type":"ORDER_CREATE","status":"PENDING","expiresAt":(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat(),"fingerprint":"a"*64}
    async def execute(self,user_id,action_id,approval):
        self.effects+=1;return {"type":"ORDER_CREATE","actionStatus":"CONFIRMED","orderId":7}
    async def cancel(self,user_id,action_id):return {"type":"ORDER_CREATE","actionStatus":"CANCELLED"}

@pytest.mark.asyncio
async def test_internal_auth_real_interrupt_and_recovery_route(tmp_path,monkeypatch):
    monkeypatch.setattr(action_workflows,'settings',SimpleNamespace(internal_token='test-internal',action_workflows_enabled=True))
    app=FastAPI();app.include_router(action_workflows.router,prefix='/v1')
    backend=Backend()
    async with ActionWorkflows.open(tmp_path/'cp.db',backend) as service:
        app.state.action_workflows=service
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
            body={'userId':11,'conversationId':22};path=f'/v1/action-workflows/{ACTION}'
            assert (await c.post(path+'/start',json=body)).status_code==401
            c.headers['X-Internal-Token']='test-internal'
            r=await c.post(path+'/start',json=body)
            assert r.status_code==200 and r.json()['interrupted'] and backend.effects==0
            r=await c.post(path+'/recover',json=body)
            assert r.json()['workflowStatus']=='WAITING_APPROVAL' and backend.effects==0
            forged=await c.post(path+'/resume',json={**body,'decision':'approve','result':{'orderId':999}})
            assert forged.status_code==422 and backend.effects==0
            wrong=await c.post(path+'/resume',json={**body,'conversationId':23,'decision':'approve'})
            assert wrong.status_code==409 and backend.effects==0
            r=await c.post(path+'/resume',json={**body,'decision':'approve'})
            assert r.json()['workflowStatus']=='COMPLETED' and backend.effects==1
            r=await c.post(path+'/recover',json=body)
            assert r.json()['result']['orderId']==7 and backend.effects==1

@pytest.mark.asyncio
async def test_disabled_or_missing_durable_service_never_falls_back_to_confirmation(monkeypatch):
    monkeypatch.setattr(action_workflows,'settings',SimpleNamespace(internal_token='test-internal',action_workflows_enabled=False))
    app=FastAPI();app.include_router(action_workflows.router,prefix='/v1')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers={'X-Internal-Token':'test-internal'}) as c:
        r=await c.post(f'/v1/action-workflows/{ACTION}/resume',json={'userId':11,'conversationId':22,'decision':'approve'})
        assert r.status_code==503
