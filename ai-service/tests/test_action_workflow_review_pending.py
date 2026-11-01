"""Recovery must not mistake durable pending-node output for a terminal workflow."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).parent / "fixtures" / "action_review_pending_worker.py"
PROOF_PREFIX = "NATIVE_PROOF "


def worker(tmp_path, mode, expected_exit=0):
    env = {key: value for key, value in os.environ.items()
           if key in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE"}}
    env.update(PYTHONPATH=str(SCRIPT.parents[2]), PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    process = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), mode, str(tmp_path / "checkpoint.db"), str(tmp_path / "business-ledger.db")],
        capture_output=True, text=True, encoding="utf-8", env=env, timeout=30,
    )
    assert process.returncode == expected_exit, process.stdout + process.stderr
    proofs = [json.loads(line.removeprefix(PROOF_PREFIX)) for line in process.stdout.splitlines()
              if line.startswith(PROOF_PREFIX)]
    assert len(proofs) == 1, process.stdout + process.stderr
    proof = proofs[0]
    assert proof["evidenceKind"] == "real_langgraph_sqlite_process_crash_synthetic_business"
    if proof["result"] is not None:
        assert proof["workflowStatus"] == proof["result"]["workflowStatus"]
        assert proof["recoverable"] is proof["result"]["recoverable"]
    return proof


def pending_review(tmp_path):
    started = worker(tmp_path, "start")
    assert started["result"]["interrupted"] is True and started["interrupts"] == 1
    assert started["effects"] == started["executionAttempts"] == 0
    crashed = worker(tmp_path, "review-crash", expected_exit=73)
    assert crashed["pendingDecision"] is True
    assert crashed["rawCheckpointDecision"] is None
    assert crashed["savedDecision"] == "approve" and crashed["next"] == []
    assert crashed["savedApproval"]["receiverAddress"] == "Synthetic approved address"
    assert crashed["effects"] == crashed["executionAttempts"] == 0
    return worker(tmp_path, "inspect")


def assert_completed_once(proof):
    assert proof["workflowStatus"] == "COMPLETED", proof
    assert proof["recoverable"] is False
    assert proof["savedDecision"] == "approve"
    assert proof["result"]["recoverable"] is False
    assert proof["result"]["interrupted"] is False
    assert proof["result"]["result"]["orderId"] == 42
    assert proof["result"]["result"]["receiverAddress"] == "Synthetic approved address"
    assert proof["next"] == []
    assert proof["effects"] == proof["executionAttempts"] == 1


def test_pending_review_decision_is_advertised_recoverable_without_executing(tmp_path):
    pending = pending_review(tmp_path)
    assert pending["workflowStatus"] == "EXECUTING"
    assert pending["recoverable"] is True
    assert pending["result"]["recoverable"] is True
    assert pending["result"]["interrupted"] is False
    assert pending["savedDecision"] == "approve"
    assert pending["effects"] == pending["executionAttempts"] == 0


@pytest.mark.parametrize("entrypoint", ["recover", "resume-identical"])
def test_pending_review_decision_finishes_exactly_once_after_process_restart(tmp_path, entrypoint):
    pending = pending_review(tmp_path)
    assert_completed_once(worker(tmp_path, entrypoint))
    assert pending["result"]["recoverable"] is True
    # Both APIs must subsequently return the same receipt, without even another business callback.
    assert_completed_once(worker(tmp_path, "recover"))
    assert_completed_once(worker(tmp_path, "resume-identical"))


@pytest.mark.parametrize("entrypoint", ["start", "recover"])
def test_pending_initial_registration_reaches_a_real_interrupt_without_approval(tmp_path, entrypoint):
    crashed = worker(tmp_path, "start-crash", expected_exit=73)
    assert crashed["pendingCanonical"] is True
    assert crashed["rawCheckpointHasCanonical"] is False
    assert crashed["savedDecision"] is None and crashed["next"] == []
    assert crashed["interrupts"] == 0
    assert crashed["effects"] == crashed["executionAttempts"] == 0
    repaired = worker(tmp_path, entrypoint)
    assert repaired["result"]["workflowStatus"] == "WAITING_APPROVAL"
    assert repaired["result"]["interrupted"] is True, repaired
    assert repaired["result"]["recoverable"] is True
    assert repaired["next"] == ["review"] and repaired["interrupts"] == 1
    assert repaired["savedDecision"] is None
    assert repaired["effects"] == repaired["executionAttempts"] == 0
    waiting = worker(tmp_path, "recover")
    assert waiting["result"]["interrupted"] is True
    assert waiting["savedDecision"] is None
    assert waiting["effects"] == waiting["executionAttempts"] == 0
    # Only a subsequent explicit approval may produce the synthetic business effect.
    assert_completed_once(worker(tmp_path, "resume-identical"))
    assert_completed_once(worker(tmp_path, "recover"))
