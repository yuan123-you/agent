"""Optional Ollama-backed second-stage reranking."""
from __future__ import annotations

import asyncio
import json
import logging
import re

import httpx

logger = logging.getLogger("ai-service.reranker")

_SCORE_SCHEMA = {
    "type": "object",
    "properties": {"score": {"type": "number", "minimum": 0, "maximum": 1}},
    "required": ["score"],
}


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
        response = await client.post(
            self._url,
            json={
                "model": self._model,
                "prompt": self._prompt(query, document),
                "stream": False,
                "format": _SCORE_SCHEMA,
                "keep_alive": self._keep_alive,
                "options": {
                    "temperature": 0, "num_predict": 32,
                    "num_ctx": settings.ollama_num_ctx, "num_gpu": settings.ollama_num_gpu,
                },
            },
        )
        response.raise_for_status()
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
                # Sequential calls avoid loading two 4B models concurrently on a 4 GB GPU.
                scores = [await self._score(client, query, hit.get("content", "")) for hit in hits]
        except Exception as exc:
            logger.warning("reranker unavailable; preserving fused order: %s", exc)
            return hits[:top_n]
        ranked = []
        for hit, score in zip(hits, scores):
            ranked.append({**hit, "rerank_score": round(score, 6)})
        return sorted(ranked, key=lambda item: item["rerank_score"], reverse=True)[:top_n]

from functools import lru_cache

from app.config import settings


@lru_cache
def get_reranker() -> OllamaReranker:
    """Return the optional process-wide reranker client."""
    if not settings.reranker_enabled:
        return OllamaReranker(base_url="", model="")
    return OllamaReranker(
        base_url=settings.reranker_base_url,
        model=settings.reranker_model,
        timeout=settings.reranker_timeout_s,
        keep_alive=settings.ollama_keep_alive,
    )

