import pytest
from langchain_core.embeddings import Embeddings

from app.clients.llm import EmbeddingFallbackError, FallbackEmbeddings
from app.config import Settings


class StubEmbeddings(Embeddings):
    def __init__(self, *, vector=None, error=None):
        self.vector = vector or [0.1, 0.2, 0.3]
        self.error = error
        self.query_calls = 0
        self.document_calls = 0

    def _raise_if_needed(self):
        if self.error:
            raise self.error

    def embed_query(self, text: str) -> list[float]:
        self.query_calls += 1
        self._raise_if_needed()
        return self.vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls += 1
        self._raise_if_needed()
        return [self.vector for _ in texts]

    async def aembed_query(self, text: str) -> list[float]:
        return self.embed_query(text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_documents(texts)


def test_settings_build_primary_then_ordered_unique_fallback_models():
    value = Settings(
        _env_file=None,
        embedding_model="primary-model",
        embedding_fallback_models="text-embedding-v1,text-embedding-v3,text-embedding-v2,primary-model",
    )
    assert value.embedding_model_order == (
        "primary-model",
        "text-embedding-v1",
        "text-embedding-v3",
        "text-embedding-v2",
    )


@pytest.mark.asyncio
async def test_primary_success_does_not_call_fallback():
    primary = StubEmbeddings()
    fallback = StubEmbeddings()
    embeddings = FallbackEmbeddings([("primary", primary), ("fallback", fallback)], expected_dim=3)

    assert await embeddings.aembed_query("query") == [0.1, 0.2, 0.3]
    assert primary.query_calls == 1
    assert fallback.query_calls == 0
    assert embeddings.active_model == "primary"


@pytest.mark.asyncio
async def test_models_degrade_in_order_and_stick_to_first_success():
    primary = StubEmbeddings(error=RuntimeError("primary unavailable"))
    v1 = StubEmbeddings(error=RuntimeError("v1 unavailable"))
    v3 = StubEmbeddings()
    v2 = StubEmbeddings()
    embeddings = FallbackEmbeddings(
        [("primary", primary), ("text-embedding-v1", v1), ("text-embedding-v3", v3), ("text-embedding-v2", v2)],
        expected_dim=3,
    )

    result = await embeddings.aembed_documents(["a", "b"])
    assert result == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]
    assert [primary.document_calls, v1.document_calls, v3.document_calls, v2.document_calls] == [1, 1, 1, 0]
    assert embeddings.active_model == "text-embedding-v3"

    await embeddings.aembed_query("next")
    assert primary.query_calls == 0
    assert v1.query_calls == 0
    assert v3.query_calls == 1
    assert v2.query_calls == 0


@pytest.mark.asyncio
async def test_wrong_dimension_degrades_to_next_model():
    wrong = StubEmbeddings(vector=[0.1, 0.2])
    valid = StubEmbeddings()
    embeddings = FallbackEmbeddings([("wrong", wrong), ("valid", valid)], expected_dim=3)

    assert await embeddings.aembed_query("query") == [0.1, 0.2, 0.3]
    assert embeddings.active_model == "valid"


@pytest.mark.asyncio
async def test_all_failures_report_every_attempted_model():
    embeddings = FallbackEmbeddings(
        [
            ("primary", StubEmbeddings(error=RuntimeError("down"))),
            ("text-embedding-v1", StubEmbeddings(vector=[0.1])),
        ],
        expected_dim=3,
    )

    with pytest.raises(EmbeddingFallbackError) as exc_info:
        await embeddings.aembed_query("query")

    message = str(exc_info.value)
    assert "primary" in message
    assert "text-embedding-v1" in message
