"""Real local process-failure evidence. No network, model calls, or real orders."""
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def source_fingerprint(path):
    """Canonical LF hash: same source after Windows/Git/Linux checkout."""
    return sha256(Path(path).read_bytes().replace(b"\r\n",b"\n")).hexdigest()


def validate_trace(trace):
    """Fail closed: raw observations must prove every advertised invariant."""
    start, pending, recovered, again = (trace[k] for k in ('start','inspect','recover','recover-again'))
    checks = [
        start.get('returncode') == 0 and start.get('interrupts') == 1
            and start.get('next') == ['review'] and start.get('effects') == 0,
        trace['approve-crash'].get('returncode') == 73,
        pending.get('returncode') == 0 and pending.get('savedDecision') == 'approve'
            and pending.get('next') == ['execute_decision'] and pending.get('effects') == 1
            and pending.get('executionAttempts') == 1,
        recovered.get('returncode') == 0 and recovered.get('workflowStatus') == 'COMPLETED'
            and recovered.get('next') == [] and recovered.get('effects') == 1
            and recovered.get('executionAttempts') == 2,
        again.get('returncode') == 0 and again.get('effects') == 1 and again.get('executionAttempts') == 2,
        trace['wrong-owner'].get('returncode') == 23,
    ]
    if not all(checks):
        raise ValueError('native process recovery evidence failed; no success may be claimed')


def validate_pending_traces(traces):
    review, start = traces['review'], traces['start']
    completed = lambda row: (row.get('returncode') == 0 and row.get('workflowStatus') == 'COMPLETED'
                            and row.get('effects') == row.get('executionAttempts') == 1)
    checks = [
        review['review-crash'].get('returncode') == 73 and review['review-crash'].get('pendingDecision') is True
            and review['review-crash'].get('next') == [] and review['review-crash'].get('effects') == 0,
        review['inspect'].get('returncode') == 0 and review['inspect'].get('workflowStatus') == 'EXECUTING'
            and review['inspect'].get('recoverable') is True and review['inspect'].get('savedDecision') == 'approve'
            and review['inspect'].get('effects') == 0,
        completed(review['recover']), completed(review['resume-identical']),
        start['start-crash'].get('returncode') == 73 and start['start-crash'].get('pendingCanonical') is True
            and start['start-crash'].get('rawCheckpointHasCanonical') is False
            and start['start-crash'].get('next') == [] and start['start-crash'].get('effects') == 0,
        start['recover'].get('returncode') == 0 and start['recover'].get('workflowStatus') == 'WAITING_APPROVAL'
            and start['recover'].get('next') == ['review'] and start['recover'].get('interrupts') == 1
            and start['recover'].get('savedDecision') is None and start['recover'].get('effects') == 0,
        completed(start['resume-identical']),
    ]
    if not all(checks):
        raise ValueError('pending task-write crash evidence failed')


def main():
    worker = ROOT / 'ai-service/tests/fixtures/action_workflow_worker.py'
    allowed = {'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','HOME','USERPROFILE'}
    env = {k:v for k,v in os.environ.items() if k in allowed}
    env.update(PYTHONPATH=str(ROOT/'ai-service'), PYTHONIOENCODING='utf-8')
    traces = {}
    pending_traces = {}
    with tempfile.TemporaryDirectory(prefix='native-recovery-proof-') as tmp:
        for label in ('start','approve-crash','inspect','recover','recover-again','wrong-owner'):
            mode = 'recover' if label == 'recover-again' else label
            run = subprocess.run([sys.executable,str(worker),mode,
                    str(Path(tmp)/'checkpoint.db'),str(Path(tmp)/'ledger.db')],
                env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
            rows = [json.loads(line.removeprefix('NATIVE_PROOF ')) for line in run.stdout.splitlines()
                    if line.startswith('NATIVE_PROOF ')]
            traces[label] = {**(rows[-1] if rows else {}),'returncode':run.returncode}
    pending_worker = ROOT / 'ai-service/tests/fixtures/action_review_pending_worker.py'
    for boundary, modes in (
        ('review', ('start','review-crash','inspect','recover','resume-identical')),
        ('start', ('start-crash','recover','resume-identical')),
    ):
        pending_traces[boundary] = {}
        with tempfile.TemporaryDirectory(prefix='native-pending-proof-') as tmp:
            for mode in modes:
                run = subprocess.run([sys.executable,'-B',str(pending_worker),mode,
                    str(Path(tmp)/'checkpoint.db'),str(Path(tmp)/'ledger.db')],
                    env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
                rows = [json.loads(line.removeprefix('NATIVE_PROOF ')) for line in run.stdout.splitlines()
                        if line.startswith('NATIVE_PROOF ')]
                pending_traces[boundary][mode] = {**(rows[-1] if rows else {}),'returncode':run.returncode}
    git = subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True)
    dirty = subprocess.run(['git','status','--porcelain'],cwd=ROOT,capture_output=True,text=True,check=True)
    paths = ['ai-service/app/agent/action_workflow.py','ai-service/app/resilience.py',
             'ai-service/tests/fixtures/action_workflow_worker.py',
             'ai-service/tests/fixtures/action_review_pending_worker.py','eval/native_recovery_evidence.py']
    report = {'status':'not_verified','generated_at':datetime.now(timezone.utc).isoformat(),
        'scope':'real LangGraph + durable SQLite + real process exit; synthetic idempotent business ledger',
        'limits':['not live Java/Python integration','not a real order/payment/refund',
                  'single process-local coordinator; not multi-instance HA',
                  'no model accuracy or production SLA measurement'],
        'provenance':{'base_commit':git.stdout.strip(),'uncommitted_changes':bool(dirty.stdout.strip()),
           'python':platform.python_version(),
           'packages':{p:version(p) for p in ('langgraph','langgraph-checkpoint-sqlite','aiosqlite')},
           'source_hash_mode':'utf8-lf','sha256':{p:source_fingerprint(ROOT/p) for p in paths}},'trace':traces, 'pending_write_traces':pending_traces}
    try:
        validate_trace(traces)
        validate_pending_traces(pending_traces)
    except ValueError:
        print(json.dumps(report,ensure_ascii=False,indent=2));raise SystemExit(1)
    report['status']='verified'
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
