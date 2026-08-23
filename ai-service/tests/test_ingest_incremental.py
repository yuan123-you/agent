from unittest.mock import AsyncMock

import pytest
from langchain_core.embeddings import Embeddings

from app.rag import ingest
from app.rag.ingest import IngestTask


class RecordingEmbeddings(Embeddings):
    def __init__(self):
        self.texts = []

    async def aembed_documents(self, texts):
        self.texts.extend(texts)
        return [[0.1, 0.2] for _ in texts]

    def embed_documents(self, texts):
        raise NotImplementedError

    def embed_query(self, text):
        raise NotImplementedError


class ExistingAwareStore:
    def __init__(self):
        self.rows = []

    async def existing_ids(self, ids):
        return {ids[0]}

    async def insert(self, rows):
        self.rows.extend(rows)

    async def delete_by_doc(self, doc_id, exclude_version=None):
        return {"deleteCount": 0}


@pytest.mark.asyncio
async def test_ingest_does_not_reembed_chunk_ids_present_in_current_collection(monkeypatch):
    embeddings = RecordingEmbeddings()
    store = ExistingAwareStore()
    monkeypatch.setattr(ingest, "get_embeddings", lambda: embeddings)
    monkeypatch.setattr(ingest, "get_vectorstore", lambda: store)
    monkeypatch.setattr(ingest, "split_text", lambda text: ["already embedded", "new chunk"])
    monkeypatch.setattr(ingest.backend_client, "download_file", AsyncMock(return_value=b"document"))
    monkeypatch.setattr(
        ingest.backend_client,
        "kb_chunks_batch",
        AsyncMock(return_value={"ids": [101, 102]}),
    )
    result = AsyncMock()
    monkeypatch.setattr(ingest.backend_client, "kb_result", result)

    await ingest.run_ingest(IngestTask(
        doc_id=7,
        doc_type="FAQ",
        doc_version=1,
        file_url="http://backend/file",
        file_format="TXT",
    ))

    assert embeddings.texts == ["new chunk"]
    assert [row["id"] for row in store.rows] == [102]
    result.assert_awaited_once_with(7, "ACTIVE", 2)
