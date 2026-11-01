"""Real process-death probes for pending START/review writes; synthetic business only."""
import asyncio
import json
import os
from pathlib import Path
import sqlite3
import sys

from app.agent.action_workflow import ActionWorkflows, WorkflowConflict

ACTION = "act_44444444-4444-4444-8444-444444444444"
APPROVAL = {
    "receiverName": "Synthetic buyer",
    "receiverPhone": "10000000000",
    "receiverAddress": "Synthetic approved address",
}
PROOF_PREFIX = "NATIVE_PROOF "
CRASH_EXIT = 73


class Backend:
    def __init__(self, ledger):
        self.ledger = ledger
        with sqlite3.connect(ledger) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS effects(action_id TEXT PRIMARY KEY, receipt TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY, action_id TEXT NOT NULL)")

    def counts(self):
        with sqlite3.connect(self.ledger) as connection:
            return {
                "effects": connection.execute("SELECT COUNT(*) FROM effects").fetchone()[0],
                "executionAttempts": connection.execute("SELECT COUNT(*) FROM attempts").fetchone()[0],
            }

    async def snapshot(self, user_id, action_id):
        if user_id != 101 or action_id != ACTION:
            raise WorkflowConflict("synthetic owner mismatch")
        return {
            "actionId": ACTION, "userId": 101, "conversationId": 201,
            "type": "ORDER_CREATE", "status": "CONFIRMED" if self.counts()["effects"] else "PENDING",
            "expiresAt": "2099-01-01T00:00:00+00:00", "fingerprint": "a" * 64,
        }

    async def execute(self, user_id, action_id, approval):
        assert user_id == 101 and action_id == ACTION
        assert approval == APPROVAL, "replay must retain the exact saved human delivery approval"
        receipt = {
            "type": "ORDER_CREATE", "actionStatus": "CONFIRMED", "orderId": 42,
            "orderNo": "SYNTHETIC42", **APPROVAL,
        }
        with sqlite3.connect(self.ledger) as connection:
            connection.execute("INSERT INTO attempts(action_id) VALUES(?)", (action_id,))
            connection.execute("INSERT OR IGNORE INTO effects VALUES(?, ?)", (action_id, json.dumps(receipt)))
            stored = connection.execute("SELECT receipt FROM effects WHERE action_id=?", (action_id,)).fetchone()[0]
        return json.loads(stored)

    async def cancel(self, user_id, action_id):
        raise AssertionError("these probes never submit a rejection")


def emit(proof):
    print(PROOF_PREFIX + json.dumps(proof), flush=True)


async def describe(service, backend, mode, result=None):
    config = service.config(101, 201, ACTION)
    raw = await service.graph.checkpointer.aget_tuple(config)
    state = await service.graph.aget_state(config)
    pending = raw.pending_writes if raw else []
    values = raw.checkpoint["channel_values"] if raw else {}
    view = result or {}
    return {
        "evidenceKind": "real_langgraph_sqlite_process_crash_synthetic_business",
        "mode": mode, "result": result, "next": list(state.next),
        "workflowStatus": view.get("workflowStatus", state.values.get("workflowStatus")),
        "recoverable": view.get("recoverable"),
        "interrupts": sum(len(task.interrupts) for task in state.tasks),
        "savedDecision": state.values.get("decision"),
        "savedApproval": state.values.get("approval"),
        "rawCheckpointDecision": values.get("decision"),
        "rawCheckpointHasCanonical": "canonical" in values,
        "pendingDecision": any(channel == "decision" and value == "approve" for _, channel, value in pending),
        "pendingCanonical": any(channel == "canonical" and value.get("actionId") == ACTION
                                for _, channel, value in pending),
        **backend.counts(),
    }


def crash_before_checkpoint(service, backend, boundary):
    """Hold only the next checkpoint; real AsyncSqliteSaver pending writes still commit."""
    saver = service.graph.checkpointer
    original = saver.aput
    config = service.config(101, 201, ACTION)

    async def aput(checkpoint_config, checkpoint, metadata, versions):
        values = checkpoint.get("channel_values", {})
        at_boundary = (values.get("decision") == "approve" if boundary == "review"
                       else "canonical" in values and values.get("workflowStatus") == "WAITING_APPROVAL")
        if not at_boundary:
            return await original(checkpoint_config, checkpoint, metadata, versions)
        deadline = asyncio.get_running_loop().time() + 10
        while asyncio.get_running_loop().time() < deadline:
            # A separate committed read through the real saver, not an in-memory task result.
            raw = await saver.aget_tuple(config)
            writes = raw.pending_writes if raw else []
            task_writes = {}
            for task_id, channel, value in writes:
                task_writes.setdefault(task_id, {})[channel] = value
            if boundary == "review":
                durable = any(w.get("decision") == "approve" and w.get("approval") == APPROVAL
                              and w.get("workflowStatus") == "EXECUTING" for w in task_writes.values())
            else:
                durable = any(w.get("canonical", {}).get("actionId") == ACTION
                              and w.get("workflowStatus") == "WAITING_APPROVAL"
                              for w in task_writes.values())
            if durable:
                proof = await describe(service, backend, boundary + "-crash")
                assert proof["rawCheckpointDecision"] is None
                assert boundary != "start" or not proof["rawCheckpointHasCanonical"]
                assert proof["effects"] == proof["executionAttempts"] == 0
                emit(proof)
                # No context-manager cleanup or terminal checkpoint is allowed after this point.
                os._exit(CRASH_EXIT)
            await asyncio.sleep(.01)
        raise AssertionError("expected pending node writes were not durably committed before checkpoint")

    saver.aput = aput


async def main():
    mode, checkpoint, ledger = sys.argv[1:]
    backend = Backend(ledger)
    async with ActionWorkflows.open(Path(checkpoint), backend, retry_initial=.001, retry_max=.002) as service:
        if mode == "review-crash":
            crash_before_checkpoint(service, backend, "review")
            result = await service.resume(101, 201, ACTION, "approve", APPROVAL)
            raise AssertionError("review crash boundary was not reached")
        elif mode == "start-crash":
            crash_before_checkpoint(service, backend, "start")
            result = await service.start(101, 201, ACTION)
            raise AssertionError("START crash boundary was not reached")
        elif mode == "start":
            result = await service.start(101, 201, ACTION)
        elif mode == "inspect":
            result = await service.status(101, 201, ACTION)
        elif mode == "recover":
            result = await service.recover(101, 201, ACTION)
        elif mode == "resume-identical":
            result = await service.resume(101, 201, ACTION, "approve", APPROVAL)
        else:
            raise ValueError("unknown synthetic probe mode")
        emit(await describe(service, backend, mode, result))


if __name__ == "__main__":
    asyncio.run(main())
