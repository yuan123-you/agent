"""Pure retrieval, fusion, answerability, and citation-context primitives."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from html import escape
import math
import re
import unicodedata
from collections.abc import Iterable, Sequence

from app.config import settings


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
                merged[chunk_id] = replace(candidate, matched_by=set(candidate.matched_by))
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