"""Deterministic validation for citations in knowledge-base answers."""
import re
from dataclasses import dataclass
from typing import Mapping


_CITATION_RE = re.compile(r"\[(S[1-9][0-9]*)\]")
_EVIDENCE_INSUFFICIENT = "当前知识库证据不足，暂时无法可靠回答该问题。"
_RETRIEVAL_UNAVAILABLE = "知识库暂时不可用，请稍后再试。"


@dataclass(frozen=True, slots=True)
class CitationValidation:
    content: str
    citations: tuple[dict, ...]
    valid: bool
    reason: str


def validate_citations(
    content: str,
    *,
    allowed: Mapping[str, Mapping],
    answerable: bool,
    rag_reason: str | None = None,
) -> CitationValidation:
    """Validate source IDs and expose only approved public citation metadata."""
    if not answerable:
        unavailable = rag_reason == "retrieval_unavailable"
        return CitationValidation(
            content=_RETRIEVAL_UNAVAILABLE if unavailable else _EVIDENCE_INSUFFICIENT,
            citations=(),
            valid=False,
            reason="retrieval_unavailable" if unavailable else (rag_reason or "unanswerable"),
        )

    referenced = list(dict.fromkeys(_CITATION_RE.findall(content)))
    if not referenced:
        return CitationValidation(_EVIDENCE_INSUFFICIENT, (), False, "missing_citation")
    if any(source_id not in allowed for source_id in referenced):
        return CitationValidation(_EVIDENCE_INSUFFICIENT, (), False, "unknown_citation")

    citations = tuple(
        {key: allowed[source_id][key] for key in ("id", "chunk_id", "title")}
        for source_id in referenced
    )
    return CitationValidation(content, citations, True, "valid")
