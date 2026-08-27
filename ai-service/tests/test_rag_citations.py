import pytest

from app.rag.citations import validate_citations


ALLOWED = {"S1": {"id": "S1", "chunk_id": 7, "title": "退换货条款"}}


def test_valid_ids_return_referenced_metadata():
    result = validate_citations("支持七天退货。[S1]", allowed=ALLOWED, answerable=True)

    assert result.valid is True
    assert result.content == "支持七天退货。[S1]"
    assert result.citations == (ALLOWED["S1"],)
    assert result.reason == "valid"


def test_missing_and_unknown_ids_fail():
    assert validate_citations(
        "支持七天退货。", allowed=ALLOWED, answerable=True
    ).reason == "missing_citation"
    assert validate_citations(
        "支持七天退货。[S9]", allowed=ALLOWED, answerable=True
    ).reason == "unknown_citation"


def test_referenced_ids_are_deduplicated_in_first_seen_order():
    allowed = {
        "S1": ALLOWED["S1"],
        "S2": {"id": "S2", "chunk_id": 8, "title": "保修条款"},
    }

    result = validate_citations(
        "先看[S2]，再看[S1]，仍以[S2]为准。", allowed=allowed, answerable=True
    )

    assert result.citations == (allowed["S2"], allowed["S1"])


def test_unanswerable_cannot_emit_substantive_answer():
    result = validate_citations("我认为可以退货。", allowed={}, answerable=False)

    assert result.valid is False
    assert result.content == "当前知识库证据不足，暂时无法可靠回答该问题。"
    assert result.citations == ()


def test_retrieval_unavailable_keeps_separate_wording():
    result = validate_citations(
        "我认为可以退货。",
        allowed={},
        answerable=False,
        rag_reason="retrieval_unavailable",
    )

    assert result.valid is False
    assert result.reason == "retrieval_unavailable"
    assert result.content == "知识库暂时不可用，请稍后再试。"
    assert result.citations == ()


def test_only_public_structured_metadata_is_returned():
    allowed = {
        "S1": {
            "id": "S1",
            "chunk_id": 7,
            "title": "退换货条款",
            "internal_title": "policy-v3-internal",
            "score": 0.99,
        }
    }

    result = validate_citations("支持七天退货。[S1]", allowed=allowed, answerable=True)

    assert result.citations == ({"id": "S1", "chunk_id": 7, "title": "退换货条款"},)


@pytest.mark.parametrize("forged", ["[S0]", "[S01]"])
def test_mixed_valid_and_noncanonical_source_markers_fail(forged):
    result = validate_citations(
        f"真实依据[S1]，伪造依据{forged}", allowed=ALLOWED, answerable=True
    )

    assert result.valid is False
    assert result.reason == "unknown_citation"
    assert result.citations == ()
