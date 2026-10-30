"""Deterministic validation for citations in knowledge-base answers."""
import re
from dataclasses import dataclass
from typing import Mapping


_SOURCE_MARKER_RE = re.compile(r"\[(S[0-9]+)\]")
_CANONICAL_SOURCE_RE = re.compile(r"S[1-9][0-9]*")
_EVIDENCE_INSUFFICIENT = "暂时没有找到足够依据，无法确认这项规则。您可以补充商品名称或具体情况，我再帮您核实。"
_RETRIEVAL_UNAVAILABLE = "暂时无法查询相关规则，请稍后再试。"
_ANSWER_FAILURES = {
    "generation_timeout": "答复整理超时了，请稍后重试。",
    "generation_failed": "暂时没能生成可靠的答复，请稍后重试。",
    "generation_invalid": "暂时没能整理出可靠的答复，请补充您关心的具体问题，或稍后重试。",
}


def is_document_dump(content: str, sources: Mapping[str, str]) -> bool:
    """Reject full documents/long verbatim passages, not short factual quotations."""
    def normalize(text: str) -> str:
        return re.sub(r"[\s#>*_`]+", "", _SOURCE_MARKER_RE.sub("", text))
    body = normalize(content)
    for source in sources.values():
        original = normalize(source)
        has_heading = bool(re.search(r"(?m)^\s*#{1,6}\s+", source))
        if len(original) >= (40 if has_heading else 180) and original in body:
            return True
        if any(original[start:start + 180] in body for start in range(0, len(original) - 179, 90)):
            return True
    return False


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
    sources: Mapping[str, str] | None = None,
) -> CitationValidation:
    """Validate source IDs and expose only approved public citation metadata."""
    if rag_reason in _ANSWER_FAILURES:
        return CitationValidation(_ANSWER_FAILURES[rag_reason], (), False, rag_reason)
    if not answerable:
        unavailable = rag_reason == "retrieval_unavailable"
        return CitationValidation(
            content=_RETRIEVAL_UNAVAILABLE if unavailable else _EVIDENCE_INSUFFICIENT,
            citations=(),
            valid=False,
            reason="retrieval_unavailable" if unavailable else (rag_reason or "unanswerable"),
        )

    referenced = list(dict.fromkeys(_SOURCE_MARKER_RE.findall(content)))
    if not referenced:
        return CitationValidation(_EVIDENCE_INSUFFICIENT, (), False, "missing_citation")
    if any(
        _CANONICAL_SOURCE_RE.fullmatch(source_id) is None or source_id not in allowed
        for source_id in referenced
    ):
        return CitationValidation(_EVIDENCE_INSUFFICIENT, (), False, "unknown_citation")

    if sources and is_document_dump(content, sources):
        return CitationValidation(_ANSWER_FAILURES["generation_invalid"], (), False, "generation_invalid")

    citations = tuple(
        {key: allowed[source_id][key] for key in ("id", "chunk_id", "title")}
        for source_id in referenced
    )
    return CitationValidation(content, citations, True, "valid")
