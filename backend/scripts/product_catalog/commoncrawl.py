"""Bounded Common Crawl index discovery and WARC record retrieval."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Iterator

import requests
from warcio.archiveiterator import ArchiveIterator

from .model import SourceConfig

INDEX_TIMEOUT_SECONDS = 30
WARC_TIMEOUT_SECONDS = 30
MAX_INDEX_RESPONSE_BYTES = 5 * 1024 * 1024
DATA_BASE_URL = "https://data.commoncrawl.org/"
INDEX_BASE_URL = "https://index.commoncrawl.org/"


@dataclass(frozen=True)
class CrawlRecord:
    """The exact byte range of one Common Crawl response record."""

    url: str
    filename: str
    offset: int
    length: int
    collected_at: datetime
    rate_limit_per_second: int

    def __post_init__(self) -> None:
        if self.offset < 0 or self.length <= 0:
            raise ValueError("WARC offset and length must be positive")
        if self.collected_at.tzinfo is None or self.collected_at.utcoffset() is None:
            raise ValueError("collected_at must be timezone-aware")
        if self.rate_limit_per_second <= 0:
            raise ValueError("rate_limit_per_second must be positive")


_last_request_at: dict[int, float] = {}


def _wait_for_rate_limit(rate_limit_per_second: int) -> None:
    interval = 1 / rate_limit_per_second
    now = time.monotonic()
    previous = _last_request_at.get(rate_limit_per_second)
    if previous is not None:
        remaining = interval - (now - previous)
        if remaining > 0:
            time.sleep(remaining)
    _last_request_at[rate_limit_per_second] = time.monotonic()


def _cache_path(cache_dir: Path, index: str, domain: str) -> Path:
    request = json.dumps(
        {
            "index": index,
            "url": f"*.{domain}/*",
            "output": "json",
            "filters": ["status:200", "mime:text/html"],
            "collapse": "urlkey",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return cache_dir / f"{hashlib.sha256(request).hexdigest()}.jsonl"


def _read_index_lines(response: requests.Response) -> list[str]:
    length = response.headers.get("Content-Length")
    if length is not None and int(length) > MAX_INDEX_RESPONSE_BYTES:
        raise ValueError("Common Crawl index response exceeds response cap")

    lines: list[str] = []
    size = 0
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue
        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="replace")
        size += len(line.encode("utf-8")) + 1
        if size > MAX_INDEX_RESPONSE_BYTES:
            raise ValueError("Common Crawl index response exceeds response cap")
        lines.append(line)
    return lines


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Common Crawl record timestamp is missing")
    return datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


def _records_from_lines(lines: list[str], rate_limit_per_second: int) -> Iterator[CrawlRecord]:
    for line in lines:
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            yield CrawlRecord(
                url=str(row["url"]),
                filename=str(row["filename"]),
                offset=int(row["offset"]),
                length=int(row["length"]),
                collected_at=_parse_timestamp(row["timestamp"]),
                rate_limit_per_second=rate_limit_per_second,
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue


def discover_records(source: SourceConfig, cache_dir: Path) -> Iterator[CrawlRecord]:
    """Discover bounded, cached HTML candidate ranges for each permitted domain."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    blocked = set(source.blocked_domains)
    for domain in source.allowed_domains:
        if domain in blocked:
            continue
        path = _cache_path(cache_dir, source.common_crawl_index, domain)
        if path.exists():
            lines = path.read_text(encoding="utf-8").splitlines()
        else:
            _wait_for_rate_limit(source.rate_limit_per_second)
            response = requests.get(
                f"{INDEX_BASE_URL}{source.common_crawl_index}-index",
                params=[
                    ("url", f"*.{domain}/*"),
                    ("output", "json"),
                    ("filter", "status:200"),
                    ("filter", "mime:text/html"),
                    ("collapse", "urlkey"),
                ],
                timeout=INDEX_TIMEOUT_SECONDS,
                stream=True,
            )
            response.raise_for_status()
            lines = _read_index_lines(response)
            path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

        yielded = 0
        for record in _records_from_lines(lines, source.rate_limit_per_second):
            yield record
            yielded += 1
            if yielded >= source.max_candidates_per_source:
                break


def _range_bytes(response: object, limit: int) -> bytes:
    headers = getattr(response, "headers")
    content_length = headers.get("Content-Length")
    if content_length is not None and int(content_length) > limit:
        raise ValueError("WARC response exceeds declared record length")

    payload = bytearray()
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        payload.extend(chunk)
        if len(payload) > limit:
            raise ValueError("WARC response exceeds declared record length")
    return bytes(payload)


def fetch_warc_html(record: CrawlRecord, session: requests.Session) -> str:
    """Fetch and decode only ``record``'s declared WARC byte range."""
    if record.filename.startswith("/") or ".." in Path(record.filename).parts:
        raise ValueError("invalid Common Crawl filename")
    _wait_for_rate_limit(record.rate_limit_per_second)
    end = record.offset + record.length - 1
    response = session.get(
        f"{DATA_BASE_URL}{record.filename}",
        headers={"Range": f"bytes={record.offset}-{end}"},
        timeout=WARC_TIMEOUT_SECONDS,
        stream=True,
    )
    response.raise_for_status()
    payload = _range_bytes(response, record.length)
    for warc_record in ArchiveIterator(BytesIO(payload)):
        if warc_record.rec_type != "response":
            continue
        content_type = warc_record.http_headers.get_header("Content-Type") or ""
        if "html" not in content_type.lower():
            continue
        return warc_record.content_stream().read().decode("utf-8", errors="replace")
    raise ValueError("no HTML response found in declared WARC record")