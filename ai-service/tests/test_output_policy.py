"""Evidence policy independent of HTTP/SSE; current RAG remains the only KB pipeline."""
import pytest
from app.agent.output import OutputPolicy


def policy_context():
    return {"rag_used": True, "rag_answerable": True, "rag_allowed_citations": {
        "S1": {"id": "S1", "chunk_id": 7, "title": "平台规则"},
    }}


def test_policy_query_cannot_stream_or_bypass_citations_with_web_results():
    policy = OutputPolicy("平台退货规则是什么")
    policy.tool_completed("web_search", {"results": [{"title": "网上说能退"}]})
    assert not policy.can_stream("web_answer", {})
    answer = policy.finalize("无需条件均可退货", {})
    assert answer.citation_required
    assert "无需条件均可退货" not in answer.content
    assert not answer.citations


def test_policy_preamble_is_held_as_soon_as_kb_tool_starts():
    policy = OutputPolicy("我想了解商品")
    assert policy.can_stream("small_talk", {})
    policy.tool_started("kb_search")
    assert not policy.can_stream("small_talk", {})


def test_citations_are_normalized_and_verified_against_current_evidence():
    policy = OutputPolicy("平台退款规则是什么")
    answer = policy.finalize("退款按原支付渠道退回。【S1】", policy_context())
    assert "[S1]" in answer.content
    assert answer.citations[0]["chunk_id"] == 7


def test_unknown_product_links_are_removed_in_final_output():
    policy = OutputPolicy("推荐手机")
    policy.tool_completed("product_search", {"products": [{"id": 7, "name": "真实手机", "link": "mall://product/7"}]})
    answer = policy.finalize("[真实](mall://product/7) [编造](mall://product/999)", {})
    assert "mall://product/7" in answer.content
    assert "mall://product/999" not in answer.content
    assert not policy.can_stream("agent", {})


def test_program_clarification_is_allowed_without_fabricated_policy_evidence():
    policy = OutputPolicy("这款商品的退货规则呢")
    answer = policy.finalize("模型忽略问题", {"policy_clarification": "请明确商品名称。"})
    assert answer.content == "请明确商品名称。"
    assert answer.citation_required and not answer.citations


def test_web_footer_is_appended_once_and_only_after_model_links_are_guarded():
    footer = "\n\n参考来源：[资料](https://example.com/verified)"
    policy = OutputPolicy("新闻")
    policy.tool_completed("web_search", {"results": []})
    answer = policy.finalize("查询结果" + footer, {}, web_footer=footer)
    assert answer.content.count(footer) == 1
    assert not answer.citation_required
