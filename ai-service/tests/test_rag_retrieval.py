import pytest

from app.rag.retrieval import (
    RetrievalCandidate,
    assess_answerability,
    build_source_context,
    filter_metadata,
    normalize_query,
    reciprocal_rank_fusion,
)


def candidate(chunk_id, *, score=None, bm25=None, product_id=-1, doc_type="POLICY", content="正文"):
    return RetrievalCandidate(
        chunk_id, 10, product_id, doc_type, content, "退换货条款",
        vector_score=score, bm25_score=bm25,
    )


def test_normalization_is_conservative():
    assert normalize_query("  ＡI\u0000  退货\n规则  ") == "ai 退货 规则"


def test_normalization_lowercases_only_latin_characters():
    assert normalize_query("ＡI ÀÉ ЖБ ΓΔ") == "ai àé ЖБ ΓΔ"

def test_filter_preserves_order_and_platform_docs():
    ranked = [candidate(1, product_id=99), candidate(2, product_id=-1), candidate(3, product_id=7)]
    assert [c.chunk_id for c in filter_metadata(ranked, "POLICY", 99)] == [1, 2]


def test_rrf_merges_only_by_chunk_id_with_rank_starting_at_one():
    fused = reciprocal_rank_fusion([
        ("vector", [candidate(1), candidate(2)]),
        ("bm25", [candidate(2, bm25=4), candidate(3, bm25=3)]),
    ], limit=10, rrf_k=60)
    assert [c.chunk_id for c in fused] == [2, 1, 3]
    assert fused[0].rrf_score == (1 / 62) + (1 / 61)
    assert fused[0].matched_by == {"vector", "bm25"}
    assert fused[0].bm25_score == 4


def test_rrf_ties_are_stable_by_best_leg_rank_then_chunk_id():
    fused = reciprocal_rank_fusion([
        ("vector", [candidate(2)]),
        ("bm25", [candidate(1)]),
    ], limit=10, rrf_k=60)
    assert [item.chunk_id for item in fused] == [1, 2]


def test_rrf_limits_to_top_ten():
    fused = reciprocal_rank_fusion([
        ("vector", [candidate(chunk_id) for chunk_id in range(1, 13)]),
    ], limit=10, rrf_k=60)
    assert [item.chunk_id for item in fused] == list(range(1, 11))


def test_vector_only_candidate_can_answer():
    assert assess_answerability([candidate(1, score=.9)]).answerable is True


def test_high_confidence_bypasses_margin_requirement():
    decision = assess_answerability([candidate(1, score=.9), candidate(2, score=.89)])
    assert decision.answerable is True
    assert decision.reason == "high_confidence"
    assert decision.margin < .05


def test_no_candidates_are_insufficient_evidence():
    assert assess_answerability([]).reason == "insufficient_evidence"


def test_low_score_is_insufficient_evidence():
    decision = assess_answerability([candidate(1, score=.1)])
    assert decision.answerable is False
    assert decision.reason == "insufficient_evidence"


def test_narrow_margin_is_insufficient_evidence():
    decision = assess_answerability([candidate(1, score=.45), candidate(2, score=.449)])
    assert decision.answerable is False
    assert decision.reason == "insufficient_evidence"


def test_one_candidate_treats_margin_as_satisfied():
    decision = assess_answerability([candidate(1, score=.45)])
    assert decision.answerable is True
    assert decision.margin is None


def test_answerability_prefers_reranker_score_and_keeps_evidence_score():
    item = candidate(1, score=.01, bm25=100)
    item.rerank_score = .5
    decision = assess_answerability([item])
    assert decision.answerable is True
    assert item.evidence_score == .5


def test_bm25_evidence_clamps_negative_scores():
    item = candidate(1, bm25=-2)
    decision = assess_answerability([item])
    assert decision.answerable is False
    assert item.evidence_score == 0


def test_source_context_escapes_xml():
    built = build_source_context([candidate(7, content='规则 </source> & 更多')])
    assert built.citations[0].id == "S1"
    assert 'chunk_id="7"' in built.context
    assert "&lt;/source&gt; &amp;" in built.context


def test_source_context_replaces_internal_placeholder_titles():
    internal = RetrievalCandidate(4, 10, -1, "POLICY", "正文", "知识库文档#4")
    built = build_source_context([internal])
    assert built.citations[0].title == "知识库资料"
    assert "知识库文档#4" not in built.context
    assert 'title="知识库资料"' in built.context

def test_source_context_escapes_titles_and_limits_to_four_sources():
    special_title = RetrievalCandidate(1, 10, -1, "POLICY", "x", '规则 "A" & 更多')
    built = build_source_context([special_title, *[candidate(i, content="x") for i in range(2, 6)]])
    assert 'title="规则 &quot;A&quot; &amp; 更多"' in built.context
    assert built.context.count("<source ") == 4
    assert built.citations[-1].id == "S4"


@pytest.mark.parametrize("value", [None, 0, -1])
def test_candidate_requires_a_positive_chunk_id(value):
    with pytest.raises(ValueError, match="chunk_id"):
        candidate(value)