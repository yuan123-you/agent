"""Pure retrieval, fusion, answerability, and citation-context primitives."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
from functools import lru_cache
from html import escape
import logging
import math
import re
import unicodedata
from collections.abc import Awaitable, Callable, Iterable, Sequence
from typing import TYPE_CHECKING, Any

from app.config import settings
from app.observability.telemetry import span_ctx

if TYPE_CHECKING:
    from app.rag.reranker import Reranker

logger = logging.getLogger("ai-service.retrieval")


@dataclass(slots=True)
class RetrievalCandidate:
    chunk_id: int
    doc_id: int
    product_id: int | None
    doc_type: str
    content: str
    source: str
    vector_score: float | None = None
    bm25_score: float | None = None
    rrf_score: float = 0.0
    rerank_score: float | None = None
    evidence_score: float = 0.0
    matched_by: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if isinstance(self.chunk_id, bool) or not isinstance(self.chunk_id, int) or self.chunk_id <= 0:
            raise ValueError("chunk_id must be a positive integer")


@dataclass(frozen=True, slots=True)
class Citation:
    id: str
    chunk_id: int
    title: str


@dataclass(frozen=True, slots=True)
class AnswerabilityDecision:
    answerable: bool
    reason: str
    top1: float | None
    margin: float | None


@dataclass(frozen=True, slots=True)
class SourceContext:
    context: str
    citations: tuple[Citation, ...]


def normalize_query(query: str) -> str:
    """Normalize presentation noise without changing the query's meaning."""
    normalized = unicodedata.normalize("NFKC", query)
    normalized = "".join(char for char in normalized if not (unicodedata.category(char).startswith("C") and not char.isspace()))
    normalized = "".join(
        char.lower() if "LATIN" in unicodedata.name(char, "") else char
        for char in normalized
    )
    return re.sub(r"\s+", " ", normalized).strip()


def _safe_source_title(title: str) -> str:
    return "知识库资料" if re.fullmatch(r"\s*知识库文档#\d+\s*", title) else title


def filter_metadata(
    candidates: Iterable[RetrievalCandidate], doc_type: str | None, product_id: int | None
) -> list[RetrievalCandidate]:
    """Keep matching document metadata in the supplied ranking order."""
    return [
        candidate
        for candidate in candidates
        if (not doc_type or doc_type == "ALL" or candidate.doc_type == doc_type)
        and (product_id is None or candidate.product_id in (product_id, -1, None))
    ]


def reciprocal_rank_fusion(
    ranked_legs: Iterable[tuple[str, Sequence[RetrievalCandidate]]], *, limit: int, rrf_k: int
) -> list[RetrievalCandidate]:
    """Fuse ranked legs exclusively by their validated chunk identifiers."""
    merged: dict[int, RetrievalCandidate] = {}
    best_ranks: dict[int, int] = {}

    for leg_name, candidates in ranked_legs:
        for rank, candidate in enumerate(candidates, start=1):
            chunk_id = candidate.chunk_id
            if not isinstance(chunk_id, int) or isinstance(chunk_id, bool) or chunk_id <= 0:
                continue
            if chunk_id not in merged:
                merged[chunk_id] = replace(candidate, rrf_score=0.0, matched_by=set(candidate.matched_by))
                best_ranks[chunk_id] = rank
            else:
                combined = merged[chunk_id]
                if candidate.vector_score is not None:
                    combined.vector_score = candidate.vector_score
                if candidate.bm25_score is not None:
                    combined.bm25_score = candidate.bm25_score
                if candidate.rerank_score is not None:
                    combined.rerank_score = candidate.rerank_score
                best_ranks[chunk_id] = min(best_ranks[chunk_id], rank)

            current = merged[chunk_id]
            current.rrf_score += 1 / (rrf_k + rank)
            current.matched_by.add(leg_name)

    return sorted(
        merged.values(),
        key=lambda candidate: (-candidate.rrf_score, best_ranks[candidate.chunk_id], candidate.chunk_id),
    )[:limit]


def _vector_evidence(raw: float) -> float:
    scaled = (raw - settings.rag_vector_score_center) / settings.rag_vector_score_scale
    if scaled >= 0:
        return 1 / (1 + math.exp(-scaled))
    exp_scaled = math.exp(scaled)
    return exp_scaled / (1 + exp_scaled)


def _bm25_evidence(raw: float) -> float:
    nonnegative = max(raw, 0)
    return nonnegative / (nonnegative + settings.rag_bm25_score_scale)


