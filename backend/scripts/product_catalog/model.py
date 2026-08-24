"""Immutable records exchanged by product catalog pipeline stages."""
from __future__ import annotations

import json
import re
from hashlib import sha256
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

CATEGORIES = (
    "PHONE", "DIGITAL", "COMPUTER", "APPLIANCE", "HOME_DECOR", "FURNITURE",
    "CLOTHING", "SHOES", "BAGS", "BEAUTY", "PERSONAL_CARE", "FOOD", "FRESH",
    "MATERNAL", "TOYS", "SPORTS", "BOOK", "CAR", "PET", "HEALTH", "JEWELRY",
)
_HASH = re.compile(r"^[0-9a-fA-F]{64}$")


def _utc_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_nonblank(value: str | None, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonblank")


@dataclass(frozen=True)
class ImageCandidate:
    """An image URL discovered at the source, before it is downloaded."""

    original_url: str
    alt_text: str | None = None
    mime_type: str | None = None


@dataclass(frozen=True)
class RawProduct:
    """Extraction-stage facts, which may be incomplete until Task 3 validation."""

    name: str | None
    brand: str | None
    category: str | None
    price: Decimal | None
    currency: str | None
    description: str | None
    selling_points: tuple[str, ...]
    specs: Mapping[str, Any]
    source_name: str | None
    source_url: str | None
    source_product_id: str | None
    source_updated_at: datetime | None
    collected_at: datetime
    image_candidates: tuple[ImageCandidate, ...]
    origin: str | None = None
    material: str | None = None
    production_date: str | None = None

    def __post_init__(self) -> None:
        _utc_timestamp(self.collected_at)
        if self.source_updated_at is not None:
            _utc_timestamp(self.source_updated_at)


@dataclass(frozen=True)
class CatalogProductCandidate:
    """A normalized candidate retained for Task 3 quality validation."""

    raw: RawProduct
    stock: int | None = None
    sales: int | None = None
    simulated_commerce_fields: bool = True

    @property
    def unique_key(self) -> str:
        """Stable source identity used for duplicate and demo-value derivation."""
        return f"{self.raw.source_name}\x1f{self.raw.source_product_id}"

    @property
    def seed(self) -> int:
        return int(sha256(self.unique_key.encode("utf-8")).hexdigest()[:8], 16)


@dataclass(frozen=True)
class CatalogProduct:
    """A validated catalog entry ready to be emitted as a JSONL manifest row."""

    raw: RawProduct
    stock: int
    sales: int
    image_url: str
    image_sha256: str
    content_hash: str
    catalog_version: str
    commerce_values_simulated: bool = True

    def __post_init__(self) -> None:
        raw = self.raw
        for field in ("name", "brand", "currency", "source_name", "source_url", "source_product_id"):
            _require_nonblank(getattr(raw, field), field)
        if raw.category not in CATEGORIES:
            raise ValueError(f"unsupported category: {raw.category}")
        if not isinstance(raw.price, Decimal) or raw.price <= 0:
            raise ValueError("price must be positive")
        if not isinstance(raw.specs, Mapping):
            raise ValueError("specs must be a JSON object")
        try:
            json.dumps(raw.specs, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("specs must be JSON-serializable") from exc
        if not isinstance(self.image_url, str) or not self.image_url.startswith("/") or self.image_url.startswith("//") or ".." in self.image_url:
            raise ValueError("image_url must be a local catalog path")
        for field in ("image_sha256", "content_hash"):
            if not isinstance(getattr(self, field), str) or not _HASH.fullmatch(getattr(self, field)):
                raise ValueError(f"{field} must be a 64-character hexadecimal hash")
        if self.commerce_values_simulated is not True:
            raise ValueError("commerce_values_simulated must be true")

    def to_json(self) -> dict[str, Any]:
        """Return a JSON-compatible, auditable manifest representation."""
        raw = self.raw
        return {
            "name": raw.name,
            "brand": raw.brand,
            "category": raw.category,
            "price": str(raw.price),
            "currency": raw.currency,
            "stock": self.stock,
            "sales": self.sales,
            "commerce_values_simulated": self.commerce_values_simulated,
            "description": raw.description,
            "selling_points": list(raw.selling_points),
            "specs": dict(raw.specs),
            "origin": raw.origin,
            "material": raw.material,
            "production_date": raw.production_date,
            "source_name": raw.source_name,
            "source_url": raw.source_url,
            "source_product_id": raw.source_product_id,
            "source_updated_at": (
                _utc_timestamp(raw.source_updated_at) if raw.source_updated_at is not None else None
            ),
            "collected_at": _utc_timestamp(raw.collected_at),
            "original_image_url": (
                raw.image_candidates[0].original_url if raw.image_candidates else None
            ),
            "image_url": self.image_url,
            "image_sha256": self.image_sha256,
            "content_hash": self.content_hash,
            "catalog_version": self.catalog_version,
        }


@dataclass(frozen=True)
class SourceConfig:
    """Validated source policy shared by candidate collectors."""

    common_crawl_index: str
    minimum_source_time: datetime
    rate_limit_per_second: int
    max_candidates_per_source: int
    allowed_domains: tuple[str, ...]
    blocked_domains: tuple[str, ...]

    @property
    def minimum_collected_at(self) -> datetime:
        """Compatibility name for the source-recency cutoff enforced by Task 3."""
        return self.minimum_source_time
