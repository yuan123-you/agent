"""Deterministic emission and independently verifiable catalog reports."""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
from typing import Any, Iterable
from urllib.parse import urlsplit

from .model import CATEGORIES, CatalogProduct

TARGET_COUNT, REPLACEMENT_COUNT = 2512, 512
MINIMUM_TIME = datetime(2025, 1, 1, tzinfo=timezone.utc)
_HASH = re.compile(r"^[0-9a-f]{64}$")
_IMAGE_PATH = re.compile(r"^/api/v1/product-images/catalog/([0-9a-f]{64})\.(jpg|png|webp)$")
_ALLOWED_REJECTIONS = frozenset({"duplicate source key", "duplicate content hash", "remote or Picsum image URL", "commerce_values_simulated must be true", "price must be positive", "unsupported category", "invalid specs", "stale time", "invalid content hash", "invalid image hash", "invalid image bytes", "invalid image path", "not selected", "missing name", "missing brand", "missing currency", "missing source_name", "missing source_url", "missing source_product_id", "invalid source URL", "invalid replacement slot"})

@dataclass(frozen=True)
class CatalogReport:
    input_count: int; product_count: int; replacement_slots: int; source_counts: dict[str, int]; category_counts: dict[str, int]; rejection_counts: dict[str, int]; duplicate_source_keys: int; duplicate_content_hashes: int; image_failures: int; bytes_before: int; bytes_after: int; bytes_saved: int; bytes_saved_percentage: float; webp_count: int; retained_original_count: int; shared_image_references: int; simulated_fields: list[str]
    def to_json(self) -> dict[str, Any]: return {field: getattr(self, field) for field in self.__dataclass_fields__}

@dataclass(frozen=True)
class VerificationResult:
    valid: bool; errors: tuple[str, ...]; product_count: int = 0; replacement_slots: int = 0
    @property
    def passed(self) -> bool: return self.valid

def _serialized_key(product: CatalogProduct) -> tuple[str, ...]:
    row = product.to_json(); raw = product.raw
    return (raw.category or "", raw.brand or "", raw.name or "", raw.source_name or "", raw.source_product_id or "", product.content_hash, product.image_sha256, product.image_url, json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str))

