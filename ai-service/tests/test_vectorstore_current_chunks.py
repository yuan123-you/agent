from unittest.mock import AsyncMock

import pytest

from app.rag import vectorstore


class FakeMilvus:
    def search(self, **kwargs):
        return [[
            {"id": 11, "distance": 0.91, "entity": {"content": "现行政策", "doc_id": 1, "product_id": -1, "doc_type": "POLICY"}},
            {"id": 12, "distance": 0.88, "entity": {"content": "过期政策", "doc_id": 1, "product_id": -1, "doc_type": "POLICY"}},
        ]]


@pytest.mark.asyncio
async def test_vector_search_discards_chunks_not_current_in_backend(monkeypatch):
    store = vectorstore.VectorStore.__new__(vectorstore.VectorStore)
    store.client = FakeMilvus()
    store.embeddings = AsyncMock()
    store.embeddings.aembed_query.return_value = [0.1, 0.2]
    current = AsyncMock(return_value={11: "现行政策标题"})
    monkeypatch.setattr(vectorstore.backend_client, "kb_current_chunks", current, raising=False)
    monkeypatch.setattr(vectorstore.backend_client, "kb_titles", AsyncMock(return_value={1: "不应使用"}))

    result = await store.search("退货", top_k=2)

    assert [hit["chunk_id"] for hit in result["hits"]] == [11]
    assert result["hits"][0]["source"] == "现行政策标题"
    current.assert_awaited_once_with([11, 12])
