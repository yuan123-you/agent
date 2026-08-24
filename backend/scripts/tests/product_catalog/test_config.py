import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.scripts.product_catalog.config import load_source_config


def test_load_source_config_reads_the_pinned_catalog_policy(tmp_path: Path):
    config_path = tmp_path / "sources.json"
    config_path.write_text(
        json.dumps(
            {
                "common_crawl_index": "CC-MAIN-2025-30",
                "minimum_source_time": "2025-01-01T00:00:00Z",
                "rate_limit_per_second": 1,
                "max_candidates_per_source": 100,
                "allowed_domains": ["apple.com", "samsung.com"],
                "blocked_domains": ["blocked.example"],
            }
        ),
        encoding="utf-8",
    )

    config = load_source_config(config_path)

    assert config.common_crawl_index == "CC-MAIN-2025-30"
    assert config.minimum_source_time == datetime(2025, 1, 1, tzinfo=timezone.utc)
    assert config.rate_limit_per_second == 1
    assert config.max_candidates_per_source == 100
    assert config.allowed_domains == ("apple.com", "samsung.com")
    assert config.blocked_domains == ("blocked.example",)


def test_load_source_config_rejects_unknown_or_invalid_values(tmp_path: Path):
    config_path = tmp_path / "sources.json"
    config_path.write_text('{"common_crawl_index": "CC-MAIN-2025-30"}', encoding="utf-8")

    with pytest.raises(ValueError, match="missing required keys"):
        load_source_config(config_path)


def test_load_source_config_allows_an_empty_blocked_domain_list(tmp_path: Path):
    config_path = tmp_path / "sources.json"
    config_path.write_text(
        json.dumps(
            {
                "common_crawl_index": "CC-MAIN-2025-30",
                "minimum_source_time": "2025-01-01T00:00:00Z",
                "rate_limit_per_second": 1,
                "max_candidates_per_source": 100,
                "allowed_domains": ["apple.com"],
                "blocked_domains": [],
            }
        ),
        encoding="utf-8",
    )

    assert load_source_config(config_path).blocked_domains == ()
