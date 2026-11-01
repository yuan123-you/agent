import pytest
from app.config import settings
from app.tools import tools

@pytest.mark.asyncio
@pytest.mark.parametrize('name,args',[
    ('order_create',{'product_id':11}),
    ('order_cancel_prepare',{'order_id':30}),
    ('after_sale_prepare',{'order_id':30,'order_item_id':41,'service_type':'RETURN_REFUND','issue_category':'QUALITY','reason':'fixture'}),
])
async def test_preparation_identity_is_hidden_injected_and_stable(monkeypatch,name,args):
    monkeypatch.setattr(settings,'action_workflows_enabled',True)
    calls=[]
    async def prepare(**kwargs):
        calls.append(kwargs);return {'actionId':'act_fixture'}
    target={'order_create':'order_prepare'}.get(name,name)
    monkeypatch.setattr(tools.backend_client,target,prepare)
    tools.set_tool_ctx({'user_id':7,'conversation_id':9})
    tool=getattr(tools,name)
    schema=tool.tool_call_schema.model_json_schema()
    assert 'tool_call_id' not in schema.get('properties',{})
    for _ in range(2):
        await tool.ainvoke({'name':name,'id':'call_stable_1','type':'tool_call',
                           'args':{**args,'tool_call_id':'forged'}})
    assert len(calls)==2
    assert calls[0]['preparation_key']==calls[1]['preparation_key']=='call_stable_1'

@pytest.mark.asyncio
async def test_native_preparation_requires_a_real_toolcall(monkeypatch):
    monkeypatch.setattr(settings,'action_workflows_enabled',True)
    with pytest.raises(ValueError):
        await tools.order_create.ainvoke({'product_id':11,'tool_call_id':'forged'})

@pytest.mark.asyncio
async def test_legacy_preparation_does_not_send_a_native_key(monkeypatch):
    monkeypatch.setattr(settings,'action_workflows_enabled',False)
    calls=[]
    async def prepare(**kwargs):calls.append(kwargs);return {'actionId':'legacy'}
    monkeypatch.setattr(tools.backend_client,'order_prepare',prepare)
    tools.set_tool_ctx({'user_id':7,'conversation_id':9})
    await tools.order_create.ainvoke({'name':'order_create','id':'call_legacy','type':'tool_call','args':{'product_id':11}})
    assert 'preparation_key' not in calls[0]
