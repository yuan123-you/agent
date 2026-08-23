"""Small Ollama HTTP clients used by the local RAG pipeline."""
from __future__ import annotations

import httpx
from langchain_core.embeddings import Embeddings


class OllamaEmbeddings(Embeddings):
    """LangChain embedding adapter for Ollama's native ``/api/embed`` API."""

    def __init__(
        self,
        base_url: str,
        model: str,
        dimensions: int,
        *,
        timeout: float = 120.0,
        keep_alive: str = "10m",
        max_batch_size: int = 16,
        num_ctx: int = 2048,
        num_gpu: int = 10,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._url = base_url.rstrip("/") + "/api/embed"
        self._model = model
        self._dimensions = dimensions
        self._timeout = timeout
        self._keep_alive = keep_alive
        self._max_batch_size = max_batch_size
        self._num_ctx = num_ctx
        self._num_gpu = num_gpu
        self._transport = transport

    def _payload(self, texts: list[str]) -> dict:
        payload = {
            "model": self._model,
            "input": texts,
            "truncate": True,
            "keep_alive": self._keep_alive,
        "options": {"num_ctx": self._num_ctx, "num_gpu": self._num_gpu},
        }
        if self._dimensions > 0:
            payload["dimensions"] = self._dimensions
        return payload

    def _validate(self, vectors: list[list[float]], count: int) -> list[list[float]]:
        if len(vectors) != count:
            raise ValueError(f"expected {count} vectors, got {len(vectors)}")
        if self._dimensions > 0:
            for vector in vectors:
                if len(vector) != self._dimensions:
                    raise ValueError(
                        f"expected dimension {self._dimensions}, got {len(vector)}"
                    )
        return vectors

    async def _acall(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.post(self._url, json=self._payload(texts))
            response.raise_for_status()
            return self._validate(response.json().get("embeddings") or [], len(texts))

    def _call(self, texts: list[str]) -> list[list[float]]:
        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(self._url, json=self._payload(texts))
            response.raise_for_status()
            return self._validate(response.json().get("embeddings") or [], len(texts))

    async def aembed_query(self, text: str) -> list[float]:
        return (await self._acall([text]))[0]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._max_batch_size):
            vectors.extend(await self._acall(texts[start:start + self._max_batch_size]))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._call([text])[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._max_batch_size):
            vectors.extend(self._call(texts[start:start + self._max_batch_size]))
        return vectors




