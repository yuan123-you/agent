"""Immutable records exchanged by product catalog pipeline stages."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

CATEGORIES = (
    "PHONE", "DIGITAL", "COMPUTER", "APPLIANCE", "HOME_DECOR", "FURNITURE",
    "CLOTHING", "SHOES", "BAGS", "BEAUTY", "PERSONAL_CARE", "FOOD", "FRESH",
    "MATERNAL", "TOYS", "SPORTS", "BOOK", "CAR", "PET", "HEALTH", "JEWELRY",
)


def _utc_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ImageCandidate:
    """An image URL discovered at the source, before it is downloaded."""

    original_url: str
    alt_text: str | None = None
    mime_type: str | None = None


@dataclass(frozen=True)
class RawProduct:
    """Facts found at a public source before image processing and import."""

    name: str
    brand: str
    category: str
    price: Decimal
    currency: str
    description: str
    selling_points: tuple[str, ...]
    specs: Mapping[str, Any]
    source_name: str
    source_url: str
    source_product_id: str
    source_updated_at: datetime | None
    collected_at: datetime
    image_candidates: tuple[ImageCandidate, ...]
    origin: str | None = None
    material: str | None = None
    production_date: str | None = None

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError(f"unsupported category: {self.category}")
        if self.price <= 0:
            raise ValueError("price must be positive")
        _utc_timestamp(self.collected_at)
        if self.source_updated_at is not None:
            _utc_timestamp(self.source_updated_at)


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
