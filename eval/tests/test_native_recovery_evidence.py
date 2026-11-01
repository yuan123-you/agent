import pytest
from eval.native_recovery_evidence import validate_trace

def test_evidence_rejects_duplicate_effects_and_unsaved_decisions():
    trace={'start':{'returncode':0,'interrupts':1,'next':['review'],'effects':0},
       'approve-crash':{'returncode':73},
       'inspect':{'returncode':0,'savedDecision':'approve','next':['execute_decision'],'effects':1,'executionAttempts':1},
       'recover':{'returncode':0,'workflowStatus':'COMPLETED','next':[],'effects':1,'executionAttempts':2},
       'recover-again':{'returncode':0,'effects':1,'executionAttempts':2},
       'wrong-owner':{'returncode':23}}
    validate_trace(trace)
    trace['recover']['effects']=2
    with pytest.raises(ValueError):validate_trace(trace)
    trace['recover']['effects']=1;trace['inspect']['savedDecision']=None
    with pytest.raises(ValueError):validate_trace(trace)


def test_pending_write_evidence_requires_a_real_wait_and_never_approves_on_start():
    from eval.native_recovery_evidence import validate_pending_traces
    review={'review-crash':{'returncode':73,'pendingDecision':True,'next':[],'effects':0},
            'inspect':{'returncode':0,'workflowStatus':'EXECUTING','recoverable':True,'savedDecision':'approve','effects':0},
            'recover':{'returncode':0,'workflowStatus':'COMPLETED','effects':1,'executionAttempts':1},
            'resume-identical':{'returncode':0,'workflowStatus':'COMPLETED','effects':1,'executionAttempts':1}}
    start={'start-crash':{'returncode':73,'pendingCanonical':True,'rawCheckpointHasCanonical':False,'next':[],'effects':0},
           'recover':{'returncode':0,'workflowStatus':'WAITING_APPROVAL','next':['review'],'interrupts':1,
                      'savedDecision':None,'effects':0},
           'resume-identical':{'returncode':0,'workflowStatus':'COMPLETED','effects':1,'executionAttempts':1}}
    validate_pending_traces({'review':review,'start':start})
    start['recover']['effects']=1
    with pytest.raises(ValueError):validate_pending_traces({'review':review,'start':start})

def test_native_source_fingerprint_is_lf_portable_but_content_bound(tmp_path):
    from eval.native_recovery_evidence import source_fingerprint
    path=tmp_path/'source.py';path.write_bytes(b'first\r\nsecond\r\n')
    original=source_fingerprint(path)
    path.write_bytes(b'first\nsecond\n')
    assert source_fingerprint(path)==original
    path.write_bytes(b'changed\nsecond\n')
    assert source_fingerprint(path)!=original
