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