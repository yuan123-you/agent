import pytest
from unittest.mock import AsyncMock
from types import SimpleNamespace

from app.tools.tools import clean_search_keyword, product_search, set_tool_ctx
from app.rag import product_index


def test_clean_search_keyword_strips_order_and_noise_phrases():
    # 口语词 "帮我下单一个" 与 "没有要求" 应该被清洗
    raw = "帮我下单一个3000元的手机，没有要求"
    cleaned = clean_search_keyword(raw)
    assert "下单" not in (cleaned or "")
    assert "要求" not in (cleaned or "")
    assert "3000元" not in (cleaned or "")


@pytest.mark.asyncio
async def test_phone_search_filters_out_accessories(monkeypatch):
    # 当用户搜索手机时，即使候选中有带 iPhone/手机 字样的卡包、耳机、钥匙扣，也必须过滤掉，只保留真实手机
    corpus = product_index.ProductCorpus()
    products = [
        {"productId": 1, "name": "星耀 X5 Pro", "category": "PHONE", "price": 2999.00, "stock": 100, "sales": 10},
        {"productId": 2, "name": "iPhone 专用 MagSafe 精织斜纹卡包 - 海军蓝色", "category": "PHONE", "price": 449.00, "stock": 100, "sales": 50},
        {"productId": 3, "name": "Beats Studio Buds + 真无线降噪耳机 — 象牙白", "category": "PHONE", "price": 1349.00, "stock": 100, "sales": 40},
        {"productId": 4, "name": "AirTag 精织斜纹钥匙扣 - 深橄榄色", "category": "PHONE", "price": 299.00, "stock": 100, "sales": 30},
        {"productId": 5, "name": "轻语 Note 14", "category": "PHONE", "price": 2699.00, "stock": 100, "sales": 20},
    ]
    texts = [
        "星耀 X5 Pro 品牌 星耀 手机 智能手机 数码 卖点 旗舰影像 大电池",
        "iPhone 专用 MagSafe 精织斜纹卡包 手机 智能手机 数码",
        "Beats Studio Buds + 真无线降噪耳机 手机 智能手机 数码",
        "AirTag 精织斜纹钥匙扣 手机 智能手机 数码",
        "轻语 Note 14 品牌 轻语 手机 智能手机 数码",
    ]
    corpus.rebuild(products, texts)
    monkeypatch.setattr(product_index, "get_product_corpus", lambda: corpus)
    monkeypatch.setattr(product_index, "get_product_index", lambda: SimpleNamespace(
        vector_recall=AsyncMock(return_value=[(2, 0.9), (3, 0.8), (4, 0.7), (1, 0.6), (5, 0.5)])
    ))

    result = await product_index.hybrid_product_search(
        keyword="手机", category="PHONE", min_price=None, max_price=3000.0, top_k=5
    )
    product_names = [p["name"] for p in result["products"]]
    assert "星耀 X5 Pro" in product_names
    assert "轻语 Note 14" in product_names
    assert not any("卡包" in name for name in product_names)
    assert not any("耳机" in name for name in product_names)
    assert not any("钥匙扣" in name for name in product_names)


@pytest.mark.asyncio
async def test_phone_search_returns_empty_when_no_real_phones_exist(monkeypatch):
    # 当库中只有配件时，搜索手机必须返回空，严禁拿配件充数
    corpus = product_index.ProductCorpus()
    products = [
        {"productId": 2, "name": "iPhone 专用 MagSafe 精织斜纹卡包 - 海军蓝色", "category": "PHONE", "price": 449.00, "stock": 100, "sales": 50},
        {"productId": 3, "name": "Beats Studio Buds + 真无线降噪耳机 — 象牙白", "category": "PHONE", "price": 1349.00, "stock": 100, "sales": 40},
        {"productId": 4, "name": "AirTag 精织斜纹钥匙扣 - 深橄榄色", "category": "PHONE", "price": 299.00, "stock": 100, "sales": 30},
    ]
    texts = [p["name"] for p in products]
    corpus.rebuild(products, texts)
    monkeypatch.setattr(product_index, "get_product_corpus", lambda: corpus)
    monkeypatch.setattr(product_index, "get_product_index", lambda: SimpleNamespace(
        vector_recall=AsyncMock(return_value=[(2, 0.9), (3, 0.8), (4, 0.7)])
    ))

    result = await product_index.hybrid_product_search(
        keyword=None, category="PHONE", min_price=None, max_price=3000.0, top_k=5
    )
    assert result["total"] == 0
    assert result["products"] == []
