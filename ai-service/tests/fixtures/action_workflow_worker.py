"""Synthetic business ledger + real LangGraph/SQLite; never a production action."""
import asyncio,json,os,sqlite3,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
from app.agent.action_workflow import ActionWorkflows,WorkflowConflict

mode,checkpoint,ledger=sys.argv[1:]
ACTION="act_33333333-3333-4333-8333-333333333333"
class Backend:
    def __init__(self):
        with sqlite3.connect(ledger) as c:
            c.execute('CREATE TABLE IF NOT EXISTS effects(action_id TEXT PRIMARY KEY,receipt TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY,action_id TEXT NOT NULL)')
    async def snapshot(self,user_id,action_id):
        if user_id!=101 or action_id!=ACTION:raise WorkflowConflict('owner mismatch')
        with sqlite3.connect(ledger) as c:done=c.execute('SELECT 1 FROM effects WHERE action_id=?',(ACTION,)).fetchone()
        return {'actionId':ACTION,'userId':101,'conversationId':201,'type':'ORDER_CREATE',
          'status':'CONFIRMED' if done else 'PENDING','expiresAt':'2099-01-01T00:00:00+00:00','fingerprint':'a'*64}
    async def execute(self,user_id,action_id,approval):
        receipt={'type':'ORDER_CREATE','actionStatus':'CONFIRMED','orderId':42,'orderNo':'SYNTHETIC42'}
        with sqlite3.connect(ledger) as c:
            c.execute('INSERT INTO attempts(action_id) VALUES(?)',(action_id,))
            c.execute('INSERT OR IGNORE INTO effects VALUES(?,?)',(action_id,json.dumps(receipt)))
        if mode=='approve-crash':os._exit(73) # effect committed; no graph return/checkpoint
        return receipt
    async def cancel(self,user_id,action_id):return {'type':'ORDER_CREATE','actionStatus':'CANCELLED'}
async def main():
    backend=Backend()
    async with ActionWorkflows.open(checkpoint,backend,retry_initial=.001,retry_max=.002) as service:
        if mode=='start':result=await service.start(101,201,ACTION)
        elif mode=='approve-crash':result=await service.resume(101,201,ACTION,'approve',None)
        elif mode=='recover':result=await service.recover(101,201,ACTION)
        elif mode=='inspect':result=await service.status(101,201,ACTION)
        elif mode=='wrong-owner':result=await service.recover(102,201,ACTION)
        else:raise ValueError('unknown test mode')
        state=await service.graph.aget_state(service.config(101,201,ACTION))
        with sqlite3.connect(ledger) as c:
            effects=c.execute('SELECT COUNT(*) FROM effects').fetchone()[0]
            attempts=c.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]
        print('NATIVE_PROOF '+json.dumps({'mode':mode,'workflowStatus':result['workflowStatus'],
            'next':list(state.next),'interrupts':sum(len(t.interrupts) for t in state.tasks),
            'savedDecision':state.values.get('decision'),'effects':effects,'executionAttempts':attempts}),flush=True)
try:asyncio.run(main())
except WorkflowConflict:
    print('OWNER_REJECTED',flush=True);sys.exit(23)
