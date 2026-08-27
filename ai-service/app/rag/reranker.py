"""Optional local and Qwen-compatible HTTP rerankers."""
from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from functools import lru_cache
from typing import Protocol

import httpx

from app.config import settings
from app.rag.retrieval import RetrievalCandidate

logger = logging.getLogger("ai-service.reranker")

_SCORE_SCHEMA = {
    "type": "object",
    "properties": {"score": {"type": "number", "minimum": 0, "maximum": 1}},
    "required": ["score"],
}


class Reranker(Protocol):
    """Rerank retrieval candidates without changing their identity."""

    async def rerank(
        self, query: str, candidates: list[RetrievalCandidate]
    ) -> list[RetrievalCandidate]: ...


class QwenHttpReranker:
    """Qwen3-compatible HTTP reranker boundary for retrieval candidates."""

    def __init__(self, reranker_settings=settings):
        self._base_url = reranker_settings.rag_reranker_base_url.rstrip("/")
        self._endpoint = reranker_settings.rag_reranker_endpoint
        self._model = reranker_settings.rag_reranker_model
        self._api_key = reranker_settings.rag_reranker_api_key
        self._timeout = reranker_settings.rag_reranker_timeout_s
        self._batch_size = reranker_settings.rag_reranker_batch_size

    @property
    def _url(self) -> str:
        return f"{self._base_url}/{self._endpoint.lstrip('/')}"

    async def rerank(
        self, query: str, candidates: list[RetrievalCandidate]
    ) -> list[RetrievalCandidate]:
        if not candidates:
            return []

        request_options = {"headers": {"Authorization": f"Bearer {self._api_key}"}} if self._api_key else {}
        scored: list[tuple[RetrievalCandidate, float]] = []
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for start in range(0, len(candidates), self._batch_size):
                batch = candidates[start : start + self._batch_size]
                response = await client.post(
                    self._url,
                    json={
                        "model": self._model,
                        "query": query,
                        "documents": [candidate.content for candidate in batch],
                        "top_n": len(batch),
                    },
                    timeout=self._timeout,
                    **request_options,
                )
                response.raise_for_status()
                scores = self._validated_scores(response.json(), len(batch))
                scored.extend(zip(batch, scores, strict=True))

        for candidate, score in scored:
            candidate.rerank_score = score
            candidate.evidence_score = score
        return [candidate for candidate, _ in sorted(scored, key=lambda item: item[1], reverse=True)]

    @staticmethod
    def _validated_scores(payload: object, expected_count: int) -> list[float]:
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise ValueError("reranker response must contain a results list")
        results = payload["results"]
        if len(results) != expected_count:
            raise ValueError("reranker response result count does not match input")

        scores: list[float | None] = [None] * expected_count
        for result in results:
            if not isinstance(result, dict):
                raise ValueError("reranker response result must be an object")
            index = result.get("index")
            score = result.get("relevance_score")
            if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < expected_count:
                raise ValueError("reranker response contains an invalid index")
            if scores[index] is not None:
                raise ValueError("reranker response contains a duplicate index")
            if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
                raise ValueError("reranker response contains an invalid relevance score")
            if not 0 <= score <= 1:
                raise ValueError("reranker response relevance score is outside [0, 1]")
            scores[index] = float(score)

        if any(score is None for score in scores):
            raise ValueError("reranker response is missing an input index")
        return [score for score in scores if score is not None]


class OllamaReranker:
    """Score query/document pairs through an Ollama-hosted Qwen3 reranker."""

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        timeout: float = 120.0,
        keep_alive: str = "10m",
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._url = base_url.rstrip("/") + "/api/generate" if base_url else ""
        self._model = model
        self._timeout = timeout
        self._keep_alive = keep_alive
        self._transport = transport

    @property
    def enabled(self) -> bool:
        return bool(self._url and self._model)

    @staticmethod
    def _prompt(query: str, document: str) -> str:
        return (
            "Judge whether the document is relevant to the query. "
            "Return only JSON with a relevance score from 0 to 1.\n"
            f"Query: {query}\nDocument: {document}"
        )

    async def _score(self, client: httpx.AsyncClient, query: str, document: str) -> float:
        payload = {
            "model": self._model,
            "prompt": self._prompt(query, document),
            "stream": False,
            "format": _SCORE_SCHEMA,
            "keep_alive": self._keep_alive,
            "options": {
                "temperature": 0, "num_predict": 32,
                "num_ctx": settings.ollama_num_ctx, "num_gpu": settings.ollama_num_gpu,
            },
        }
        for attempt in range(2):
            response = await client.post(self._url, json=payload)
            if attempt == 0 and (response.status_code == 429 or response.status_code >= 500):
                await asyncio.sleep(1)
                continue
            response.raise_for_status()
            break
        raw = response.json().get("response", "")
        try:
            value = float(json.loads(raw)["score"])
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            match = re.search(r"(?:score\D*)?(0(?:\.\d+)?|1(?:\.0+)?)", raw)
            if not match:
                raise ValueError(f"reranker returned no score: {raw[:120]}")
            value = float(match.group(1))
        return max(0.0, min(1.0, value))

    async def rerank(self, query: str, hits: list[dict], top_n: int) -> list[dict]:
        if not hits or top_n <= 0:
            return []
        if not self.enabled:
            return hits[:top_n]
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                scores = [await self._score(client, query, hit.get("content", "")) for hit in hits]
        except Exception as exc:
            logger.warning("reranker unavailable; preserving fused order: %s", exc)
            return hits[:top_n]
        ranked = []
        for hit, score in zip(hits, scores):
            ranked.append({**hit, "rerank_score": round(score, 6)})
        return sorted(ranked, key=lambda item: item["rerank_score"], reverse=True)[:top_n]


@lru_cache
def get_reranker() -> QwenHttpReranker | OllamaReranker | None:
    """Return the configured reranker, or ``None`` when both are disabled."""
    if settings.rag_reranker_enabled:
        return QwenHttpReranker()
    if settings.reranker_enabled:
        return OllamaReranker(
            base_url=settings.reranker_base_url,
            model=settings.reranker_model,
            timeout=settings.reranker_timeout_s,
            keep_alive=settings.ollama_keep_alive,
        )
    return None
