"""Strict parser for the catalog source policy."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .model import SourceConfig

_REQUIRED_KEYS = frozenset({
    "common_crawl_index",
    "minimum_source_time",
    "rate_limit_per_second",
    "max_candidates_per_source",
    "allowed_domains",
    "blocked_domains",
})


def _parse_utc_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 timestamp string")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return timestamp.astimezone(timezone.utc)


def _parse_domains(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(domain, str) and domain for domain in value):
        raise ValueError(f"{field} must be a list of domain strings")
    return tuple(value)


def load_source_config(path: Path) -> SourceConfig:
    """Load a source policy and reject malformed or unrecognized configuration."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not load source config: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("source config must be a JSON object")

    actual_keys = set(payload)
    missing = _REQUIRED_KEYS - actual_keys
    unknown = actual_keys - _REQUIRED_KEYS
    if missing:
        raise ValueError(f"missing required keys: {', '.join(sorted(missing))}")
    if unknown:
        raise ValueError(f"unknown keys: {', '.join(sorted(unknown))}")

    common_crawl_index = payload["common_crawl_index"]
    if not isinstance(common_crawl_index, str) or not common_crawl_index:
        raise ValueError("common_crawl_index must be a non-empty string")

    rate_limit = payload["rate_limit_per_second"]
    candidate_limit = payload["max_candidates_per_source"]
    if type(rate_limit) is not int or rate_limit <= 0:
        raise ValueError("rate_limit_per_second must be a positive integer")
    if type(candidate_limit) is not int or candidate_limit <= 0:
        raise ValueError("max_candidates_per_source must be a positive integer")

    return SourceConfig(
        common_crawl_index=common_crawl_index,
        minimum_source_time=_parse_utc_timestamp(payload["minimum_source_time"], "minimum_source_time"),
        rate_limit_per_second=rate_limit,
        max_candidates_per_source=candidate_limit,
        allowed_domains=_parse_domains(payload["allowed_domains"], "allowed_domains"),
        blocked_domains=_parse_domains(payload["blocked_domains"], "blocked_domains"),
    )
