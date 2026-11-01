"""Real LangGraph interrupt/checkpoint tests; not mocked model-quality claims."""
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from app.agent.action_workflow import ActionWorkflows, WorkflowConflict, WorkflowRetryable

ACTION="act_11111111-1111-4111-8111-111111111111"
class Backend:
    def __init__(self):
        self.effects=0;self.cancels=0;self.failures=0
        self.value={"actionId":ACTION,"userId":101,"conversationId":201,"type":"ORDER_CREATE",
            "status":"PENDING","expiresAt":(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat(),"fingerprint":"a"*64}
    async def snapshot(self,user_id,action_id):
        if user_id!=101 or action_id!=ACTION:raise WorkflowConflict("owner mismatch")
        return dict(self.value)
    async def execute(self,user_id,action_id,approval):
        if self.failures:
            self.failures-=1;raise WorkflowRetryable("temporary")
        if self.value['status']!='CONFIRMED':self.effects+=1
        self.value['status']='CONFIRMED'
        return {"type":"ORDER_CREATE","actionStatus":"CONFIRMED","orderId":42,"orderNo":"TEST42","status":"PENDING_PAYMENT"}
    async def cancel(self,user_id,action_id):
        self.cancels+=1;self.value['status']='CANCELLED'
        return {"type":"ORDER_CREATE","actionStatus":"CANCELLED"}

@pytest.mark.asyncio
async def test_native_interrupt_persists_and_resumes_after_service_reconstruction(tmp_path):
    b=Backend();path=tmp_path/'workflow.db'
    async with ActionWorkflows.open(path,b) as service:
        first=await service.start(101,201,ACTION)
        assert first['workflowStatus']=='WAITING_APPROVAL' and first['interrupted']
        state=await service.graph.aget_state(service.config(101,201,ACTION))
        assert state.next==('review',) and state.tasks[0].interrupts
        assert b.effects==0
    async with ActionWorkflows.open(path,b) as service:
        waiting=await service.recover(101,201,ACTION)
        assert waiting['interrupted'] and b.effects==0
        result=await service.resume(101,201,ACTION,'approve',None)
        assert result['workflowStatus']=='COMPLETED' and result['result']['orderId']==42
        assert b.effects==1
        assert not (await service.graph.aget_state(service.config(101,201,ACTION))).next
        again=await service.resume(101,201,ACTION,'approve',None)
        assert again['result']==result['result'] and b.effects==1

@pytest.mark.asyncio
async def test_reject_is_a_durable_decision_and_never_executes_order(tmp_path):
    b=Backend()
    async with ActionWorkflows.open(tmp_path/'workflow.db',b) as service:
        await service.start(101,201,ACTION)
        result=await service.resume(101,201,ACTION,'reject',None)
        assert result['workflowStatus']=='CANCELLED' and b.effects==0 and b.cancels==1
        with pytest.raises(WorkflowConflict):await service.resume(101,201,ACTION,'approve',None)

@pytest.mark.asyncio
async def test_owner_conversation_and_immutable_snapshot_are_bound(tmp_path):
    b=Backend()
    async with ActionWorkflows.open(tmp_path/'workflow.db',b) as service:
        await service.start(101,201,ACTION)
        with pytest.raises(WorkflowConflict):await service.resume(102,201,ACTION,'approve',None)
        with pytest.raises(WorkflowConflict):await service.resume(101,202,ACTION,'approve',None)
        b.value['fingerprint']='b'*64
        with pytest.raises(WorkflowConflict):await service.resume(101,201,ACTION,'approve',None)
        assert b.effects==0

@pytest.mark.asyncio
async def test_recover_without_human_decision_does_not_approve(tmp_path):
    b=Backend()
    async with ActionWorkflows.open(tmp_path/'workflow.db',b) as service:
        await service.start(101,201,ACTION)
        for _ in range(2):assert (await service.recover(101,201,ACTION))['workflowStatus']=='WAITING_APPROVAL'
        assert b.effects==0

@pytest.mark.asyncio
async def test_native_retry_is_bounded_and_permanent_rejection_is_not_retried(tmp_path):
    b=Backend();b.failures=2
    async with ActionWorkflows.open(tmp_path/'workflow.db',b,retry_initial=.001,retry_max=.002) as service:
        await service.start(101,201,ACTION)
        r=await service.resume(101,201,ACTION,'approve',None)
        assert r['workflowStatus']=='COMPLETED' and b.failures==0 and b.effects==1

@pytest.mark.asyncio
async def test_durability_cannot_silently_fall_back_to_in_memory():
    with pytest.raises(ValueError):
        async with ActionWorkflows.open(':memory:',Backend()):pass

@pytest.mark.asyncio
async def test_duplicate_concurrent_approval_has_one_effect(tmp_path):
    b=Backend()
    async with ActionWorkflows.open(tmp_path/'workflow.db',b) as service:
        await service.start(101,201,ACTION)
        results=await asyncio.gather(*(service.resume(101,201,ACTION,'approve',None) for _ in range(3)))
        assert all(r['workflowStatus']=='COMPLETED' for r in results) and b.effects==1


@pytest.mark.asyncio
async def test_permanent_domain_rejection_is_not_retried_or_changed_into_success(tmp_path):
    from app.agent.action_workflow import WorkflowRejected
    b=Backend();calls=[]
    async def reject(user_id,action_id,approval):
        calls.append(action_id);raise WorkflowRejected(2015,'quote changed')
    b.execute=reject
    async with ActionWorkflows.open(tmp_path/'cp.db',b,retry_initial=.001,retry_max=.002) as service:
        await service.start(101,201,ACTION)
        result=await service.resume(101,201,ACTION,'approve',None)
        assert result['workflowStatus']=='FAILED' and result['error']['code']==2015
        assert len(calls)==1 and b.effects==0
        assert (await service.recover(101,201,ACTION))['workflowStatus']=='FAILED'
        assert len(calls)==1


@pytest.mark.asyncio
async def test_expired_waiting_action_can_never_resume_into_execution(tmp_path):
    b=Backend()
    async with ActionWorkflows.open(tmp_path/'cp.db',b) as service:
        await service.start(101,201,ACTION)
        b.value['status']='EXPIRED'
        result=await service.recover(101,201,ACTION)
        assert result['workflowStatus']=='EXPIRED' and b.effects==0
        assert not (await service.graph.aget_state(service.config(101,201,ACTION))).next

@pytest.mark.asyncio
async def test_exhausted_execution_can_recover_only_the_persisted_decision(tmp_path):
    b=Backend();b.failures=3
    async with ActionWorkflows.open(tmp_path/'cp.db',b,retry_initial=.001,retry_max=.002) as service:
        await service.start(101,201,ACTION)
        with pytest.raises(WorkflowRetryable):
            await service.resume(101,201,ACTION,'approve',None)
        state=await service.graph.aget_state(service.config(101,201,ACTION))
        assert state.values['decision']=='approve' and state.next==('execute_decision',)
        with pytest.raises(WorkflowConflict):
            await service.resume(101,201,ACTION,'reject',None)
        result=await service.recover(101,201,ACTION)
        assert result['workflowStatus']=='COMPLETED' and b.effects==1

@pytest.mark.asyncio
async def test_saved_delivery_approval_cannot_be_replaced_on_retry(tmp_path):
    b=Backend();b.failures=3
    first={'receiverName':'fixture','receiverPhone':'10000000000','receiverAddress':'address A'}
    async with ActionWorkflows.open(tmp_path/'cp.db',b,retry_initial=.001,retry_max=.002) as service:
        await service.start(101,201,ACTION)
        with pytest.raises(WorkflowRetryable):await service.resume(101,201,ACTION,'approve',first)
        with pytest.raises(WorkflowConflict):
            await service.resume(101,201,ACTION,'approve',{**first,'receiverAddress':'address B'})
        assert (await service.recover(101,201,ACTION))['workflowStatus']=='COMPLETED'
        state=await service.graph.aget_state(service.config(101,201,ACTION))
        assert state.values['approval']==first and b.effects==1

@pytest.mark.asyncio
async def test_http_caller_cancellation_cannot_withdraw_saved_approval_or_duplicate_effect(tmp_path):
    b=Backend();entered=asyncio.Event();release=asyncio.Event();original=b.execute
    async def delayed(*args):
        entered.set();await release.wait();return await original(*args)
    b.execute=delayed
    async with ActionWorkflows.open(tmp_path/'cp.db',b) as service:
        await service.start(101,201,ACTION)
        task=asyncio.create_task(service.resume(101,201,ACTION,'approve',None))
        await asyncio.wait_for(entered.wait(),timeout=5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        recovery=asyncio.create_task(service.recover(101,201,ACTION))
        await asyncio.sleep(.01)
        assert not recovery.done()
        release.set()
        result=await asyncio.wait_for(recovery,timeout=5)
        assert result['workflowStatus']=='COMPLETED' and b.effects==1

@pytest.mark.asyncio
async def test_malformed_backend_snapshot_is_a_dependency_failure_not_an_approval(tmp_path):
    b=Backend();b.value['fingerprint']='bad'
    async with ActionWorkflows.open(tmp_path/'cp.db',b) as service:
        with pytest.raises(WorkflowRetryable):await service.start(101,201,ACTION)
        assert b.effects==0

@pytest.mark.asyncio
async def test_success_receipt_has_no_truthy_frontend_error_metadata(tmp_path):
    b=Backend()
    async with ActionWorkflows.open(tmp_path/'cp.db',b) as service:
        await service.start(101,201,ACTION)
        result=await service.resume(101,201,ACTION,'approve',None)
        assert result['workflowStatus']=='COMPLETED' and result['error'] is None
