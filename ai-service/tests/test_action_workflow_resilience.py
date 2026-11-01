import asyncio,json
import httpx,pytest
from app.agent.action_workflow import ActionWorkflows,WorkflowRetryable
from app.clients.action_workflows import ActionWorkflowBackend
from app.resilience import DeadlineExceeded,budget_scope
from tests.test_action_workflow_native import Backend,ACTION

@pytest.mark.asyncio
async def test_invalid_receipt_is_not_a_transient_failure(tmp_path):
    b=Backend();calls=[]
    async def invalid(*args):calls.append(1);return {'type':'WRONG','actionStatus':'CONFIRMED'}
    b.execute=invalid
    async with ActionWorkflows.open(tmp_path/'cp.db',b,retry_initial=.001,retry_max=.002) as service:
        await service.start(101,201,ACTION)
        with pytest.raises(WorkflowRetryable):await service.resume(101,201,ACTION,'approve',None)
        assert len(calls)==1

@pytest.mark.asyncio
async def test_real_http_lost_ack_has_one_retry_owner_and_one_effect(tmp_path):
    ledger={};calls=[]
    async def handler(request):
        body=json.loads(request.content)
        if request.url.path.endswith('/snapshot'):
            return httpx.Response(200,json={'code':0,'data':{'actionId':ACTION,'userId':101,'conversationId':201,
                'type':'ORDER_CREATE','status':'CONFIRMED' if ledger else 'PENDING','expiresAt':'2099-01-01T00:00:00Z','fingerprint':'a'*64}})
        calls.append(body)
        receipt={'type':'ORDER_CREATE','actionStatus':'CONFIRMED','orderId':42}
        ledger.setdefault(body['actionId'],receipt)
        if len(calls)==1:raise httpx.ReadTimeout('committed reply lost',request=request)
        return httpx.Response(200,json={'code':0,'data':ledger[body['actionId']]})
    async with httpx.AsyncClient(base_url='http://backend',transport=httpx.MockTransport(handler)) as client:
        async with ActionWorkflows.open(tmp_path/'cp.db',ActionWorkflowBackend(client),retry_initial=.001,retry_max=.002) as service:
            await service.start(101,201,ACTION)
            result=await service.resume(101,201,ACTION,'approve',None)
            assert result['workflowStatus']=='COMPLETED' and len(calls)==2 and len(ledger)==1
            assert calls[0]==calls[1]

@pytest.mark.asyncio
async def test_deadline_stops_retry_but_keeps_decision_available_for_explicit_recovery(tmp_path):
    b=Backend();original=b.execute;calls=[]
    async def delayed(*args):
        calls.append(1)
        if len(calls)==1:await asyncio.sleep(2)
        return await original(*args)
    b.execute=delayed
    async with ActionWorkflows.open(tmp_path/'cp.db',b,retry_initial=.001,retry_max=.002) as service:
        await service.start(101,201,ACTION)
        with budget_scope(.2):
            with pytest.raises(DeadlineExceeded):await service.resume(101,201,ACTION,'approve',None)
        state=await service.graph.aget_state(service.config(101,201,ACTION))
        assert state.values['decision']=='approve' and b.effects==0 and len(calls)==1
        result=await service.recover(101,201,ACTION)
        assert result['workflowStatus']=='COMPLETED' and b.effects==1 and len(calls)==2

def test_isolated_workflow_engine_does_not_load_application_credentials(tmp_path):
    import os,subprocess,sys
    from pathlib import Path
    (tmp_path/'.env').write_text('ACTION_WORKFLOWS_ENABLED=true\nINTERNAL_TOKEN=\n',encoding='utf-8')
    env={k:v for k,v in os.environ.items() if k in {'PATH','SYSTEMROOT','WINDIR','TEMP','TMP'}}
    env['PYTHONPATH']=str(Path(__file__).resolve().parents[1])
    process=subprocess.run([sys.executable,'-c',"import sys;import app.agent.action_workflow;assert 'app.config' not in sys.modules"],
                           cwd=tmp_path,env=env,capture_output=True,timeout=15)
    assert process.returncode==0,'isolated native engine imported application configuration'

@pytest.mark.asyncio
@pytest.mark.parametrize('phase',['canonical','operation'])
async def test_owned_native_invocation_deadline_includes_all_work_and_releases_lock(tmp_path,phase):
    b=Backend();operation_finished=[]
    if phase=='canonical':
        original=b.snapshot
        async def snapshot(*args):await asyncio.sleep(.12);return await original(*args)
        b.snapshot=snapshot
    async def operation(config,canonical):await asyncio.sleep(.12);operation_finished.append(1);return {'late':True}
    async with ActionWorkflows.open(tmp_path/'cp.db',b,total_timeout_s=.03) as service:
        with pytest.raises(DeadlineExceeded):await service._owned(101,201,ACTION,operation)
        await asyncio.sleep(0)
        assert not service._tasks and operation_finished==[]