def _row_errors(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    path = row.get("image_url"); match = _IMAGE_PATH.fullmatch(path) if isinstance(path, str) else None
    if not match or match.group(1) != row.get("image_sha256"): errors.append("invalid image path")
    original = row.get("original_image_url")
    try:
        original_is_picsum = isinstance(original, str) and "picsum" in urlsplit(original).netloc.casefold()
    except (TypeError, ValueError):
        original_is_picsum = True
    if (isinstance(path, str) and ("picsum" in path.casefold() or path.startswith(("http://", "https://")))) or original_is_picsum: errors.append("remote or Picsum image URL")
    if row.get("commerce_values_simulated") is not True: errors.append("commerce_values_simulated must be true")
    try:
        price = Decimal(str(row.get("price")))
        if not price.is_finite() or price <= 0: errors.append("price must be positive")
    except (InvalidOperation, ValueError): errors.append("price must be positive")
    if not isinstance(row.get("category"), str) or row["category"] not in CATEGORIES: errors.append("unsupported category")
    for field in ("name", "brand", "currency", "source_name", "source_url", "source_product_id"):
        if not isinstance(row.get(field), str) or not row[field].strip(): errors.append(f"missing {field}")
    source_url = row.get("source_url")
    if not isinstance(source_url, str):
        errors.append("invalid source URL")
    else:
        try:
            source = urlsplit(source_url)
            if source.scheme not in {"http", "https"} or not source.hostname or source.username is not None or source.password is not None: errors.append("invalid source URL")
        except (TypeError, ValueError): errors.append("invalid source URL")
    for field, label in (("content_hash", "invalid content hash"), ("image_sha256", "invalid image hash")):
        if not isinstance(row.get(field), str) or not _HASH.fullmatch(row[field]): errors.append(label)
    try:
        before, after = row["image_original_bytes"], row["image_output_bytes"]
        if type(before) is not int or type(after) is not int or before <= 0 or after <= 0 or after > before: raise ValueError
    except (KeyError, ValueError): errors.append("invalid image bytes")
    if not isinstance(row.get("specs"), dict): errors.append("invalid specs")
    else:
        try: json.dumps(row["specs"], allow_nan=False)
        except (TypeError, ValueError): errors.append("invalid specs")
    times = []
    for value in (row.get("source_updated_at"), row.get("collected_at")):
        try:
            stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if stamp.tzinfo: times.append(stamp.astimezone(timezone.utc))
        except ValueError: pass
    if not times or max(times) < MINIMUM_TIME: errors.append("stale time")
    slot = row.get("replacement_slot")
    if slot is not None and (type(slot) is not int or not 1 <= slot <= REPLACEMENT_COUNT): errors.append("invalid replacement slot")
    return errors

def _pool(items: Iterable[CatalogProduct]) -> tuple[list[CatalogProduct], Counter[str], Counter[str]]:
    ordered = sorted(items, key=_serialized_key)
    rows = [item.to_json() for item in ordered]
    source_groups = Counter((str(row.get("source_name")), str(row.get("source_product_id"))) for row in rows)
    content_groups = Counter(item.content_hash for item in ordered)
    summaries = Counter({"duplicate source key": sum(count - 1 for count in source_groups.values()), "duplicate content hash": sum(count - 1 for count in content_groups.values()), "image failures": sum(any("image" in error for error in _row_errors(row)) for row in rows)})
    valid: list[CatalogProduct] = []; rejected: Counter[str] = Counter(); sources: set[tuple[str, str]] = set(); contents: set[str] = set()
    for item, row in zip(ordered, rows):
        errors = _row_errors(row); source = (str(row.get("source_name")), str(row.get("source_product_id")))
        if source in sources: errors.append("duplicate source key")
        if item.content_hash in contents: errors.append("duplicate content hash")
        if errors: rejected[min(errors)] += 1; continue
        sources.add(source); contents.add(item.content_hash); valid.append(item)
    return valid, rejected, summaries

def select_catalog(items: Iterable[CatalogProduct], total: int = TARGET_COUNT, replacement_count: int = REPLACEMENT_COUNT) -> list[CatalogProduct]:
    if type(total) is not int or total <= 0 or type(replacement_count) is not int or not 0 <= replacement_count <= total: raise ValueError("invalid catalog size or replacement count")
    valid, _, _ = _pool(items); queues: dict[str, list[CatalogProduct]] = defaultdict(list)
    for item in valid: queues[item.raw.category or ""].append(item)
    chosen: list[CatalogProduct] = []
    while len(chosen) < total:
        progressed = False
        for category in CATEGORIES:
            if queues[category]: chosen.append(queues[category].pop(0)); progressed = True
            if len(chosen) == total: break
        if not progressed: raise ValueError(f"only {len(chosen)} valid products available; need {total}")
    return [replace(item, replacement_slot=index if index <= replacement_count else None) for index, item in enumerate(chosen, 1)]

def _report(products: list[CatalogProduct], input_count: int, rejected: Counter[str], summaries: Counter[str]) -> CatalogReport:
    rows = [product.to_json() for product in products]; before = sum(row["image_original_bytes"] for row in rows); after = sum(row["image_output_bytes"] for row in rows); saved = before - after; webp = sum(row["image_url"].endswith(".webp") for row in rows); images = Counter(row["image_sha256"] for row in rows)
    return CatalogReport(input_count, len(rows), sum(row["replacement_slot"] is not None for row in rows), dict(sorted(Counter(row["source_name"] for row in rows).items())), {category: sum(row["category"] == category for row in rows) for category in CATEGORIES}, dict(sorted(rejected.items())), summaries["duplicate source key"], summaries["duplicate content hash"], summaries["image failures"], before, after, saved, saved * 100 / before, webp, len(rows) - webp, sum(count - 1 for count in images.values()), ["stock", "sales"])

def write_catalog(items: Iterable[CatalogProduct], output_dir: Path | str) -> CatalogReport:
    records = list(items); valid, rejected, summaries = _pool(records); products = select_catalog(valid); directory = Path(output_dir); directory.mkdir(parents=True, exist_ok=True)
    manifest = directory / "products.jsonl"; manifest.write_text("".join(json.dumps(product.to_json(), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n" for product in products), encoding="utf-8", newline="\n")
    rejected["not selected"] += len(valid) - len(products); report = _report(products, len(records), rejected, summaries); (directory / "catalog-report.json").write_text(json.dumps(report.to_json(), ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    lines = ["# Catalog report", "", *[f"- {key}: {value}" for key, value in report.to_json().items()], "", "## Sources", *[f"- {key}: {value}" for key, value in report.source_counts.items()], "", "## Categories", *[f"- {key}: {value}" for key, value in report.category_counts.items()], "", "## Rejections", *[f"- {key}: {value}" for key, value in report.rejection_counts.items()]]
    (directory / "catalog-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n"); return report

def verify_catalog(path: Path | str, report_path: Path | str) -> VerificationResult:
    errors: list[str] = []
    try:
        raw = Path(path).read_bytes(); rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
        if not raw.endswith(b"\n") or b"\r\n" in raw: errors.append("manifest must be UTF-8 JSONL with a final LF")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc: return VerificationResult(False, (f"invalid manifest: {exc}",))
    sources: set[tuple[Any, Any]] = set(); contents: set[Any] = set(); slots: list[Any] = []
    for row in rows:
        if not isinstance(row, dict): errors.append("invalid JSON row"); continue
        errors.extend(_row_errors(row)); source = (row.get("source_name") if isinstance(row.get("source_name"), str) else None, row.get("source_product_id") if isinstance(row.get("source_product_id"), str) else None)
        content = row.get("content_hash") if isinstance(row.get("content_hash"), str) else None
        if source in sources: errors.append("duplicate source key")
        if content in contents: errors.append("duplicate content hash")
        sources.add(source); contents.add(content)
        if type(row.get("replacement_slot")) is int: slots.append(row["replacement_slot"])
    if len(rows) != TARGET_COUNT: errors.append(f"expected {TARGET_COUNT} products")
    if sorted(slots) != list(range(1, REPLACEMENT_COUNT + 1)): errors.append(f"expected replacement slots 1-{REPLACEMENT_COUNT}")
    try:
        report = json.loads(Path(report_path).read_text(encoding="utf-8")); required = set(CatalogReport.__dataclass_fields__)
        if not required.issubset(report): errors.append("incomplete report statistics")
        rejected = report.get("rejection_counts")
        if not isinstance(rejected, dict) or set(rejected) - _ALLOWED_REJECTIONS or any(type(value) is not int or value < 0 for value in rejected.values()):
            errors.append("invalid rejection statistics")
            rejected = {}
        before = sum(row.get("image_original_bytes", 0) for row in rows if type(row.get("image_original_bytes")) is int)
        after = sum(row.get("image_output_bytes", 0) for row in rows if type(row.get("image_output_bytes")) is int)
        image_hashes = Counter(str(row.get("image_sha256")) for row in rows)
        actual = {"product_count": len(rows), "replacement_slots": len(slots), "source_counts": dict(sorted(Counter(str(row.get("source_name")) for row in rows).items())), "category_counts": {category: sum(row.get("category") == category for row in rows) for category in CATEGORIES}, "bytes_before": before, "bytes_after": after, "bytes_saved": before - after, "bytes_saved_percentage": (before - after) * 100 / before if before else 0.0, "webp_count": sum(str(row.get("image_url")).endswith(".webp") for row in rows), "retained_original_count": sum(not str(row.get("image_url")).endswith(".webp") for row in rows), "shared_image_references": sum(count - 1 for count in image_hashes.values())}
        for field, value in actual.items():
            if report.get(field) != value: errors.append("report image statistics mismatch" if field in {"bytes_before", "bytes_after", "bytes_saved", "bytes_saved_percentage", "webp_count", "retained_original_count", "shared_image_references"} else "report distribution mismatch")
        if report.get("input_count") != len(rows) + sum(rejected.values()): errors.append("report input-count mismatch")
        if any(type(report.get(field)) is not int or report[field] < 0 for field in ("duplicate_source_keys", "duplicate_content_hashes", "image_failures")): errors.append("report duplicate summary mismatch")
        if report.get("simulated_fields") != ["stock", "sales"]: errors.append("report simulated fields mismatch")
    except (OSError, json.JSONDecodeError, TypeError, KeyError, ValueError) as exc: errors.append(f"invalid report: {exc}")
    return VerificationResult(not errors, tuple(sorted(set(errors))), len(rows), len(slots))
