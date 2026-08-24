from datetime import datetime, timezone
from decimal import Decimal

from backend.scripts.product_catalog.model import CatalogProduct, ImageCandidate, RawProduct


def test_catalog_product_serializes_auditable_facts_and_simulated_commerce_values():
    product = CatalogProduct(
        raw=RawProduct(
            name="MacBook Air",
            brand="Apple",
            category="COMPUTER",
            price=Decimal("7999.00"),
            currency="CNY",
            description="Lightweight laptop",
            selling_points=("M4 chip",),
            specs={"memory": "16GB"},
            source_name="Apple",
            source_url="https://apple.com/macbook-air",
            source_product_id="macbook-air-m4",
            source_updated_at=datetime(2025, 7, 1, tzinfo=timezone.utc),
            collected_at=datetime(2025, 7, 2, tzinfo=timezone.utc),
            image_candidates=(ImageCandidate(original_url="https://apple.com/macbook-air.jpg"),),
        ),
        stock=100,
        sales=25,
        image_url="/images/macbook-air.webp",
        image_sha256="a" * 64,
        content_hash="b" * 64,
        catalog_version="2025-30",
    )

    payload = product.to_json()

    assert payload["price"] == "7999.00"
    assert payload["source_updated_at"] == "2025-07-01T00:00:00Z"
    assert payload["specs"] == {"memory": "16GB"}
    assert payload["origin"] is None
    assert payload["material"] is None
    assert payload["production_date"] is None
    assert payload["commerce_values_simulated"] is True
    assert payload["stock"] == 100
    assert payload["sales"] == 25
