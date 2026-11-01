"""Real process death/restart evidence, using a synthetic idempotent business ledger."""
import json,os,subprocess,sys
from pathlib import Path


def worker(tmp_path,mode):
    script=Path(__file__).parent/'fixtures'/'action_workflow_worker.py'
    env={k:v for k,v in os.environ.items() if k in {'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','HOME','USERPROFILE'}}
    env['PYTHONPATH']=str(script.parents[2]);env['PYTHONIOENCODING']='utf-8'
    result=subprocess.run([sys.executable,str(script),mode,str(tmp_path/'checkpoint.db'),str(tmp_path/'business-ledger.db')],
        capture_output=True,text=True,encoding='utf-8',env=env,timeout=30)
    rows=[json.loads(l.removeprefix('NATIVE_PROOF ')) for l in result.stdout.splitlines() if l.startswith('NATIVE_PROOF ')]
    return result,rows[-1] if rows else None


def test_restart_and_crash_after_commit_before_checkpoint_have_one_business_effect(tmp_path):
    process,first=worker(tmp_path,'start')
    assert process.returncode==0,process.stderr
    assert first['interrupts']==1 and first['next']==['review'] and first['effects']==0
    crashed,_=worker(tmp_path,'approve-crash')
    assert crashed.returncode==73
    _,pending=worker(tmp_path,'inspect')
    assert pending['savedDecision']=='approve' and pending['next']==['execute_decision']
    assert pending['effects']==1 and pending['executionAttempts']==1
    process,recovered=worker(tmp_path,'recover')
    assert process.returncode==0,process.stderr
    assert recovered['workflowStatus']=='COMPLETED' and recovered['next']==[]
    assert recovered['effects']==1 and recovered['executionAttempts']==2
    _,again=worker(tmp_path,'recover')
    assert again['effects']==1 and again['executionAttempts']==2
    denied,_=worker(tmp_path,'wrong-owner')
    assert denied.returncode==23
