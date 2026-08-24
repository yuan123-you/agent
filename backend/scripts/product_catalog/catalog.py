"""Deterministic emission and hard verification for the product catalog."""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal
import json
import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit
from .model import CATEGORIES, CatalogProduct

TARGET_COUNT, REPLACEMENT_COUNT = 2512, 512
MINIMUM_TIME = datetime(2025, 1, 1, tzinfo=timezone.utc)
_HASH = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
_MANIFEST, _JSON_REPORT, _MARKDOWN_REPORT = "products.jsonl", "catalog-report.json", "catalog-report.md"

@dataclass(frozen=True)
class CatalogReport:
    product_count: int; replacement_slots: int; source_counts: dict[str, int]; category_counts: dict[str, int]; rejection_counts: dict[str, int]; duplicate_source_keys: int; duplicate_content_hashes: int; image_failures: int; bytes_before: int; bytes_after: int; bytes_saved: int; bytes_saved_percentage: float; webp_count: int; retained_original_count: int; simulated_fields: list[str]
    def to_json(self) -> dict[str, Any]: return {name: getattr(self, name) for name in self.__dataclass_fields__}

@dataclass(frozen=True)
class VerificationResult:
    valid: bool; errors: tuple[str, ...]; product_count: int = 0; replacement_slots: int = 0
    @property
    def passed(self) -> bool: return self.valid

def _sort_key(product: CatalogProduct) -> tuple[str, str, str, str, str]:
    raw = product.raw
    return (raw.category or "", raw.brand or "", raw.name or "", raw.source_name or "", raw.source_product_id or "")

def _image_error(row: dict[str, Any]) -> str | None:
    url, original = row.get("image_url"), row.get("original_image_url")
    if not isinstance(url, str) or not url.startswith("/api/v1/product-images/catalog/") or "picsum" in url.casefold() or (isinstance(original, str) and "picsum" in urlsplit(original).netloc.casefold()): return "remote or Picsum image URL"
    return None

