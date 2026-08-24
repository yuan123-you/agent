from datetime import datetime, timezone
from hashlib import sha256
from decimal import Decimal

from backend.scripts.product_catalog.model import ImageCandidate, RawProduct
from backend.scripts.product_catalog.normalize import deduplicate, normalize, validation_errors


MINIMUM_TIME = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _raw(**changes):
    values = {
        "name": "Orbit Phone Pro",
        "brand": "Acme Audio",
        "category": None,
        "price": Decimal("199.995"),
        "currency": "usd",
        "description": "  <p>Wireless&nbsp; headphones <b>with</b> spatial audio.</p>  ",
        "selling_points": ("  <strong>30-hour</strong> battery  ",),
        "specs": {" Color ": "  Midnight Blue  "},
        "source_name": " Example Shop ",
        "source_url": "HTTPS://Example.TEST:443/products/orbit/?utm_source=feed&color=blue#details",
        "source_product_id": " ORBIT-100 ",
        "source_updated_at": None,
        "collected_at": datetime(2025, 7, 1, tzinfo=timezone.utc),
        "image_candidates": (ImageCandidate("HTTPS://Images.Example.TEST:443/orbit.jpg#hero"),),
        "origin": None,
        "material": None,
        "production_date": None,
    }
    values.update(changes)
    return RawProduct(**values)


def test_normalize_cleans_html_and_whitespace_preserves_unicode_and_sets_demo_values():
    candidate = normalize(_raw(name="  Ｏｒｂｉｔ™  手机  "), "PHONE")

    assert candidate.raw.name == "Ｏｒｂｉｔ™ 手机"
    assert candidate.raw.description == "Wireless headphones with spatial audio."
    assert candidate.raw.selling_points == ("30-hour battery",)
    assert candidate.raw.specs == {"Color": "Midnight Blue"}
    assert candidate.raw.price == Decimal("200.00")
    assert candidate.raw.currency == "USD"
    assert candidate.raw.source_name == "Example Shop"
    assert candidate.raw.source_product_id == "ORBIT-100"
    assert candidate.raw.source_url == "https://example.test/products/orbit/?color=blue"
    assert candidate.raw.image_candidates[0].original_url == "https://images.example.test/orbit.jpg"
    assert candidate.raw.category == "PHONE"
    assert candidate.raw.origin is None
    assert candidate.raw.material is None
    assert candidate.raw.production_date is None
    seed = int(sha256(candidate.unique_key.encode("utf-8")).hexdigest()[:8], 16)
    assert candidate.simulated_commerce_fields is True
    assert candidate.stock == 10 + seed % 491
    assert candidate.sales == 50 + seed % 9951


def test_normalize_uses_source_hint_before_keyword_mapping():
    candidate = normalize(_raw(name="Galaxy Book", category="clothing"), "computer")

    assert candidate.raw.category == "COMPUTER"


def test_normalize_maps_category_from_keywords_when_source_hint_is_unknown():
    candidate = normalize(_raw(name="Orbit wireless headphones", category=None), None)

    assert candidate.raw.category == "DIGITAL"


def test_validation_rejects_invalid_currency_and_stale_sources_but_accepts_fresh_collection():
    invalid_currency = normalize(_raw(currency="ZZZ"), "PHONE")
    stale = normalize(
        _raw(
            source_updated_at=datetime(2024, 12, 31, tzinfo=timezone.utc),
            collected_at=datetime(2024, 12, 31, tzinfo=timezone.utc),
        ),
        "PHONE",
    )
    fresh_collection = normalize(
        _raw(
            source_updated_at=datetime(2024, 12, 31, tzinfo=timezone.utc),
            collected_at=MINIMUM_TIME,
        ),
        "PHONE",
    )
    fresh_source_update = normalize(
        _raw(
            source_updated_at=MINIMUM_TIME,
            collected_at=datetime(2024, 12, 31, tzinfo=timezone.utc),
        ),
        "PHONE",
    )

    assert "unsupported currency: ZZZ" in validation_errors(invalid_currency, MINIMUM_TIME)
    assert "source is older than minimum_time" in validation_errors(stale, MINIMUM_TIME)
    assert validation_errors(fresh_collection, MINIMUM_TIME) == []
    assert validation_errors(fresh_source_update, MINIMUM_TIME) == []


def test_deduplicate_removes_repeated_source_sku_and_normalized_brand_model():
    first = normalize(_raw(), "PHONE")
    duplicate_sku = normalize(_raw(name="Another product", source_url="https://example.test/another"), "PHONE")
    duplicate_model = normalize(
        _raw(
            name="  ORBIT   PHONE  PRO ",
            brand="ＡＣＭＥ ＡＵＤＩＯ",
            source_name="Other Shop",
            source_product_id="OTHER-1",
            source_url="https://other.example.test/orbit",
        ),
        "PHONE",
    )
    distinct = normalize(
        _raw(
            name="Orbit Phone Mini",
            source_product_id="ORBIT-101",
            source_url="https://example.test/mini",
        ),
        "PHONE",
    )

    assert deduplicate([first, duplicate_sku, duplicate_model, distinct]) == [first, distinct]


def test_normalize_leaves_malformed_urls_for_validation_rejection():
    candidate = normalize(_raw(source_url="https://example.test:bad/"), "PHONE")

    assert "source_url must be an absolute HTTP URL" in validation_errors(candidate, MINIMUM_TIME)
