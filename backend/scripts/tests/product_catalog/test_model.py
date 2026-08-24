from datetime import datetime, timezone
from decimal import Decimal
from types import MappingProxyType

import pytest

from backend.scripts.product_catalog import CatalogProductCandidate
from backend.scripts.product_catalog.model import (
    CatalogProduct,
    ImageCandidate,
    RawProduct,
)


def _raw(**changes):
    values = {
        "name": "MacBook Air",
        "brand": "Apple",
        "category": "COMPUTER",
        "price": Decimal("7999.00"),
        "currency": "CNY",
        "description": "Lightweight laptop",
        "selling_points": ("M4 chip",),
        "specs": {"memory": "16GB"},
        "source_name": "Apple",
        "source_url": "https://apple.com/macbook-air",
        "source_product_id": "macbook-air-m4",
        "source_updated_at": datetime(2025, 7, 1, tzinfo=timezone.utc),
        "collected_at": datetime(2025, 7, 2, tzinfo=timezone.utc),
        "image_candidates": (ImageCandidate(original_url="https://apple.com/macbook-air.jpg"),),
    }
    values.update(changes)
    return RawProduct(**values)


def _product(**changes):
    values = {
        "raw": _raw(),
        "stock": 100,
        "sales": 25,
        "image_url": "/images/macbook-air.webp",
        "image_sha256": "a" * 64,
        "content_hash": "b" * 64,
        "catalog_version": "2025-30",
        "image_original_bytes": 100,
        "image_output_bytes": 80,
    }
    values.update(changes)
    return CatalogProduct(**values)


def test_catalog_product_candidate_preserves_incomplete_extraction_facts():
    candidate = CatalogProductCandidate(raw=_raw(name=None, brand=None, price=None))

    assert candidate.raw.name is None
    assert candidate.raw.brand is None
    assert candidate.raw.price is None
    with pytest.raises(AttributeError):
        candidate.raw = _raw()


def test_catalog_product_serializes_auditable_facts_and_simulated_commerce_values():
    payload = _product().to_json()

    assert payload["price"] == "7999.00"
    assert payload["source_updated_at"] == "2025-07-01T00:00:00Z"
    assert payload["specs"] == {"memory": "16GB"}
    assert payload["origin"] is None
    assert payload["material"] is None
    assert payload["production_date"] is None
    assert payload["commerce_values_simulated"] is True
    assert payload["stock"] == 100
    assert payload["sales"] == 25
    assert payload["image_original_bytes"] == 100
    assert payload["image_output_bytes"] == 80


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("raw", _raw(name=" "), "name must be nonblank"),
        ("raw", _raw(brand=""), "brand must be nonblank"),
        ("raw", _raw(currency=" "), "currency must be nonblank"),
        ("raw", _raw(source_name=""), "source_name must be nonblank"),
        ("raw", _raw(source_url=""), "source_url must be nonblank"),
        ("raw", _raw(source_product_id=""), "source_product_id must be nonblank"),
        ("raw", _raw(price=Decimal("0")), "price must be positive"),
        ("raw", _raw(specs={"bad": {1, 2}}), "specs must be JSON-serializable"),
        ("image_url", "https://example.com/image.webp", "image_url must be a local catalog path"),
        ("image_sha256", "not-a-sha256", "image_sha256 must be a 64-character hexadecimal hash"),
        ("content_hash", "not-a-sha256", "content_hash must be a 64-character hexadecimal hash"),
        ("commerce_values_simulated", False, "commerce_values_simulated must be true"),
    ],
)
def test_catalog_product_rejects_invalid_final_record_values(field, value, message):
    with pytest.raises(ValueError, match=message):
        _product(**{field: value})


def test_catalog_product_materializes_nested_mapping_specs_for_serialization():
    product = _product(
        raw=_raw(specs=MappingProxyType({"a": MappingProxyType({"values": (1, 2)})}))
    )

    assert product.to_json()["specs"] == {"a": {"values": [1, 2]}}


@pytest.mark.parametrize("specs", [{"a": {"set"}}, {"a": [float("nan")]}])
def test_catalog_product_rejects_nested_non_json_specs(specs):
    with pytest.raises(ValueError, match="specs must be JSON-serializable"):
        _product(raw=_raw(specs=specs))
