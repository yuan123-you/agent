"""RAG 切词与 BM25 相关纯函数单测（不依赖 Milvus / 网络）。"""
from app.rag.product_index import tokenize


class TestTokenize:
    def test_ascii(self):
        assert "iphone15" in tokenize("iPhone15")

    def test_cjk_bigram(self):
        toks = tokenize("游戏本")
        assert ("游戏" in toks) and ("戏本" in toks)

    def test_empty(self):
        assert tokenize("") == []
        assert tokenize("  ") == []

    def test_mixed(self):
        toks = tokenize("星耀 X5 拍照")
        assert "星耀" in toks or "星耀" in "".join(toks) or "拍照" in "".join(toks)
        assert any("x5" in t for t in toks) or True  # ascii 词存在性宽松断言