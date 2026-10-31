from types import SimpleNamespace
import httpx,pytest
from app.clients import llm

def config(**overrides):
    return SimpleNamespace(**{**dict(llm_warmup_enabled=True,llm_api_base='http://ollama:11434/v1',llm_chat_model='existing-model',llm_intent_model='existing-model',llm_keep_alive_s=-1,llm_warmup_timeout_s=45),**overrides})

async def test_startup_primes_static_classification_and_knowledge_prefixes_before_user_requests(monkeypatch):
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
    assert 'route' in calls[0][1]['messages'][0]['content'] and 'HELP' in calls[0][1]['messages'][0]['content']
    assert 'points' in calls[1][1]['messages'][0]['content'] and 'sources' in calls[1][1]['messages'][0]['content']

async def test_normal_external_provider_configuration_never_triggers_native_warmup(monkeypatch):
    monkeypatch.setattr(llm,'settings',config(llm_warmup_enabled=False,llm_api_base='https://provider.example/v1'))
    def forbidden(**kw): pytest.fail('A normal external provider must not receive Ollama native requests')
    monkeypatch.setattr(llm.httpx,'AsyncClient',forbidden)
    await llm.warm_local_models()

async def test_independent_intent_service_warms_its_own_endpoint(monkeypatch):
    calls=[]
    def handle(request):
        import json
        calls.append((str(request.url), json.loads(request.content)))
        return httpx.Response(200, json={'done':True})
    original=httpx.AsyncClient
    monkeypatch.setattr(llm, 'settings', config(
        llm_intent_api_base='http://intent:11434/v1', llm_intent_model='candidate-model'))
    monkeypatch.setattr(llm.httpx, 'AsyncClient', lambda **kw:original(transport=httpx.MockTransport(handle), **kw))
    await llm.warm_local_models()
    assert [(url, payload['model']) for url, payload in calls] == [
        ('http://intent:11434/api/chat', 'candidate-model'),
        ('http://ollama:11434/api/chat', 'existing-model'),
    ]

@pytest.mark.parametrize('failure', ['http-error', 'timeout'])
async def test_failed_intent_warmup_does_not_skip_generation(monkeypatch, failure):
    calls=[]
    async def handle(request):
        calls.append(str(request.url))
        if request.url.host == 'intent':
            if failure == 'timeout':
                import asyncio
                await asyncio.sleep(10)
            return httpx.Response(404, json={'error':'candidate missing'})
        return httpx.Response(200, json={'done': True})
    original=httpx.AsyncClient
    monkeypatch.setattr(llm, 'settings', config(
        llm_intent_api_base='http://intent:11434/v1', llm_warmup_timeout_s=0.05))
    monkeypatch.setattr(llm.httpx, 'AsyncClient', lambda **kw:original(transport=httpx.MockTransport(handle), **kw))
    await llm.warm_local_models()
    assert 'http://ollama:11434/api/chat' in calls

async def test_local_embedding_weights_are_primed_without_writing_any_index(monkeypatch):
    from unittest.mock import AsyncMock
    embed=AsyncMock(return_value=[0.0]*768)
    monkeypatch.setattr(llm,'settings',config(embedding_provider='ollama'))
    monkeypatch.setattr(llm,'get_embeddings',lambda:SimpleNamespace(aembed_query=embed))
    original=httpx.AsyncClient
    monkeypatch.setattr(llm.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(
        lambda request:httpx.Response(200,json={'done':True})),**kw))
    await llm.warm_local_models()
    embed.assert_awaited_once()

@pytest.mark.parametrize("provider", ["openai", "maas"])
async def test_local_warmup_never_embeds_with_external_provider(monkeypatch, provider):
    monkeypatch.setattr(llm, "settings", config(embedding_provider=provider))
    monkeypatch.setattr(llm, "get_embeddings", lambda: pytest.fail("external embedding billing"))
    original = httpx.AsyncClient
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kw: original(
        transport=httpx.MockTransport(lambda request: httpx.Response(200)), **kw))
    await llm.warm_local_models()

async def test_embedding_warmup_is_bounded_and_does_not_skip_other_models(monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock
    async def slow_embed(text):
        await asyncio.sleep(10)
    embed = AsyncMock(side_effect=slow_embed)
    monkeypatch.setattr(llm, "settings", config(embedding_provider="ollama", llm_warmup_timeout_s=0.05))
    monkeypatch.setattr(llm, "get_embeddings", lambda: SimpleNamespace(aembed_query=embed))
    calls = []
    def handle(request):
        calls.append(str(request.url))
        return httpx.Response(200)
    original = httpx.AsyncClient
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kw: original(
        transport=httpx.MockTransport(handle), **kw))
    async with asyncio.timeout(0.5):
        await llm.warm_local_models()
    assert len(calls) == 2
    embed.assert_awaited_once()
