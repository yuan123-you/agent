from copy import deepcopy
from datetime import datetime, timezone
import json
import pytest
from backend.scripts.product_catalog.official_store import parse_product_page, listing_product_urls

URL = "https://www.apple.com.cn/shop/product/mkr74fe/a"
PHOTO = "https://store.storeimages.cdn-apple.com/1/as-images.apple.com/is/MKR74?wid=1200&hei=1200&fmt=jpeg"

def page(currency="CNY", photo=PHOTO):
    product = {"productTitle": "带支架的 iPhone 双面夹 - 海军蓝色", "purchaseInfo": {
        "partNumber": "MKR74FE/A", "price": {"priceCurrency": currency,
        "currentPrice": {"raw_amount": "999.00"}}, "buyNowButton": {"disabled": False}},
        "imageGallery": {"galleryImagesList": {"items": [{"value": {"gallery": {
        "sources": [{"srcSet": photo}], "alt": "海军蓝色保护壳正面实物图", "noImage": False}}}]}}}
    overview = {"tiles": {"groups": {"items": [{"value": {"render": "<h3>概述</h3><p>内置磁体，可展开支架。</p>"}}]}}}
    compatibility = {"compatibleProducts": [{"header": "iPhone 机型", "products": {"items": [{"value": {"text": "iPhone"}}]}}]}
    return "".join("<script>window.pageLevelData." + key + " = " + json.dumps(obj, ensure_ascii=False) + ";</script>"
        for key, obj in [("PDPContent", product), ("Overview", overview), ("Compatibility", compatibility)])


def test_extracts_same_sku_chinese_name_cny_price_gallery_and_source_specs():
    p = parse_product_page(page(), URL, datetime(2026, 10, 28, tzinfo=timezone.utc))
    assert p["name"] == "带支架的 iPhone 双面夹 - 海军蓝色"
    assert p["source_product_id"] == "MKR74FE/A"
    assert p["price"] == "999.00" and p["currency"] == "CNY"
    assert p["original_image_url"] == PHOTO
    assert p["source_url"] == URL
    assert p["specs"]["产品型号"] == "MKR74FE/A"
    assert "iPhone" in p["specs"]["兼容机型"]
    assert "内置磁体" in p["description"] and "<p>" not in p["description"]
    assert p["sales"] == 0 and p["commerce_values_simulated"] is True


@pytest.mark.parametrize("currency,photo", [("USD", PHOTO), ("CNY", "data:image/svg+xml,emoji"),
    ("CNY", "https://picsum.photos/600/600"), ("CNY", "https://evil.example/p.jpg")])
def test_rejects_foreign_currency_and_untraceable_or_placeholder_photos(currency, photo):
    with pytest.raises(ValueError): parse_product_page(page(currency, photo), URL)


def test_rejects_official_page_without_product_price_and_sku():
    with pytest.raises(ValueError): parse_product_page("<h1>Store</h1>", URL)


def test_collects_only_official_product_links_in_html_or_embedded_models():
    html = '<a href="/shop/product/abc/a?fnode=1">Item</a><script>{"productDetailsUrl":"https://www.apple.com.cn/shop/product/def/a"}</script><a href="https://evil.example/shop/product/x/a">X</a>'
    assert listing_product_urls(html) == ["https://www.apple.com.cn/shop/product/abc/a", "https://www.apple.com.cn/shop/product/def/a"]


@pytest.mark.parametrize("title,category,brand", [
    ("Aer Go Pack 2 背包", "BAGS", "Aer"),
    ("Herschel Cloud Sling 斜挎包 (适用于 iPhone)", "BAGS", "Herschel"),
    ("带有触控 ID 的妙控键盘 (USB-C)", "LAPTOP", "Apple"),
    ("两件装 Beats USB-A 转 USB-C 编织连接线", "PHONE", "Beats"),
    ("Powerbeats Pro 2 高性能耳机", "PHONE", "Beats"),
])
def test_classifies_explicit_product_type_and_brand_without_using_compatible_device(title, category, brand):
    html = page().replace("带支架的 iPhone 双面夹 - 海军蓝色", title)
    p = parse_product_page(html, URL)
    assert (p["category"], p["brand"]) == (category, brand)
