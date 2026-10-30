"""Evidence-aware answer policy, independent of SSE and LangGraph events.

Knowledge answers are held for citation validation; safe terminal model text may
stream through the existing incremental link guard. No model calls occur here.
"""
from dataclasses import dataclass, field
import json
import re
from typing import Any, Mapping

from app.agent.link_guard import collect_known_ids, ensure_product_links, guard_links
from app.rag.citations import validate_citations
from app.request_policy import requires_kb


@dataclass(frozen=True, slots=True)
class FinalAnswer:
    content: str
    citations: tuple[dict, ...]
    citation_required: bool
    rag_used: bool


@dataclass
class OutputPolicy:
    query: str
    link_guard_enabled: bool = True
    known_ids: set[str] = field(default_factory=set, init=False)
    product_result: dict | None = field(default=None, init=False)
    product_links_needed: bool = field(default=True, init=False)
    rag_started: bool = field(default=False, init=False)
    web_used: bool = field(default=False, init=False)
    policy_required: bool = field(init=False)

    def __post_init__(self):
        self.policy_required = requires_kb(self.query)

    def tool_started(self, name: str) -> None:
        if name == "kb_search":
            self.rag_started = True

    def tool_completed(self, name: str, result: Any) -> None:
        self.tool_started(name)
        if name in {"order_create", "order_query", "order_cancel_prepare",
                    "after_sale_prepare", "escalate_to_human", "web_search"}:
            self.product_links_needed = False
        if name == "web_search":
            self.web_used = True
        if name == "product_search" and isinstance(result, dict):
            self.product_result = result
        self.known_ids.update(collect_known_ids(json.dumps(result, ensure_ascii=False, default=str)))

    def can_stream(self, node: str | None, context: Mapping) -> bool:
        return bool(
            node in {"small_talk", "finalize_without_tools", "web_answer"}
            and not self.policy_required and not self.rag_started and not context.get("rag_used")
            and (self.product_result is None or not self.product_links_needed)
        )

    def finalize(self, text: str, context: Mapping, *, web_footer: str = "") -> FinalAnswer:
        # Verified provider links are program-owned; do not treat them as model links.
        if web_footer and text.endswith(web_footer):
            text = text[:-len(web_footer)]
        rag_used = bool(context.get("rag_used") or self.rag_started or self.policy_required)
        citation_required = rag_used and (self.policy_required or not self.web_used)
        citations: tuple[dict, ...] = ()
        if context.get("policy_clarification"):
            text = context["policy_clarification"]
        elif citation_required:
            normalized = re.sub(r"[【（(](S[0-9]+)[】）)]", r"[\1]", text)
            normalized = re.sub(r"\[s([0-9]+)\]", r"[S\1]", normalized)
            validation = validate_citations(
                normalized, allowed=context.get("rag_allowed_citations") or {},
                answerable=bool(context.get("rag_answerable")), rag_reason=context.get("rag_reason"),
                sources=context.get("rag_source_contents") or {},
            )
            text, citations = validation.content, validation.citations
        if not rag_used and not self.web_used and self.product_links_needed:
            text = ensure_product_links(text, self.product_result)
        if self.link_guard_enabled:
            text = guard_links(text, self.known_ids)
        return FinalAnswer(text + web_footer, citations, citation_required, rag_used)
