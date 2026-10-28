from types import SimpleNamespace
import httpx,pytest
from app.clients import llm

def config(**overrides):
    return SimpleNamespace(**{**dict(llm_warmup_enabled=True,llm_api_base='http://ollama:11434/v1',llm_chat_model='existing-model',llm_intent_model='existing-model',llm_keep_alive_s=-1,llm_warmup_timeout_s=45),**overrides})

async def test_startup_primes_static_classification_and_web_prefixes_before_user_requests(monkeypatch):
    calls=[]
    def handle(request):
        import json
        calls.append((str(request.url),json.loads(request.content)))
        return httpx.Response(200,json={'done':True,'response':''})
    original=httpx.AsyncClient
    monkeypatch.setattr(llm,'settings',config())
    monkeypatch.setattr(llm.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handle),**kw))
    await llm.warm_local_models()
    assert len(calls)==2
    assert all(url=='http://ollama:11434/api/chat' for url,payload in calls)
    assert all(payload['model']=='existing-model' and payload['keep_alive']==-1 for url,payload in calls)
    assert all(payload['options']['num_predict']==1 for url,payload in calls)
    assert all(payload['messages'][0]['role']=='system' for url,payload in calls)
    assert '意图分类器' in calls[0][1]['messages'][0]['content']
    assert '联网问答' in calls[1][1]['messages'][0]['content']

async def test_normal_external_provider_configuration_never_triggers_native_warmup(monkeypatch):
    monkeypatch.setattr(llm,'settings',config(llm_warmup_enabled=False,llm_api_base='https://provider.example/v1'))
    def forbidden(**kw): pytest.fail('A normal external provider must not receive Ollama native requests')
    monkeypatch.setattr(llm.httpx,'AsyncClient',forbidden)
    await llm.warm_local_models()
