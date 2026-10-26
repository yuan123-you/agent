"""Task versions must survive every ingestion callback; no external services."""
import json
from unittest.mock import AsyncMock

import httpx
import pytest

from app.clients.backend_client import BackendClient
from app.rag import ingest
from app.rag.ingest import IngestTask


@pytest.mark.asyncio
async def test_backend_callbacks_serialize_task_version_without_changing_positional_arguments():
    requests = []

    async def handle(request):
        requests.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"code": 0, "data": {"ids": [101]}})

    client = BackendClient.__new__(BackendClient)
    async with httpx.AsyncClient(base_url="http://backend.test", transport=httpx.MockTransport(handle)) as transport:
        client._long_client = transport
        chunks = [{"chunkIndex": 0, "content": "policy", "tokenCount": 3}]
        assert await client.kb_chunks_batch(7, chunks, doc_version=4) == {"ids": [101]}
        await client.kb_result(7, "ACTIVE", 1, None, 1, doc_version=4)
        await client.kb_result(7, "FAILED", 0, "parse failed", doc_version=4)

    assert requests == [
        ("/internal/kb/chunks/batch", {"docId": 7, "docVersion": 4, "chunks": chunks}),
        ("/internal/kb/result", {"docId": 7, "docVersion": 4, "status": "ACTIVE",
                                 "chunkCount": 1, "failReason": None, "vectorCount": 1}),
        ("/internal/kb/result", {"docId": 7, "docVersion": 4, "status": "FAILED",
                                 "chunkCount": 0, "failReason": "parse failed"}),
    ]


class RecordingBackend:
    def __init__(self, mode):
        self.mode = mode
        self.batches = []
        self.results = []

    async def download_file(self, url):
        return b"" if self.mode == "empty" else b"policy"

    async def kb_chunks_batch(self, doc_id, chunks, **kwargs):
        self.batches.append((doc_id, chunks, kwargs))
        return {"error": "stale version"} if self.mode == "rejected" else {"ids": [101]}

    async def kb_result(self, doc_id, status, chunk_count=0, fail_reason=None, **kwargs):
        self.results.append((doc_id, status, chunk_count, fail_reason, kwargs))


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["success", "degraded", "empty", "rejected"])
async def test_ingest_keeps_task_version_on_chunks_and_all_result_paths(monkeypatch, mode):
    backend = RecordingBackend(mode)
    store = type("Store", (), {
        "existing_ids": AsyncMock(return_value=set()),
        "insert": AsyncMock(),
        "delete_by_doc": AsyncMock(),
    })()
    embeddings = type("Embeddings", (), {"aembed_documents": AsyncMock(return_value=[[0.1, 0.2]])})()
    if mode == "degraded":
        embeddings.aembed_documents.side_effect = RuntimeError("embedding offline")
    monkeypatch.setattr(ingest, "backend_client", backend)
    monkeypatch.setattr(ingest, "get_vectorstore", lambda: store)
    monkeypatch.setattr(ingest, "get_embeddings", lambda: embeddings)

    await ingest.run_ingest(IngestTask(doc_id=7, doc_type="POLICY", doc_version=4,
                                       file_url="/internal/files/7", file_format="TXT"))

    if mode != "empty":
        assert backend.batches[0][2] == {"doc_version": 4}
    assert len(backend.results) == 1
    doc_id, status, count, reason, kwargs = backend.results[0]
    assert doc_id == 7
    assert kwargs["doc_version"] == 4
    if mode in {"empty", "rejected"}:
        assert status == "FAILED"
        assert count == 0
        assert reason
        store.insert.assert_not_awaited()
    else:
        assert status == "ACTIVE"
        assert count == 1
        assert kwargs["vector_count"] == (0 if mode == "degraded" else 1)
        if mode == "success":
            assert store.insert.await_args.args[0][0]["doc_version"] == 4
