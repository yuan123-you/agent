from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from app.api import action_workflows
from app.config import Settings

@pytest.mark.asyncio
async def test_feature_disabled_does_not_allocate_an_approval_database(tmp_path,monkeypatch):
    monkeypatch.setattr(action_workflows,'settings',SimpleNamespace(action_workflows_enabled=False))
    app=FastAPI()
    async with action_workflows.lifespan(app):assert app.state.action_workflows is None
    assert not list(tmp_path.iterdir())

@pytest.mark.asyncio
async def test_enabled_feature_opens_and_closes_a_durable_native_saver(tmp_path,monkeypatch):
    path=tmp_path/'private'/'cp.db'
    monkeypatch.setattr(action_workflows,'settings',SimpleNamespace(action_workflows_enabled=True,
        action_workflow_checkpoint_path=str(path),backend_base_url='http://backend',internal_token='test-only',
        action_workflow_callback_timeout_s=3,action_workflow_total_timeout_s=15,retry_budget_limit=6))
    app=FastAPI()
    async with action_workflows.lifespan(app):
        assert app.state.action_workflows is not None and path.is_file()
    assert app.state.action_workflows is None

@pytest.mark.asyncio
async def test_unavailable_checkpoint_fails_closed_without_a_memory_fallback(tmp_path,monkeypatch):
    parent=tmp_path/'not-a-directory';parent.write_text('fixture')
    monkeypatch.setattr(action_workflows,'settings',SimpleNamespace(action_workflows_enabled=True,
        action_workflow_checkpoint_path=str(parent/'cp.db'),backend_base_url='http://backend',internal_token='test-only',
        action_workflow_callback_timeout_s=3,action_workflow_total_timeout_s=15,retry_budget_limit=6))
    app=FastAPI()
    with pytest.raises(OSError):
        async with action_workflows.lifespan(app):pass
    assert app.state.action_workflows is None

@pytest.mark.parametrize('path',['',':memory:','file::memory:?cache=shared'])
def test_enabled_configuration_rejects_nonpersistent_checkpoints(path):
    with pytest.raises(ValueError):
        Settings(_env_file=None,action_workflows_enabled=True,action_workflow_checkpoint_path=path,internal_token='test-only')
