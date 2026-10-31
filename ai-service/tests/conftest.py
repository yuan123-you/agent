"""ai-service 单元测试公共配置。

- 强制关闭 Langfuse tracing 与联网，避免单测依赖外部服务/网络。
- 关闭 product sync 后台 job（测试环境不连 Milvus）。
"""
import os

os.environ.setdefault("LANGFUSE_ENABLED", "false")
os.environ.setdefault("PRODUCT_SYNC_ENABLED", "false")
os.environ.setdefault("LOG_LEVEL", "ERROR")

import pytest

from app.config import settings
from app.rag import product_index as _pi_mod
from app.rag import vectorstore as _vs_mod


class _FakeVectorStore:
    """内存 fake：替换惰性 getter，任何检索/写入都返回空结果，不触达 Milvus。"""
    client = None

    def ensure_collection(self) -> None:
        return None

    async def search(self, query, top_k=20, **_compat) -> dict:
        return {"hits": [], "total": 0}

    async def existing_ids(self, ids, include_legacy=True) -> set[int]:
        return set()

    async def insert(self, rows) -> None:
        return None

    async def delete_by_doc(self, doc_id, exclude_version=None) -> dict:
        return {"deleteCount": 0}


class _FakeProductIndex:
    """内存 fake：语料与向量召回均置空（corpus 未就绪 → 检索降级后端 SQL）。"""
    client = None

    def __init__(self):
        self.corpus = _FakeProductIndex._Corpus()

    class _Corpus:
        def __init__(self):
            self.products = {}

        def ready(self) -> bool:
            return False

        def structured(self, *a, **k) -> list:
            return []

        def bm25_recall(self, *a, **k) -> list:
            return []

        def rebuild(self, products, texts) -> None:
            return None

        def clear(self) -> None:
            self.products = {}

    def ensure_collection(self) -> None:
        return None

    async def upsert(self, rows) -> None:
        return None

    async def delete_old_versions(self, version) -> None:
        return None

    async def vector_recall(self, query, category, min_price, max_price, k) -> list:
        return []


@pytest.fixture(autouse=True)
def _fake_retrievers(monkeypatch):
    """无 Milvus 环境：用内存 fake 替换惰性 getter，保证任何检索入口都不触达 Milvus。"""
    monkeypatch.setattr(_vs_mod, "get_vectorstore", lambda: _FakeVectorStore())
    monkeypatch.setattr(_pi_mod, "get_product_index", lambda: _FakeProductIndex())


@pytest.fixture(autouse=True)
def _no_network():
    """确保单测在关闭 tracing 的前提下进行（不触发外部依赖）。"""
    assert settings.langfuse_enabled is False


@pytest.fixture(autouse=True)
def _offline_semantic_routing(monkeypatch):
    """Semantic unit tests inject vectors; unrelated model tests abstain without networking."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.agent import nodes
    monkeypatch.setattr(nodes, "get_semantic_router", lambda: SimpleNamespace(classify=AsyncMock(return_value=None)))
    monkeypatch.setattr(nodes, "get_intent_llm", lambda: SimpleNamespace(
        ainvoke=AsyncMock(side_effect=RuntimeError("Offline test: inject semantic/model decision explicitly"))))


@pytest.fixture
def semantic_route(monkeypatch):
    """Inject a validated semantic result when testing consumers, not embedding accuracy."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.agent import nodes
    from app.agent.request_decision import RequestDecision
    def choose(intent, next_step=None, missing=None):
        decision=RequestDecision(intent, next_step or ("retrieve" if intent=="AFTER_SALE_FAQ" else "assist"),
                                 missing, source="embedding",score=.95,margin=.2)
        router=SimpleNamespace(classify=AsyncMock(return_value=decision))
        monkeypatch.setattr(nodes,"get_semantic_router",lambda:router)
        from langchain_core.messages import AIMessage
        import json
        model=SimpleNamespace(ainvoke=AsyncMock(return_value=AIMessage(content=json.dumps({
            "intent":intent,"next_step":decision.next_step,"missing":missing}))))
        monkeypatch.setattr(nodes,"get_intent_llm",lambda:model)
        return router
    return choose