def _row_errors(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if error := _image_error(row): errors.append(error)
    if row.get("commerce_values_simulated") is not True: errors.append("commerce_values_simulated must be true")
    try:
        if Decimal(str(row.get("price"))) <= 0: errors.append("price must be positive")
    except Exception: errors.append("price must be positive")
    if row.get("category") not in CATEGORIES: errors.append("unsupported category")
    for field in ("name", "brand", "currency", "source_name", "source_url", "source_product_id"):
        if not isinstance(row.get(field), str) or not row[field].strip(): errors.append(f"missing {field}")
    for field, label in (("content_hash", "invalid content hash"), ("image_sha256", "invalid image hash")):
        if not isinstance(row.get(field), str) or not _HASH.fullmatch(row[field]): errors.append(label)
    if not isinstance(row.get("specs"), dict): errors.append("invalid specs")
    else:
        try: json.dumps(row["specs"], allow_nan=False)
        except (TypeError, ValueError): errors.append("invalid specs")
    times = []
    for value in (row.get("source_updated_at"), row.get("collected_at")):
        if value is None: continue
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is not None: times.append(parsed.astimezone(timezone.utc))
        except ValueError: pass
    if not times or max(times) < MINIMUM_TIME: errors.append("stale time")
    return errors

def _validated(items: Iterable[CatalogProduct]) -> tuple[list[CatalogProduct], Counter[str]]:
    valid: list[CatalogProduct] = []; rejected: Counter[str] = Counter(); source_keys: set[tuple[str, str]] = set(); hashes: set[str] = set()
    for item in items:
        row, errors = item.to_json(), _row_errors(item.to_json()); key = (str(row.get("source_name")), str(row.get("source_product_id")))
        if key in source_keys: errors.append("duplicate source key")
        if item.content_hash in hashes: errors.append("duplicate content hash")
        if errors: rejected.update(errors); continue
        source_keys.add(key); hashes.add(item.content_hash); valid.append(item)
    return valid, rejected

def select_catalog(items: Iterable[CatalogProduct], total: int = TARGET_COUNT, replacement_count: int = REPLACEMENT_COUNT) -> list[CatalogProduct]:
    """Select a stable, category-round-robin catalog without inventing records."""
    if type(total) is not int or total <= 0 or type(replacement_count) is not int or not 0 <= replacement_count <= total: raise ValueError("invalid catalog size or replacement count")
    valid, rejected = _validated(sorted(items, key=_sort_key))
    queues: dict[str, list[CatalogProduct]] = defaultdict(list)
    for item in valid: queues[item.raw.category or ""].append(item)
    selected: list[CatalogProduct] = []
    while len(selected) < total:
        progressed = False
        for category in CATEGORIES:
            if queues[category]:
                selected.append(queues[category].pop(0)); progressed = True
                if len(selected) == total: break
        if not progressed: raise ValueError(f"only {len(selected)} valid products available; need {total}")
    return [replace(item, replacement_slot=index if index <= replacement_count else None) for index, item in enumerate(selected, 1)]

def _report(products: list[CatalogProduct], rejected: Counter[str] | None = None) -> CatalogReport:
    rows = [product.to_json() for product in products]; categories = {category: sum(row["category"] == category for row in rows) for category in CATEGORIES}; sources = dict(sorted(Counter(str(row["source_name"]) for row in rows).items())); webp = sum(Path(str(row["image_url"])).suffix.casefold() == ".webp" for row in rows)
    return CatalogReport(len(rows), sum(row["replacement_slot"] is not None for row in rows), sources, categories, dict(sorted((rejected or Counter()).items())), 0, 0, 0, 0, 0, 0, 0.0, webp, len(rows) - webp, ["stock", "sales"])

def write_catalog(items: Iterable[CatalogProduct], output_dir: Path | str) -> CatalogReport:
    """Write stable JSONL plus deterministic JSON and Markdown audit reports."""
    records = list(items); _, rejected = _validated(sorted(records, key=_sort_key)); products = select_catalog(records); directory = Path(output_dir); directory.mkdir(parents=True, exist_ok=True); manifest = directory / _MANIFEST
    manifest.write_text("".join(json.dumps(product.to_json(), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n" for product in products), encoding="utf-8", newline="\n")
    report = _report(products, rejected)
    (directory / _JSON_REPORT).write_text(json.dumps(report.to_json(), ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    lines = ["# Catalog report", "", f"- Products: {report.product_count}", f"- Replacement slots: {report.replacement_slots}", f"- Simulated fields: {', '.join(report.simulated_fields)}", f"- Bytes before/after/saved: {report.bytes_before}/{report.bytes_after}/{report.bytes_saved} ({report.bytes_saved_percentage:.2f}%)", f"- WebP/retained original/image failures: {report.webp_count}/{report.retained_original_count}/{report.image_failures}", "", "## Sources", ""] + [f"- {name}: {count}" for name, count in report.source_counts.items()] + ["", "## Categories", ""] + [f"- {name}: {count}" for name, count in report.category_counts.items()] + ["", "## Rejections", ""] + [f"- {name}: {count}" for name, count in report.rejection_counts.items()]
    (directory / _MARKDOWN_REPORT).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return report

def verify_catalog(path: Path | str, report_path: Path | str) -> VerificationResult:
    """Hard-fail a manifest unless every catalog-wide invariant holds."""
    errors: list[str] = []
    try:
        raw = Path(path).read_bytes()
        if not raw.endswith(b"\n") or b"\r\n" in raw: errors.append("manifest must be UTF-8 JSONL with a final LF")
        rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc: return VerificationResult(False, (f"invalid manifest: {exc}",))
    source_keys: set[tuple[Any, Any]] = set(); hashes: set[Any] = set(); slots: list[Any] = []
    for row in rows:
        if not isinstance(row, dict): errors.append("invalid JSON row"); continue
        errors.extend(_row_errors(row)); key = (row.get("source_name"), row.get("source_product_id"))
        if key in source_keys: errors.append("duplicate source key")
        source_keys.add(key)
        if row.get("content_hash") in hashes: errors.append("duplicate content hash")
        hashes.add(row.get("content_hash"))
        if row.get("replacement_slot") is not None: slots.append(row["replacement_slot"])
    if len(rows) != TARGET_COUNT: errors.append(f"expected {TARGET_COUNT} products")
    if sorted(slots) != list(range(1, REPLACEMENT_COUNT + 1)): errors.append(f"expected replacement slots 1-{REPLACEMENT_COUNT}")
    try:
        report = json.loads(Path(report_path).read_text(encoding="utf-8"))
        required = set(CatalogReport.__dataclass_fields__)
        if not required.issubset(report): errors.append("incomplete report statistics")
        if report.get("product_count") != len(rows) or report.get("replacement_slots") != len(slots): errors.append("report count mismatch")
        if report.get("simulated_fields") != ["stock", "sales"]: errors.append("report simulated fields mismatch")
        sources = dict(sorted(Counter(str(row.get("source_name")) for row in rows).items()))
        categories = {category: sum(row.get("category") == category for row in rows) for category in CATEGORIES}
        if report.get("source_counts") != sources or report.get("category_counts") != categories: errors.append("report distribution mismatch")
        if any(report.get(field) != 0 for field in ("duplicate_source_keys", "duplicate_content_hashes", "image_failures")): errors.append("report hard-error count mismatch")
    except (OSError, json.JSONDecodeError) as exc: errors.append(f"invalid report: {exc}")
    return VerificationResult(not errors, tuple(sorted(set(errors))), len(rows), len(slots))
