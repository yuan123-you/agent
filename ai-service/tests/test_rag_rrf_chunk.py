"""RAG 质量升级单测：RRF 混排与标题感知的可配置中文分块。"""
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.rag.ingest import split_text
from app.tools.tools import _rrf_content


def _hit(content: str, doc_id: int = 1) -> dict:
    return {"content": content, "doc_id": doc_id, "score": 0.5}


class TestRrfContent:
    def test_dual_hit_ranked_first(self):
        a = _hit("退换货政策：七天无理由")
        b = _hit("保修期一年")
        merged = _rrf_content([[a, b], [a]], top_k=4)
        assert merged[0]["content"] == a["content"]

    def test_single_source_preserved(self):
        merged = _rrf_content([[_hit("仅向量命中")], [_hit("仅关键词命中")]], top_k=4)
        contents = {m["content"] for m in merged}
        assert contents == {"仅向量命中", "仅关键词命中"}

    def test_top_k_limits(self):
        hits = [[_hit(f"片段{i}", i) for i in range(5)], [_hit(f"片段{i}", i) for i in range(5)]]
        merged = _rrf_content(hits, top_k=3)
        assert len(merged) == 3

    def test_empty_inputs(self):
        assert _rrf_content([[], []], top_k=4) == []


class TestSplitText:
    def test_markdown_headers_keep_context(self):
        md = "# 退换货政策\n\n七天无理由退货。\n\n## 退款时效\n\n审核通过后 3 个工作日到账。"
        chunks = split_text(md)
        assert len(chunks) >= 2
        assert any("退换货政策" in c for c in chunks)
        assert any("退款时效" in c for c in chunks)

    def test_long_section_repeats_heading_and_respects_requested_size(self):
        md = "# 手机售后\n\n## 屏幕保障\n\n" + "。".join(f"条款{i:03d}适用于碎屏服务" for i in range(120))
        chunks = split_text(md, chunk_size=240, chunk_overlap=36)
        assert len(chunks) > 4
        assert all(len(c) <= 240 for c in chunks)
        assert all("手机售后" in c and "屏幕保障" in c for c in chunks)

    def test_chinese_punctuation_is_preferred_boundary(self):
        text = "。".join(f"第{i:02d}条规则包含完整条件" for i in range(40)) + "。"
        chunks = split_text(text, chunk_size=200, chunk_overlap=30)
        assert len(chunks) > 2
        assert all(len(c) <= 200 for c in chunks)
        assert all(c.endswith(("。", "；", "！", "？")) for c in chunks[:-1])

    def test_plain_text_degrades_to_paragraphs(self):
        text = "第一段。\n\n第二段。"
        chunks = split_text(text)
        assert chunks and "第一段。" in chunks[0]

    def test_empty(self):
        assert split_text("") == []
        assert split_text("   ") == []


class TestChunkSettings:
    def test_defaults_are_optimized_for_chinese_ecommerce(self):
        value = Settings(_env_file=None)
        assert value.rag_chunk_size == 600
        assert value.rag_chunk_overlap == 90

    @pytest.mark.parametrize(("size", "overlap"), [(199, 20), (600, -1), (600, 600), (600, 700)])
    def test_invalid_chunk_window_fails_fast(self, size, overlap):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, rag_chunk_size=size, rag_chunk_overlap=overlap)

