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
                          catalog_version="2026-08-24", image_original_bytes=100 + index,
                          image_output_bytes=80 + index)


def catalog_inputs() -> list[CatalogProduct]:
    return [product(category_index * 120 + position, category)
            for category_index, category in enumerate(CATEGORIES)
            for position in range(120)]


def _verify_with_timestamp_updates(tmp_path: Path, **updates):
    write_catalog(catalog_inputs(), tmp_path)
    manifest = tmp_path / "products.jsonl"
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    rows[0].update(updates)
    manifest.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8", newline="\n")
    return verify_catalog(manifest, tmp_path / "catalog-report.json")


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


def test_catalog_report_uses_manifest_byte_statistics_and_allows_shared_images(tmp_path: Path):
    shared_hash = "f" * 64
    first = replace(product(1), image_sha256=shared_hash, image_url=f"/api/v1/product-images/catalog/{shared_hash}.webp")
    second = replace(product(2), image_sha256=shared_hash, image_url=f"/api/v1/product-images/catalog/{shared_hash}.webp")

    selected = select_catalog([first, second], total=2, replacement_count=1)

    assert len(selected) == 2
    assert selected[0].image_sha256 == selected[1].image_sha256
    report = write_catalog(catalog_inputs(), tmp_path)
    rows = [json.loads(line) for line in (tmp_path / "products.jsonl").read_text(encoding="utf-8").splitlines()]
    assert report.bytes_before == sum(row["image_original_bytes"] for row in rows)
    assert report.bytes_after == sum(row["image_output_bytes"] for row in rows)
    assert report.bytes_saved == report.bytes_before - report.bytes_after
    assert report.bytes_saved_percentage == pytest.approx(report.bytes_saved * 100 / report.bytes_before)


def test_verify_catalog_rejects_corrupted_byte_report(tmp_path: Path):
    write_catalog(catalog_inputs(), tmp_path)
    report_path = tmp_path / "catalog-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["bytes_saved"] += 1
    report_path.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    result = verify_catalog(tmp_path / "products.jsonl", report_path)

    assert not result.valid
    assert "report image statistics mismatch" in result.errors


def test_duplicate_winner_is_canonical_across_reversed_and_shuffled_input():
    first = product(1)
    duplicate = replace(product(2), content_hash=first.content_hash)
    inputs = [first, duplicate, product(3)]
    shuffled = inputs[:]
    random.Random(42).shuffle(shuffled)

    selected = select_catalog(inputs, total=2, replacement_count=1)
    reversed_selected = select_catalog(list(reversed(inputs)), total=2, replacement_count=1)
    shuffled_selected = select_catalog(shuffled, total=2, replacement_count=1)

    assert [item.to_json() for item in selected] == [item.to_json() for item in reversed_selected]
    assert [item.to_json() for item in selected] == [item.to_json() for item in shuffled_selected]


def test_report_counts_all_overlapping_duplicate_and_image_failures(tmp_path: Path):
    first = product(1)
    overlapping = replace(
        first,
        raw=replace(first.raw, image_candidates=(ImageCandidate("https://picsum.photos/200"),)),
    )

    report = write_catalog(catalog_inputs() + [overlapping], tmp_path)

    assert report.input_count == 2521
    assert report.duplicate_source_keys == 1
    assert report.duplicate_content_hashes == 1
    assert report.image_failures == 1
    assert sum(report.rejection_counts.values()) == report.input_count - report.product_count


def test_verify_rejects_missing_provenance_uppercase_image_and_simulated_fields_report(tmp_path: Path):
    write_catalog(catalog_inputs(), tmp_path)
    manifest = tmp_path / "products.jsonl"
    report_path = tmp_path / "catalog-report.json"
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    rows[0]["name"] = ""
    rows[1]["image_url"] = rows[1]["image_url"].upper()
    manifest.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8", newline="\n")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["simulated_fields"] = ["sales", "stock"]
    report_path.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    result = verify_catalog(manifest, report_path)

    assert not result.valid
    assert "missing name" in result.errors
    assert "invalid image path" in result.errors
    assert "report simulated fields mismatch" in result.errors


def test_verify_catalog_returns_failure_not_exception_for_hostile_json_field_types(tmp_path: Path):
    write_catalog(catalog_inputs(), tmp_path)
    manifest = tmp_path / "products.jsonl"
    report = tmp_path / "catalog-report.json"
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    rows[0].update({"source_url": [], "image_url": {}, "image_sha256": [], "price": {}, "image_original_bytes": "100", "source_updated_at": [], "collected_at": {}, "replacement_slot": {}})
    manifest.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8", newline="\n")

    result = verify_catalog(manifest, report)

    assert not result.valid
    assert "invalid source URL" in result.errors
    assert "invalid image path" in result.errors
    assert "invalid image hash" in result.errors
    assert "price must be positive" in result.errors
    assert "invalid image bytes" in result.errors
    assert "stale time" in result.errors


@pytest.mark.parametrize("bad_timestamp", [[], "not-a-timestamp", "2026-08-24T00:00:00"])
def test_verify_rejects_bad_source_updated_at_even_with_fresh_collected_at(tmp_path: Path, bad_timestamp):
    result = _verify_with_timestamp_updates(tmp_path, source_updated_at=bad_timestamp)

    assert not result.valid
    assert "invalid source_updated_at" in result.errors


@pytest.mark.parametrize("bad_timestamp", [[], "not-a-timestamp", "2026-08-24T00:00:00"])
def test_verify_rejects_bad_collected_at_even_with_fresh_source_updated_at(tmp_path: Path, bad_timestamp):
    result = _verify_with_timestamp_updates(tmp_path, collected_at=bad_timestamp)

    assert not result.valid
    assert "invalid collected_at" in result.errors


def test_verify_accepts_null_optional_source_updated_at(tmp_path: Path):
    result = _verify_with_timestamp_updates(tmp_path, source_updated_at=None)

    assert result.valid


def test_verify_rejects_stale_valid_timestamp_pair(tmp_path: Path):
    stale = "2024-12-31T23:59:59+00:00"
    result = _verify_with_timestamp_updates(tmp_path, source_updated_at=stale, collected_at=stale)

    assert not result.valid
    assert "stale time" in result.errors
