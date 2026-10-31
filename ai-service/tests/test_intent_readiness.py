"""Dedicated intent readiness must not be hidden by a healthy generator."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.api import health


@pytest.mark.parametrize('failure', ['missing-model', 'http-error', 'timeout'])
async def test_readiness_detects_unavailable_dedicated_intent(monkeypatch, failure):
    monkeypatch.setattr(health, 'settings', SimpleNamespace(
        llm_api_base='http://generation/v1', llm_api_key='generation-key',
        llm_intent_api_base='http://intent/v1', llm_intent_api_key='intent-key',
        llm_intent_model='candidate:7b',
    ))
    for name in ('_check_milvus', '_check_llm', '_check_backend'):
        monkeypatch.setattr(health, name, AsyncMock(return_value=True))
    def handle(request):
        assert str(request.url) == 'http://intent/v1/models'
        assert request.headers['Authorization'] == 'Bearer intent-key'
        if failure == 'timeout':
            raise httpx.ReadTimeout('intent timeout')
        return httpx.Response(503 if failure == 'http-error' else 200, json={'data': []})
    original = httpx.AsyncClient
    monkeypatch.setattr(health.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    result = await health.ready()
    assert isinstance(result, health.Response) and result.status_code == 503
    assert 'intent_llm' in result.body.decode()


async def test_readiness_accepts_installed_intent_model(monkeypatch):
    monkeypatch.setattr(health, 'settings', SimpleNamespace(
        llm_api_base='http://generation/v1', llm_api_key='shared-key',
        llm_intent_api_base='http://intent/v1', llm_intent_api_key='',
        llm_intent_model='candidate:7b',
    ))
    for name in ('_check_milvus', '_check_llm', '_check_backend'):
        monkeypatch.setattr(health, name, AsyncMock(return_value=True))
    def handle(request):
        assert request.headers['Authorization'] == 'Bearer shared-key'
        return httpx.Response(200, json={'data': [{'id': 'candidate:7b'}]})
    original = httpx.AsyncClient
    monkeypatch.setattr(health.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    result = await health.ready()
    assert result['status'] == 'UP' and result['dependencies']['intent_llm'] is True


async def test_shared_provider_does_not_add_duplicate_intent_probe(monkeypatch):
    monkeypatch.setattr(health, 'settings', SimpleNamespace(llm_intent_api_base=''))
    for name in ('_check_milvus', '_check_llm', '_check_backend'):
        monkeypatch.setattr(health, name, AsyncMock(return_value=True))
    def forbidden(**kw):
        pytest.fail('shared-provider readiness must not add another network call')
    monkeypatch.setattr(health.httpx, 'AsyncClient', forbidden)
    assert (await health.ready())['status'] == 'UP'
