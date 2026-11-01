"""Durable, per-action native approval workflows; no LLM may approve an action.

Single AI instance + local persistent SQLite. This is not a distributed execution
claim. Business effects remain in the backend's owner/expiry/quote/idempotency gate.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import hashlib
from pathlib import Path
from typing import Annotated, Literal, Protocol, TypedDict
from weakref import WeakValueDictionary

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from app.resilience import DeadlineExceeded, TransientFailure, budget_scope, remaining_timeout, run
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError


class WorkflowConflict(Exception):
    pass


class WorkflowNotFound(WorkflowConflict):
    pass


class WorkflowRetryable(TransientFailure):
    """Transport/429/5xx only, never arbitrary business rejection."""


class WorkflowRejected(Exception):
    def __init__(self, code: int, message: str):
        self.code, self.message = code, message
        super().__init__(message)


class DeliveryApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    receiverName: Annotated[StrictStr, Field(min_length=1, max_length=100)]
    receiverPhone: Annotated[StrictStr, Field(min_length=1, max_length=32)]
    receiverAddress: Annotated[StrictStr, Field(min_length=1, max_length=500)]


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    approval: DeliveryApproval | None = None


class CanonicalAction(BaseModel):
    actionId: Annotated[StrictStr, Field(min_length=1, max_length=128)]
    userId: Annotated[StrictInt, Field(gt=0)]
    conversationId: Annotated[StrictInt, Field(gt=0)]
    type: Literal["ORDER_CREATE", "ORDER_CANCEL", "AFTER_SALE_APPLY"]
    status: Literal["PENDING", "CONFIRMED", "CANCELLED", "EXPIRED"]
    expiresAt: str
    fingerprint: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class ActionBackend(Protocol):
    async def snapshot(self, user_id: int, action_id: str) -> dict: ...
    async def execute(self, user_id: int, action_id: str, approval: dict | None) -> dict: ...
    async def cancel(self, user_id: int, action_id: str) -> dict: ...


class ActionState(TypedDict, total=False):
    schemaVersion: int
    canonical: dict
    decision: str
    approval: dict | None
    workflowStatus: str
    result: dict
    error: dict | None


class ActionWorkflows:
    def __init__(self, saver, backend: ActionBackend, *, retry_initial=.5, retry_max=2.0,
                 total_timeout_s=15, callback_timeout_s=3, retry_tokens=6):
        self.backend = backend
        self._retry_initial, self._retry_max = retry_initial, retry_max
        self._total_timeout_s, self._callback_timeout_s = total_timeout_s, callback_timeout_s
        self._retry_tokens = retry_tokens
        self._locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()
        self._tasks: set[asyncio.Task] = set()
        builder = StateGraph(ActionState)
        builder.add_node("review", self._review)
        # Shared policy is the only retry owner; no additive LangGraph/HTTP retries.
        builder.add_node("execute_decision", self._execute)
        builder.add_edge(START, "review")
        builder.add_edge("review", "execute_decision")
        builder.add_edge("execute_decision", END)
        self.graph = builder.compile(checkpointer=saver)

    @classmethod
    @asynccontextmanager
    async def open(cls, path, backend, **kwargs):
        text = str(path)
        if not text.strip() or text == ":memory:" or text.startswith("file:"):
            raise ValueError("approval workflows require a durable filesystem checkpoint")
        target = Path(path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        async with AsyncSqliteSaver.from_conn_string(str(target)) as saver:
            await saver.setup()
            target.chmod(0o600)
            service = cls(saver, backend, **kwargs)
            try:
                yield service
            finally:
                # Caller cancellation never converts into withdrawal of a saved approval.
                # Finish owned work before closing its checkpoint connection.
                if service._tasks:
                    await asyncio.shield(asyncio.gather(*tuple(service._tasks), return_exceptions=True))

    @staticmethod
    def config(user_id, conversation_id, action_id):
        binding = f"{user_id}:{conversation_id}:{action_id}".encode()
        return {"configurable": {"thread_id": "action-v1:" + hashlib.sha256(binding).hexdigest()}}

    @staticmethod
    def _review(state: ActionState):
        action = state["canonical"]
        # This node is replayed on resume. No side effect is allowed before interrupt.
        choice = interrupt({"actionId": action["actionId"], "type": action["type"],
                            "conversationId": action["conversationId"],
                            "expiresAt": action["expiresAt"], "requiresExplicitApproval": True})
        decision = Decision.model_validate(choice)
        return {"decision": decision.decision,
                "approval": decision.approval.model_dump() if decision.approval else None,
                "workflowStatus": "EXECUTING"}

    async def _execute(self, state: ActionState):
        async def attempt(_timeout):
            return await self._execute_once(state)
        # The stable canonical actionId makes execution replay-safe. A timeout is
        # not proof of rollback: a later recovery repeats the same saved decision.
        return await run("action.execute",attempt,replay_safe=True,
                         attempt_timeout_s=self._callback_timeout_s,
                         total_timeout_s=self._total_timeout_s,
                         base_delay_s=self._retry_initial,max_delay_s=self._retry_max)

    async def _execute_once(self, state: ActionState):
        action = state["canonical"]
        try:
            if state["decision"] == "approve":
                result = await self.backend.execute(action["userId"], action["actionId"], state.get("approval"))
                expected_status, terminal = "CONFIRMED", "COMPLETED"
            else:
                result = await self.backend.cancel(action["userId"], action["actionId"])
                expected_status, terminal = "CANCELLED", "CANCELLED"
            if (not isinstance(result, dict) or result.get("type") != action["type"]
                    or result.get("actionStatus") != expected_status):
                raise WorkflowRetryable("invalid backend execution receipt",retryable=False)
            return {"result": result, "workflowStatus": terminal, "error": None}
        except WorkflowRejected as error:
            return {"workflowStatus": "EXPIRED" if error.code == 2011 else "FAILED",
                    "error": {"code": error.code, "message": error.message}}

    async def _canonical(self, user_id, conversation_id, action_id):
        if type(user_id) is not int or type(conversation_id) is not int:
            raise WorkflowConflict("invalid owner binding")
        try:
            action = CanonicalAction.model_validate(await self.backend.snapshot(user_id, action_id))
        except ValidationError as error:
            raise WorkflowRetryable("invalid backend action snapshot",retryable=False) from error
        if (action.userId, action.conversationId, action.actionId) != (user_id, conversation_id, action_id):
            raise WorkflowConflict("action owner/conversation binding mismatch")
        return action.model_dump()

    @staticmethod
    def _check_binding(state, canonical):
        original = state.values.get("canonical", {})
        if state.values.get("schemaVersion") != 1 or any(
            original.get(key) != canonical.get(key)
            for key in ("actionId", "userId", "conversationId", "type", "fingerprint")
        ):
            raise WorkflowConflict("action snapshot binding changed")

    async def _reconcile_waiting(self, config, current, canonical):
        # START output may be durable pending writes before a review checkpoint.
        # Materialize that real interrupt, without supplying any decision.
        if (current.values.get("workflowStatus") == "WAITING_APPROVAL"
                and not current.values.get("decision") and not current.next):
            await self.graph.ainvoke(None, config, durability="sync")
            current = await self.graph.aget_state(config)
        # Trusted backend expiry/cancellation terminates waiting, never fabricates a decision.
        if current.next == ("review",) and canonical["status"] != "PENDING":
            terminal = {"EXPIRED": "EXPIRED", "CANCELLED": "CANCELLED"}.get(
                canonical["status"], "FAILED")
            await self.graph.aupdate_state(config, {"workflowStatus": terminal,
                "error": {"code": 2011 if terminal == "EXPIRED" else 409,
                          "message": "action is no longer awaiting approval"}},
                as_node="execute_decision")
            return await self.graph.aget_state(config)
        return current

    @staticmethod
    def _has_work(state):
        # Pending task writes can expose the saved review output with next=().
        # Only an explicit terminal status, not next alone, proves completion.
        return bool(state.next or (state.values.get("decision")
                    and state.values.get("workflowStatus") == "EXECUTING"))

    @staticmethod
    def _view(state):
        values = state.values
        interrupted = bool(state.next and state.next[0] == "review")
        return {"actionId": values["canonical"]["actionId"], "nativeInterrupt": True,
                "workflowStatus": "WAITING_APPROVAL" if interrupted else values["workflowStatus"],
                "interrupted": interrupted, "recoverable": ActionWorkflows._has_work(state),
                "result": values.get("result"), "error": values.get("error") or None}

    async def _owned(self, user_id, conversation_id, action_id, operation):
        config = self.config(user_id, conversation_id, action_id)
        key = config["configurable"]["thread_id"]
        lock = self._locks.setdefault(key, asyncio.Lock())
        async def owned_operation():
            # Each explicit resume/recover gets a new bounded invocation, never a
            # new decision. Waiting for serialization also consumes its deadline.
            with budget_scope(self._total_timeout_s,
                              retry_tokens=self._retry_tokens):
                try:
                    async with asyncio.timeout(remaining_timeout(self._total_timeout_s)):
                        async with lock:
                            canonical = await self._canonical(user_id, conversation_id, action_id)
                            result=await operation(config, canonical)
                            remaining_timeout(self._total_timeout_s)
                            return result
                except TimeoutError as error:
                    raise DeadlineExceeded("native invocation deadline exhausted") from error
        task = asyncio.create_task(owned_operation(), name="action-workflow-operation")
        self._tasks.add(task)
        def completed(done):
            self._tasks.discard(done)
            if not done.cancelled(): done.exception()
        task.add_done_callback(completed)
        return await asyncio.shield(task)

    async def start(self, user_id, conversation_id, action_id):
        async def operation(config, canonical):
            current = await self.graph.aget_state(config)
            if current.values:
                self._check_binding(current, canonical)
                current = await self._reconcile_waiting(config, current, canonical)
                return self._view(current)
            if canonical["status"] != "PENDING":
                raise WorkflowConflict("only a pending action can start an approval workflow")
            await self.graph.ainvoke({"schemaVersion": 1, "canonical": canonical,
                "workflowStatus": "WAITING_APPROVAL"}, config, durability="sync")
            return self._view(await self.graph.aget_state(config))
        return await self._owned(user_id, conversation_id, action_id, operation)

    async def status(self, user_id, conversation_id, action_id):
        async def operation(config, canonical):
            current = await self.graph.aget_state(config)
            if not current.values: raise WorkflowNotFound("native workflow is not registered")
            self._check_binding(current, canonical)
            current = await self._reconcile_waiting(config, current, canonical)
            return self._view(current)
        return await self._owned(user_id, conversation_id, action_id, operation)

    async def resume(self, user_id, conversation_id, action_id, decision, approval):
        choice = Decision(decision=decision, approval=approval)
        supplied = choice.model_dump()
        async def operation(config, canonical):
            current = await self.graph.aget_state(config)
            if not current.values: raise WorkflowNotFound("native workflow is not registered")
            self._check_binding(current, canonical)
            current = await self._reconcile_waiting(config, current, canonical)
            if not current.next and not current.values.get("decision"):
                raise WorkflowConflict("action is no longer awaiting approval")
            if (choice.decision == "reject" and choice.approval is not None
                    or canonical["type"] != "ORDER_CREATE" and choice.approval is not None):
                raise WorkflowConflict("approval fields do not apply to this action")
            if current.values.get("decision"):
                if (current.values["decision"] != choice.decision
                        or current.values.get("approval") != supplied["approval"]):
                    raise WorkflowConflict("a saved decision cannot be replaced")
                command = None
            else:
                if canonical["status"] != "PENDING":
                    raise WorkflowConflict("action is no longer awaiting approval")
                command = Command(resume=supplied)
            if self._has_work(current):
                await self.graph.ainvoke(command, config, durability="sync")
            return self._view(await self.graph.aget_state(config))
        return await self._owned(user_id, conversation_id, action_id, operation)

    async def recover(self, user_id, conversation_id, action_id):
        async def operation(config, canonical):
            current = await self.graph.aget_state(config)
            if not current.values: raise WorkflowNotFound("native workflow is not registered")
            self._check_binding(current, canonical)
            current = await self._reconcile_waiting(config, current, canonical)
            if self._has_work(current) and current.values.get("decision"):
                await self.graph.ainvoke(None, config, durability="sync")
            return self._view(await self.graph.aget_state(config))
        return await self._owned(user_id, conversation_id, action_id, operation)