def _evidence_score(candidate: RetrievalCandidate) -> float:
    if candidate.rerank_score is not None:
        return candidate.rerank_score
    scores: list[float] = []
    if candidate.vector_score is not None:
        scores.append(_vector_evidence(candidate.vector_score))
    if candidate.bm25_score is not None:
        scores.append(_bm25_evidence(candidate.bm25_score))
    return max(scores, default=0.0)


def assess_answerability(candidates: Sequence[RetrievalCandidate]) -> AnswerabilityDecision:
    """Apply the configured evidence and top-two margin policy to final candidates."""
    top_candidates = candidates[:4]
    if not top_candidates:
        return AnswerabilityDecision(False, "insufficient_evidence", None, None)

    scores = []
    for candidate in top_candidates:
        candidate.evidence_score = _evidence_score(candidate)
        scores.append(candidate.evidence_score)

    top1 = scores[0]
    margin = top1 - scores[1] if len(scores) > 1 else None
    if top1 >= settings.rag_answer_high_confidence_score:
        return AnswerabilityDecision(True, "high_confidence", top1, margin)
    if top1 >= settings.rag_answer_min_score and (margin is None or margin >= settings.rag_answer_min_margin):
        return AnswerabilityDecision(True, "score_and_margin", top1, margin)
    return AnswerabilityDecision(False, "insufficient_evidence", top1, margin)


def build_source_context(candidates: Sequence[RetrievalCandidate]) -> SourceContext:
    """Build stable, XML-escaped source blocks for up to four final candidates."""
    citations = tuple(
        Citation(id=f"S{index}", chunk_id=candidate.chunk_id, title=_safe_source_title(candidate.source))
        for index, candidate in enumerate(candidates[:4], start=1)
    )
    blocks = [
        f'<source id="{escape(citation.id, quote=True)}" '
        f'chunk_id="{escape(str(citation.chunk_id), quote=True)}" '
        f'title="{escape(citation.title, quote=True)}">\n'
        f'{escape(candidate.content, quote=True)}\n'
        f'</source>'
        for citation, candidate in zip(citations, candidates[:4], strict=True)
    ]
    return SourceContext(context="\n".join(blocks), citations=citations)

@dataclass(frozen=True, slots=True)
class RetrievalResult:
    answerable: bool
    reason: str
    hits: tuple[RetrievalCandidate, ...]
    context: str
    citations: tuple[Citation, ...]
    degraded: bool
    degraded_reasons: tuple[str, ...]


SearchAdapter = Callable[..., Awaitable[dict[str, Any]]]


def _query_summary(query: str) -> dict[str, int]:
    return {"length": len(query), "word_count": len(query.split())}


def _parse_hits(payload: object, leg_name: str) -> list[RetrievalCandidate]:
    if not isinstance(payload, dict) or not isinstance(payload.get("hits"), list):
        raise ValueError(f"{leg_name} retrieval returned an invalid payload")
    if "error" in payload:
        raise RuntimeError(f"{leg_name} retrieval unavailable")

    candidates: list[RetrievalCandidate] = []
    for raw in payload["hits"]:
        chunk_id = raw.get("chunk_id") if isinstance(raw, dict) else None
        doc_id = raw.get("doc_id") if isinstance(raw, dict) else None
        if (
            isinstance(chunk_id, bool)
            or not isinstance(chunk_id, int)
            or chunk_id <= 0
            or isinstance(doc_id, bool)
            or not isinstance(doc_id, int)
        ):
            logger.warning("discarding %s candidate with missing or invalid chunk_id/doc_id", leg_name)
            continue

        product_id = raw.get("product_id")
        if isinstance(product_id, bool) or (product_id is not None and not isinstance(product_id, int)):
            logger.warning("discarding %s candidate with invalid product_id", leg_name)
            continue
        score = raw.get("score")
        numeric_score = (
            float(score)
            if not isinstance(score, bool) and isinstance(score, (int, float)) and math.isfinite(score)
            else None
        )
        candidates.append(RetrievalCandidate(
            chunk_id=chunk_id,
            doc_id=doc_id,
            product_id=product_id,
            doc_type=str(raw.get("docType") or raw.get("doc_type") or ""),
            content=str(raw.get("content") or ""),
            source=str(raw.get("source") or ""),
            vector_score=numeric_score if leg_name == "vector" else None,
            bm25_score=numeric_score if leg_name == "bm25" else None,
        ))
    return candidates


