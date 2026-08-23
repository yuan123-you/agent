import json

import httpx
import pytest

from app.clients.ollama import OllamaEmbeddings


@pytest.mark.asyncio
async def test_ollama_embeddings_requests_quantized_model_with_dimensions():
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2], [0.3, 0.4]]})

    embeddings = OllamaEmbeddings(
        base_url="http://ollama:11434",
        model="qwen3-embedding:4b",
        dimensions=2,
        transport=httpx.MockTransport(handler),
    )

    assert await embeddings.aembed_documents(["退款政策", "物流时效"]) == [[0.1, 0.2], [0.3, 0.4]]
    assert requests[0].url.path == "/api/embed"
    assert json.loads(requests[0].content) == {
        "model": "qwen3-embedding:4b",
        "input": ["退款政策", "物流时效"],
        "dimensions": 2,
        "truncate": True,
        "keep_alive": "10m",
        "options": {"num_ctx": 2048, "num_gpu": 10},
    }


@pytest.mark.asyncio
async def test_ollama_embeddings_rejects_unexpected_dimension():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3]]})

    embeddings = OllamaEmbeddings(
        base_url="http://ollama:11434",
        model="qwen3-embedding:4b",
        dimensions=2,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ValueError, match="expected dimension 2"):
        await embeddings.aembed_query("退款")

def test_embedding_factory_builds_native_ollama_client():
    from app.clients.llm import get_embeddings

    get_embeddings.cache_clear()
    assert isinstance(get_embeddings(), OllamaEmbeddings)

@pytest.mark.asyncio
async def test_ollama_embeddings_batches_large_ingest_requests():
    batch_sizes = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        batch_sizes.append(len(payload["input"]))
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2] for _ in payload["input"]]})

    embeddings = OllamaEmbeddings(
        base_url="http://ollama:11434",
        model="qwen3-embedding:4b",
        dimensions=2,
        max_batch_size=2,
        transport=httpx.MockTransport(handler),
    )
    assert len(await embeddings.aembed_documents(["a", "b", "c"])) == 3
    assert batch_sizes == [2, 1]



def test_settings_has_no_cloud_embedding_or_legacy_collection_configuration():
    from app.config import Settings

    removed = {
        "embedding_api_base",
        "embedding_api_key",
        "embedding_fallback_models",
        "embedding_provider",
        "milvus_legacy_collections",
    }
    assert removed.isdisjoint(Settings.model_fields)
