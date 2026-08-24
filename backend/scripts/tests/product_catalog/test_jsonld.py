from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from backend.scripts.product_catalog.jsonld import extract_products


def test_extract_products_skips_malformed_jsonld_and_extracts_graph_product():
    html = (Path(__file__).parent / "fixtures" / "product_page.html").read_text(encoding="utf-8")
    collected_at = datetime(2025, 7, 1, 12, 0, tzinfo=timezone.utc)

    products = extract_products(html, "https://shop.example.test/orbit", collected_at, "Example Shop")

    assert len(products) == 1
    product = products[0]
    assert product.name == "Orbit Headphones"
    assert product.brand == "Acme Audio"
    assert product.price == Decimal("199.50")
    assert product.currency == "USD"
    assert product.source_product_id == "ORBIT-100"
    assert product.description == "Wireless headphones with spatial audio."
    assert product.specs == {"Color": "Midnight Blue", "Battery life": "30 hours"}
    assert product.source_name == "Example Shop"
    assert product.source_url == "https://shop.example.test/orbit"
    assert product.collected_at == collected_at
    assert [image.original_url for image in product.image_candidates] == [
        "https://images.example.test/orbit-1.jpg",
        "https://images.example.test/orbit-2.jpg",
    ]


def test_extract_products_rejects_products_missing_required_source_facts():
    html = '<script type="application/ld+json">{"@type":"Product","name":"Invisible","image":"https://example.test/image.jpg"}</script>'

    assert extract_products(html, "https://example.test/product", datetime.now(timezone.utc), "Example") == []

def test_extract_products_uses_product_sku_before_selected_offer_sku_and_accepts_jsonld_parameters():
    html = '''<script type="application/ld+json; charset=utf-8">{
        "@type": "Product", "name": "Camera", "brand": "Acme",
        "image": "https://example.test/camera.jpg", "sku": "PRODUCT-SKU",
        "offers": {"price": "10", "priceCurrency": "USD", "sku": "OFFER-SKU"}
    }</script>'''

    [product] = extract_products(html, "https://example.test/camera", datetime.now(timezone.utc), "Example")

    assert product.source_product_id == "PRODUCT-SKU"


def test_extract_products_uses_selected_offer_sku_and_rejects_blank_source_identity():
    html = '''<script type="application/ld+json">{
        "@type": "Product", "name": "Camera", "brand": "Acme",
        "image": "https://example.test/camera.jpg",
        "offers": {"price": "10", "priceCurrency": "USD", "sku": "OFFER-SKU"}
    }</script>'''
    collected_at = datetime.now(timezone.utc)

    assert extract_products(html, "https://example.test/camera", collected_at, "Example")[0].source_product_id == "OFFER-SKU"
    assert extract_products(html, "https://example.test/camera", collected_at, "   ") == []
    assert extract_products(html, "   ", collected_at, "Example") == []