class RetrievalPipeline:
    """Coordinate normalized, parallel hybrid retrieval through final source context."""

    def __init__(
        self,
        *,
        vector_search: SearchAdapter,
        bm25_search: SearchAdapter,
        reranker: Reranker | None,
    ) -> None:
        self._vector_search = vector_search
        self._bm25_search = bm25_search
        self._reranker = reranker

    async def search(
        self, query: str, doc_type: str = "ALL", product_id: int | None = None
    ) -> RetrievalResult:
        normalized = normalize_query(query)
        summary = _query_summary(normalized)
        with span_ctx("rag::hybrid_retrieval", input={"normalized_query": summary}) as span:
            counts = {
                "normalized_query": summary,
                "vector_count": 0,
                "bm25_count": 0,
                "vector_filtered_count": 0,
                "bm25_filtered_count": 0,
                "rrf_count": 0,
                "rerank_count": 0,
            }
            if not normalized:
                result = RetrievalResult(False, "invalid_query", (), "", (), False, ())
                span.complete({
                    **counts, "top1": None, "margin": None, "answerable": False,
                    "decision_reason": result.reason, "degradation_reasons": [],
                })
                return result

            raw_results = await asyncio.gather(
                self._vector_search(normalized, top_k=settings.rag_vector_recall_k),
                self._bm25_search(normalized, top_k=settings.rag_bm25_recall_k),
                return_exceptions=True,
            )
            reasons: list[str] = []
            legs: dict[str, list[RetrievalCandidate]] = {"vector": [], "bm25": []}
            for leg_name, raw in zip(("vector", "bm25"), raw_results, strict=True):
                if isinstance(raw, BaseException):
                    reasons.append(f"{leg_name}_unavailable")
                    continue
                try:
                    legs[leg_name] = _parse_hits(raw, leg_name)
                except (TypeError, ValueError, RuntimeError):
                    reasons.append(f"{leg_name}_unavailable")

            counts["vector_count"] = len(legs["vector"])
            counts["bm25_count"] = len(legs["bm25"])
            if len(reasons) == 2:
                result = RetrievalResult(
                    False, "retrieval_unavailable", (), "", (), True, tuple(reasons)
                )
                span.complete({
                    **counts, "top1": None, "margin": None, "answerable": False,
                    "decision_reason": result.reason, "degradation_reasons": reasons,
                })
                return result

            filtered = {
                name: filter_metadata(candidates, doc_type, product_id)
                for name, candidates in legs.items()
            }
            counts["vector_filtered_count"] = len(filtered["vector"])
            counts["bm25_filtered_count"] = len(filtered["bm25"])
            fused = reciprocal_rank_fusion(
                [("vector", filtered["vector"]), ("bm25", filtered["bm25"])],
                limit=settings.rag_rrf_top_k,
                rrf_k=settings.rag_rrf_k,
            )
            counts["rrf_count"] = len(fused)

            ranked = fused
            if self._reranker is not None and fused:
                try:
                    ranked = await self._reranker.rerank(normalized, fused)
                    counts["rerank_count"] = min(len(ranked), settings.rag_final_top_k)
                except Exception:
                    logger.warning("retrieval reranker unavailable; preserving RRF order")
                    reasons.append("reranker_unavailable")
                    ranked = fused

            final = tuple(ranked[:settings.rag_final_top_k])
            decision = assess_answerability(final)
            source_context = build_source_context(final) if decision.answerable else SourceContext("", ())
            result = RetrievalResult(
                decision.answerable,
                decision.reason,
                final,
                source_context.context,
                source_context.citations,
                bool(reasons),
                tuple(reasons),
            )
            span.complete({
                **counts,
                "top1": decision.top1,
                "margin": decision.margin,
                "answerable": decision.answerable,
                "decision_reason": decision.reason,
                "degradation_reasons": reasons,
            })
            return result


@lru_cache
def get_retrieval_pipeline() -> RetrievalPipeline:
    """Build the process-wide retrieval pipeline from lazy adapters and typed T10 reranker."""
    from app.clients.backend_client import backend_client
    from app.rag.reranker import get_reranker
    from app.rag.vectorstore import get_vectorstore

    return RetrievalPipeline(
        vector_search=get_vectorstore().search,
        bm25_search=backend_client.kb_keyword_search,
        reranker=get_reranker() if settings.rag_reranker_enabled else None,
    )
