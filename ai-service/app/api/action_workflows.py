"""Backend-only native action lifecycle. Frontend claims never become receipts."""
from typing import Annotated, Literal
from contextlib import asynccontextmanager, AsyncExitStack
import anyio
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from app.agent.action_workflow import (DeliveryApproval, WorkflowConflict,
    WorkflowNotFound, WorkflowRejected, WorkflowRetryable, ActionWorkflows)
from app.config import settings
from app.resilience import DeadlineExceeded, RetryBudgetExhausted
from app.clients.action_workflows import ActionWorkflowBackend

router = APIRouter()


class OwnerBinding(BaseModel):
    model_config = ConfigDict(extra='forbid')
    userId: Annotated[StrictInt, Field(gt=0)]
    conversationId: Annotated[StrictInt, Field(gt=0)]


class ResumeDecision(OwnerBinding):
    decision: Literal['approve', 'reject']
    approval: DeliveryApproval | None = None


def service(request: Request):
    if not settings.internal_token or request.headers.get('X-Internal-Token') != settings.internal_token:
        raise HTTPException(401, 'invalid internal token')
    engine = getattr(request.app.state, 'action_workflows', None)
    if not getattr(settings, 'action_workflows_enabled', False) or engine is None:
        raise HTTPException(503, 'durable action workflows unavailable')
    return engine


async def invoke(method, *args):
    try:
        return await method(*args)
    except WorkflowNotFound as error:
        raise HTTPException(404, str(error)) from None
    except WorkflowConflict as error:
        raise HTTPException(409, str(error)) from None
    except WorkflowRejected as error:
        raise HTTPException(409, {'code': error.code, 'message': error.message}) from None
    except (WorkflowRetryable,DeadlineExceeded,RetryBudgetExhausted,TimeoutError):
        raise HTTPException(503, {'message': 'workflow temporarily unavailable; saved decision can be recovered',
                                  'recoverable': True}) from None


@router.post('/action-workflows/{action_id}/start')
async def start(action_id: str, body: OwnerBinding, engine=Depends(service)):
    return await invoke(engine.start, body.userId, body.conversationId, action_id)


@router.post('/action-workflows/{action_id}/status')
async def status(action_id: str, body: OwnerBinding, engine=Depends(service)):
    return await invoke(engine.status, body.userId, body.conversationId, action_id)


@router.post('/action-workflows/{action_id}/recover')
async def recover(action_id: str, body: OwnerBinding, engine=Depends(service)):
    return await invoke(engine.recover, body.userId, body.conversationId, action_id)


@router.post('/action-workflows/{action_id}/resume')
async def resume(action_id: str, body: ResumeDecision, engine=Depends(service)):
    return await invoke(engine.resume, body.userId, body.conversationId, action_id,
                        body.decision, body.approval.model_dump() if body.approval else None)


@asynccontextmanager
async def lifespan(app):
    app.state.action_workflows = None
    if not settings.action_workflows_enabled:
        yield
        return
    resources = AsyncExitStack()
    try:
        client = await resources.enter_async_context(httpx.AsyncClient(
            base_url=settings.backend_base_url,
            headers={"X-Internal-Token": settings.internal_token},
            timeout=httpx.Timeout(settings.action_workflow_callback_timeout_s), trust_env=False))
        engine = await resources.enter_async_context(ActionWorkflows.open(
            settings.action_workflow_checkpoint_path, ActionWorkflowBackend(client),
            total_timeout_s=settings.action_workflow_total_timeout_s,
            callback_timeout_s=settings.action_workflow_callback_timeout_s,
            retry_tokens=settings.retry_budget_limit))
        app.state.action_workflows = engine
        yield
    finally:
        app.state.action_workflows = None
        with anyio.CancelScope(shield=True):
            await resources.aclose()
