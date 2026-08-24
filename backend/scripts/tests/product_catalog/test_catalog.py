from __future__ import annotations

import json
import random
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from backend.scripts.product_catalog.catalog import select_catalog, verify_catalog, write_catalog
from backend.scripts.product_catalog.model import CATEGORIES, CatalogProduct, ImageCandidate, RawProduct

NOW = datetime(2026, 8, 24, tzinfo=timezone.utc)


def product(index: int, category: str | None = None) -> CatalogProduct:
    token = f"{index:064x}"
    raw = RawProduct(
        name=f"Product {index:04d}", brand=f"Brand {index % 19:02d}",
        category=category or CATEGORIES[index % len(CATEGORIES)], price=Decimal("19.99"),
        currency="USD", description="Real source description", selling_points=("Source fact",),
        specs={"model": f"M-{index:04d}"}, source_name=f"Shop {index % 7}",
        source_url=f"https://shop{index % 7}.example/products/{index}", source_product_id=f"SKU-{index:04d}",
        source_updated_at=NOW, collected_at=NOW,
        image_candidates=(ImageCandidate(f"https://images.example/{index}.webp"),),
    )
    return CatalogProduct(raw=raw, stock=10, sales=20,
                          image_url=f"/api/v1/product-images/catalog/{token}.webp",
                          image_sha256=token, content_hash=f"{index + 3000:064x}",
                          catalog_version="2026-08-24")


def catalog_inputs() -> list[CatalogProduct]:
    return [product(category_index * 120 + position, category)
            for category_index, category in enumerate(CATEGORIES)
            for position in range(120)]


def test_select_catalog_is_order_independent_round_robin_and_assigns_exact_replacement_slots():
    items = catalog_inputs()
    shuffled = items[:]
    random.Random(9).shuffle(shuffled)

    selected = select_catalog(items)
    selected_shuffled = select_catalog(shuffled)

    assert len(selected) == 2512
    assert [row.to_json() for row in selected] == [row.to_json() for row in selected_shuffled]
    assert [row.replacement_slot for row in selected[:512]] == list(range(1, 513))
    assert all(row.replacement_slot is None for row in selected[512:])
    assert set(row.raw.category for row in selected[:21]) == set(CATEGORIES)
    assert len({(row.raw.source_name, row.raw.source_product_id) for row in selected}) == 2512
    assert len({row.content_hash for row in selected}) == 2512


def test_write_catalog_is_utf8_stable_and_verification_hard_fails_global_constraint_violations(tmp_path: Path):
    report = write_catalog(catalog_inputs(), tmp_path)
    manifest = tmp_path / "products.jsonl"
    json_report = tmp_path / "catalog-report.json"
    markdown_report = tmp_path / "catalog-report.md"

    payload = manifest.read_bytes()
    assert payload.endswith(b"\n")
    assert b"\r\n" not in payload
    assert len(payload.splitlines()) == 2512
    assert report.product_count == 2512
    assert report.replacement_slots == 512
    assert report.simulated_fields == ["stock", "sales"]
    assert json.loads(json_report.read_text(encoding="utf-8"))["category_counts"] == report.category_counts
    assert "# Catalog report" in markdown_report.read_text(encoding="utf-8")
    assert verify_catalog(manifest, json_report).valid

    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    rows[0]["image_url"] = "https://picsum.photos/200"
    manifest.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8", newline="\n")

    result = verify_catalog(manifest, json_report)
    assert not result.valid
    assert any("remote or Picsum" in error for error in result.errors)


@pytest.mark.parametrize("field,value", [
    ("content_hash", product(1).content_hash),
    ("raw", replace(product(2).raw, price=Decimal("0"))),
    ("commerce_values_simulated", False),
])
def test_select_catalog_rejects_duplicates_invalid_price_and_simulation_flag(field, value):
    bad = product(2)
    object.__setattr__(bad, field, value)

    assert len(select_catalog([product(1), bad], total=1, replacement_count=1)) == 1
    with pytest.raises(ValueError, match="only 1 valid products"):
        select_catalog([product(1), bad], total=2, replacement_count=1)


def test_verify_catalog_hard_fails_invalid_hash_specs_and_stale_time(tmp_path: Path):
    write_catalog(catalog_inputs(), tmp_path)
    manifest = tmp_path / "products.jsonl"
    report = tmp_path / "catalog-report.json"
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    rows[0]["content_hash"] = "not-a-hash"
    rows[1]["specs"] = []
    rows[2]["source_updated_at"] = "2024-01-01T00:00:00Z"
    rows[2]["collected_at"] = "2024-01-01T00:00:00Z"
    manifest.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8", newline="\n")

    result = verify_catalog(manifest, report)

    assert not result.valid
    assert "invalid content hash" in result.errors
    assert "invalid specs" in result.errors
    assert "stale time" in result.errors
