"""Contracts and configuration for the real-product catalog pipeline."""

from .config import load_source_config
from .model import CatalogProduct, ImageCandidate, RawProduct, SourceConfig

__all__ = [
    "CatalogProduct",
    "ImageCandidate",
    "RawProduct",
    "SourceConfig",
    "load_source_config",
]
