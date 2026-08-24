"""Contracts and configuration for the real-product catalog pipeline."""

from .config import load_source_config
from .model import CatalogProduct, CatalogProductCandidate, ImageCandidate, RawProduct, SourceConfig

__all__ = [
    "CatalogProduct",
    "CatalogProductCandidate",
    "ImageCandidate",
    "RawProduct",
    "SourceConfig",
    "load_source_config",
]
