import asyncio,time
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx,pytest
from app.api import health

@pytest.mark.asyncio
async def test_dependency_probes_are_parallel_single_shot_and_share_total_budget(monkeypatch):
    calls=[]
    async def slow(name):calls.append(name);await asyncio.sleep(.2);return True
    monkeypatch.setattr(health,'_HEALTH_TIMEOUT_S',.03,raising=False)
    monkeypatch.setattr(health,'_check_milvus',lambda:slow('milvus'))
    monkeypatch.setattr(health,'_check_llm',lambda:slow('llm'))
    monkeypatch.setattr(health,'_check_backend',lambda:slow('backend'))
    result=await asyncio.wait_for(health._probe_all(),timeout=.15)
    assert result=={'milvus':False,'llm':False,'backend':False}
    assert sorted(calls)==['backend','llm','milvus']

@pytest.mark.asyncio
async def test_health_http_has_no_retry_even_on_service_unavailable(monkeypatch):
    calls=[];original=httpx.AsyncClient
    async def handler(request):calls.append(request);return httpx.Response(503)
    monkeypatch.setattr(health.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    assert await health._check_llm() is False
    assert await health._check_backend() is False
    assert len(calls)==2
