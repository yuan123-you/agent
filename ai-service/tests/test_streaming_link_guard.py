import pytest
from app.agent.link_guard import GuardedLinkBuffer, guard_links


@pytest.mark.parametrize("text", [
    "你好 [错误](mall://product/999) 后续",
    "你好 [跨行\n商品](mall://product/999) 后续",
    "[合法](mall://product/7) 与 [非法](mall://product/999)",
    "普通 [说明] 文本和 [资料] 继续",
])
def test_every_chunk_boundary_matches_whole_answer_guard_without_leaking_ids(text):
    known = {"7"}
    for split in range(1, len(text)):
        buffer = GuardedLinkBuffer(known)
        early = buffer.push(text[:split])
        early += buffer.push(text[split:])
        # Held incomplete text is only flushed through the whole-answer final guard.
        result = early + guard_links(buffer.pending, known)
        assert result == guard_links(text, known), (text, split, result)
        assert "mall://product/999" not in result


def test_disabled_guard_preserves_provider_chunks():
    buffer = GuardedLinkBuffer(set(), enabled=False)
    assert buffer.push("[商品](") == "[商品]("
    assert buffer.push("mall://product/7)") == "mall://product/7)"
