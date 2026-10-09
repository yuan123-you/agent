"""LLM and embedding factories backed entirely by environment configuration."""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Awaitable, Callable, TypeVar

import httpx
from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.config import settings
from app.clients.ollama import OllamaEmbeddings

logger = logging.getLogger(__name__)
T = TypeVar("T")


def get_chat_llm(streaming: bool = True) -> ChatOpenAI:
    """对话模型（导购生成用，支持流式）"""
    return ChatOpenAI(
        base_url=settings.llm_api_base,
        api_key=settings.llm_api_key,
        model=settings.llm_chat_model,
        temperature=settings.temperature,
        streaming=streaming,
        timeout=settings.llm_chat_timeout_s,
        reasoning_effort=settings.llm_reasoning_effort,
        max_retries=1,
    )


def get_intent_llm() -> ChatOpenAI:
    """意图识别模型（低延迟、温度 0）"""
    return ChatOpenAI(
        base_url=settings.llm_api_base,
        api_key=settings.llm_api_key,
        model=settings.llm_intent_model,
        temperature=0,
        streaming=False,
        timeout=settings.llm_intent_timeout_s,
        reasoning_effort=settings.llm_reasoning_effort,
        max_retries=1,
    )


class MaaSEmbeddings(Embeddings):
    """阿里云百炼 MaaS 端点适配器，兼容 OpenAI 与阿里原生响应格式。"""

    def __init__(self, base_url: str, api_key: str, model: str):
        self._url = base_url.rstrip("/") + "/embeddings"
        self._headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self._model = model

    async def _acall(self, texts: list[str]) -> list[list[float]]:
        payload = {"model": self._model, "input": texts}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(self._url, headers=self._headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        items = data.get("data") or data.get("output", {}).get("embeddings", [])
        items.sort(key=lambda e: e.get("index", 0))
        return [e["embedding"] for e in items]

    async def aembed_query(self, text: str) -> list[float]:
        return (await self._acall([text]))[0]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for i in range(0, len(texts), 4):
            results.extend(await self._acall(texts[i:i + 4]))
        return results

    def embed_query(self, text: str) -> list[float]:
        import asyncio
        return asyncio.run(self.aembed_query(text))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        import asyncio
        return asyncio.run(self.aembed_documents(texts))


class EmbeddingFallbackError(RuntimeError):
    """Raised after every configured embedding model has failed."""


class FallbackEmbeddings(Embeddings):
    """Try embedding models in order and remain on the first successful model."""

    def __init__(self, candidates: list[tuple[str, Embeddings]], expected_dim: int):
        if not candidates:
            raise ValueError("at least one embedding model is required")
        self._candidates = candidates
        self._expected_dim = expected_dim
        self._active_index = 0

    @property
    def active_model(self) -> str:
        return self._candidates[self._active_index][0]

    def _validate_query(self, vector: list[float]) -> list[float]:
        if len(vector) != self._expected_dim:
            raise ValueError(f"expected dimension {self._expected_dim}, got {len(vector)}")
        return vector

    def _validate_documents(self, vectors: list[list[float]], expected_count: int) -> list[list[float]]:
        if len(vectors) != expected_count:
            raise ValueError(f"expected {expected_count} vectors, got {len(vectors)}")
        for vector in vectors:
            self._validate_query(vector)
        return vectors

    async def _run_async(self, operation: str, call: Callable[[Embeddings], Awaitable[T]]) -> T:
        errors: list[str] = []
        for index in range(self._active_index, len(self._candidates)):
            model, client = self._candidates[index]
            try:
                result = await call(client)
                self._active_index = index
                if index:
                    logger.warning("embedding model degraded to %s during %s; rebuild vector indexes after model changes", model, operation)
                return result
            except Exception as exc:
                errors.append(f"{model}: {type(exc).__name__}: {exc}")
                logger.warning("embedding model %s failed during %s: %s", model, operation, exc)
        raise EmbeddingFallbackError("all embedding models failed (" + "; ".join(errors) + ")")

    def _run_sync(self, operation: str, call: Callable[[Embeddings], T]) -> T:
        errors: list[str] = []
        for index in range(self._active_index, len(self._candidates)):
            model, client = self._candidates[index]
            try:
                result = call(client)
                self._active_index = index
                if index:
                    logger.warning("embedding model degraded to %s during %s; rebuild vector indexes after model changes", model, operation)
                return result
            except Exception as exc:
                errors.append(f"{model}: {type(exc).__name__}: {exc}")
                logger.warning("embedding model %s failed during %s: %s", model, operation, exc)
        raise EmbeddingFallbackError("all embedding models failed (" + "; ".join(errors) + ")")

    async def aembed_query(self, text: str) -> list[float]:
        return await self._run_async("query", lambda client: self._validated_async_query(client, text))

    async def _validated_async_query(self, client: Embeddings, text: str) -> list[float]:
        return self._validate_query(await client.aembed_query(text))

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return await self._run_async("documents", lambda client: self._validated_async_documents(client, texts))

    async def _validated_async_documents(self, client: Embeddings, texts: list[str]) -> list[list[float]]:
        return self._validate_documents(await client.aembed_documents(texts), len(texts))

    def embed_query(self, text: str) -> list[float]:
        return self._run_sync("query", lambda client: self._validate_query(client.embed_query(text)))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._run_sync(
            "documents",
            lambda client: self._validate_documents(client.embed_documents(texts), len(texts)),
        )


def _make_embeddings(
    base: str,
    key: str,
    model: str,
    *,
    provider: str = "openai",
    dimensions: int = 0,
) -> Embeddings:
    if provider.lower() == "ollama":
        return OllamaEmbeddings(
            base_url=base,
            model=model,
            dimensions=dimensions,
            keep_alive=settings.ollama_keep_alive,
            num_ctx=settings.ollama_num_ctx,
            num_gpu=settings.ollama_num_gpu,
        )
    if provider.lower() == "maas" or "maas.aliyuncs.com" in base:
        return MaaSEmbeddings(base, key, model)
    return OpenAIEmbeddings(base_url=base, api_key=key, model=model)


@lru_cache
def get_embeddings() -> Embeddings:
    """Return an ordered, dimension-validating embedding fallback chain."""
    if settings.embedding_provider.lower() == "ollama":
        base = settings.ollama_base_url
        candidates = [(settings.embedding_model, _make_embeddings(
            base,
            "",
            settings.embedding_model,
            provider="ollama",
            dimensions=settings.embedding_dim,
        ))]
    else:
        base = settings.embedding_api_base or settings.llm_api_base
        key = settings.embedding_api_key or settings.llm_api_key
        candidates = [(model, _make_embeddings(
            base,
            key,
            model,
            provider=settings.embedding_provider,
            dimensions=settings.embedding_dim,
        )) for model in settings.embedding_model_order]
    return FallbackEmbeddings(candidates, expected_dim=settings.embedding_dim)
