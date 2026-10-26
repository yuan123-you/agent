"""Version cleanup must never delete a newer task's vectors; no live Milvus."""
import operator
import re
from unittest.mock import AsyncMock

import pytest

from app.api import kb
from app.rag import ingest
from app.rag.vectorstore import VectorStore


class ScalarFilterMilvus:
    """Storage-boundary fake that applies the actual emitted scalar filter to rows."""

    def __init__(self):
        self.rows = [
            {"id": 101, "doc_id": 7, "doc_version": 1},
            {"id": 102, "doc_id": 7, "doc_version": 2},
            {"id": 103, "doc_id": 7, "doc_version": 3},
            {"id": 104, "doc_id": 7, "doc_version": 4},
            {"id": 801, "doc_id": 8, "doc_version": 1},
        ]

    def delete(self, *, collection_name, filter):
        comparisons = {"==": operator.eq, "!=": operator.ne, "<": operator.lt}
        conditions = []
        for clause in filter.split(" and "):
            match = re.fullmatch(r"(doc_id|doc_version) (==|!=|<) (\d+)", clause)
            assert match is not None, f"unsupported Milvus scalar filter: {filter}"
            field, comparison, value = match.groups()
            conditions.append((field, comparisons[comparison], int(value)))
        kept = [row for row in self.rows if not all(
            comparison(row[field], value) for field, comparison, value in conditions
        )]
        deleted = len(self.rows) - len(kept)
        self.rows = kept
        return {"delete_count": deleted}

    def has_collection(self, name):
        return False

    def insert(self, *, collection_name, data):
        self.rows.extend(data)

    def ids(self):
        return {row["id"] for row in self.rows}


def store_with_versions():
    store = VectorStore.__new__(VectorStore)
    store.client = ScalarFilterMilvus()
    return store


@pytest.mark.asyncio
async def test_v2_cleanup_preserves_its_own_and_all_future_versions():
    store = store_with_versions()

    result = await store.delete_by_doc(7, exclude_version=2)

    assert store.client.ids() == {102, 103, 104, 801}
    assert result == {"delete_count": 1}


@pytest.mark.asyncio
async def test_v3_cleanup_removes_v1_v2_but_preserves_v3_and_future_versions():
    store = store_with_versions()

    result = await store.delete_by_doc(7, exclude_version=3)

    assert store.client.ids() == {103, 104, 801}
    assert result == {"delete_count": 2}


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [None, 0])
async def test_unversioned_delete_removes_every_version_only_for_the_requested_doc(version):
    store = store_with_versions()

    result = await store.delete_by_doc(7, exclude_version=version)

    assert store.client.ids() == {801}
    assert result == {"delete_count": 4}


@pytest.mark.asyncio
@pytest.mark.parametrize("version,expected", [(2, {102, 103, 104, 801}), (3, {103, 104, 801})])
async def test_versioned_delete_api_uses_the_same_safe_upper_bound(monkeypatch, version, expected):
    store = store_with_versions()
    monkeypatch.setattr(kb, "get_vectorstore", lambda: store)

    await kb.delete_doc(7, version=version)

    assert store.client.ids() == expected


@pytest.mark.asyncio
async def test_disable_and_delete_version_zero_api_still_remove_all_doc_versions(monkeypatch):
    # Both backend lifecycle operations call this route with version=0.
    store = store_with_versions()
    monkeypatch.setattr(kb, "get_vectorstore", lambda: store)

    result = await kb.delete_doc(7, version=0)

    assert store.client.ids() == {801}
    assert result == {"deleted": {"delete_count": 4}}


@pytest.mark.asyncio
async def test_delete_api_default_still_removes_all_doc_versions(monkeypatch):
    store = store_with_versions()
    monkeypatch.setattr(kb, "get_vectorstore", lambda: store)

    await kb.delete_doc(7)

    assert store.client.ids() == {801}


@pytest.mark.asyncio
@pytest.mark.parametrize("version,expected", [
    (2, {102, 103, 104, 202, 801}),
    (3, {103, 104, 203, 801}),
])
async def test_ingest_cleanup_cannot_delete_vectors_from_a_newer_task(monkeypatch, version, expected):
    store = store_with_versions()
    monkeypatch.setattr(ingest, "get_vectorstore", lambda: store)
    embeddings = type("Embeddings", (), {"aembed_documents": AsyncMock(return_value=[[0.1, 0.2]])})()
    monkeypatch.setattr(ingest, "get_embeddings", lambda: embeddings)
    backend = type("Backend", (), {
        "download_file": AsyncMock(return_value=b"policy"),
        "kb_chunks_batch": AsyncMock(return_value={"ids": [200 + version]}),
        "kb_result": AsyncMock(),
    })()
    monkeypatch.setattr(ingest, "backend_client", backend)

    await ingest.run_ingest(ingest.IngestTask(
        doc_id=7, doc_type="POLICY", doc_version=version,
        file_url="/internal/files/7", file_format="TXT",
    ))

    assert store.client.ids() == expected
    assert next(row for row in store.client.rows if row["id"] == 200 + version)["doc_version"] == version
    backend.kb_result.assert_awaited_once_with(7, "ACTIVE", 1, vector_count=1, doc_version=version)
