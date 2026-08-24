"""Bounded Common Crawl index discovery and WARC record retrieval."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
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
INDEX_MAX_RETRIES = 4
INDEX_RETRY_BACKOFF_SECONDS = 2
MAX_INDEX_RESPONSE_BYTES = 20 * 1024 * 1024
MAX_HTML_BYTES = 5 * 1024 * 1024
DATA_BASE_URL = "https://data.commoncrawl.org/"
INDEX_BASE_URL = "https://index.commoncrawl.org/"
_CONTENT_RANGE = re.compile(r"^bytes (\d+)-(\d+)/(\d+|\*)$", re.IGNORECASE)
_CACHE_COMPLETE_MARKER = "# commoncrawl-cache-complete"


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
    try:
        if length is not None and int(length) > MAX_INDEX_RESPONSE_BYTES:
            raise ValueError("Common Crawl index response exceeds response cap")
    except ValueError as exc:
        if "response cap" in str(exc):
            raise
        raise ValueError("invalid Common Crawl index Content-Length") from exc

    lines: list[str] = []
    size = 0
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue
        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="strict")
        size += len(line.encode("utf-8")) + 1
        if size > MAX_INDEX_RESPONSE_BYTES:
            raise ValueError("Common Crawl index response exceeds response cap")
        lines.append(line)
    return lines


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Common Crawl record timestamp is missing")
    return datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


def _record_from_line(line: str, rate_limit_per_second: int) -> CrawlRecord:
    row = json.loads(line)
    if not isinstance(row, dict):
        raise ValueError("Common Crawl index row must be an object")
    return CrawlRecord(
        url=str(row["url"]),
        filename=str(row["filename"]),
        offset=int(row["offset"]),
        length=int(row["length"]),
        collected_at=_parse_timestamp(row["timestamp"]),
        rate_limit_per_second=rate_limit_per_second,
    )


def _records_from_lines(lines: list[str], rate_limit_per_second: int) -> Iterator[CrawlRecord]:
    for line in lines:
        yield _record_from_line(line, rate_limit_per_second)


def _read_cache(path: Path, rate_limit_per_second: int) -> list[str]:
    maximum_cache_bytes = MAX_INDEX_RESPONSE_BYTES + len(_CACHE_COMPLETE_MARKER.encode("utf-8")) + 1
    with path.open("rb") as cache_file:
        payload = cache_file.read(maximum_cache_bytes + 1)
    if len(payload) > maximum_cache_bytes:
        raise ValueError("cached Common Crawl index exceeds response cap")
    if not payload.endswith((_CACHE_COMPLETE_MARKER + "\n").encode("utf-8")):
        raise ValueError("cached Common Crawl index is truncated")
    try:
        lines = payload.decode("utf-8").splitlines()
        if lines.pop() != _CACHE_COMPLETE_MARKER:
            raise ValueError("cached Common Crawl index is incomplete")
        list(_records_from_lines(lines, rate_limit_per_second))
    except (UnicodeDecodeError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("cached Common Crawl index is corrupt") from exc
    return lines


def _write_cache(path: Path, lines: list[str]) -> None:
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as temporary:
            temporary_name = temporary.name
            temporary.write(("\n".join(lines) + "\n" if lines else "") + _CACHE_COMPLETE_MARKER + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _fetch_index_lines(source: SourceConfig, domain: str) -> list[str]:
    _wait_for_rate_limit(source.rate_limit_per_second)
    url = f"{INDEX_BASE_URL}{source.common_crawl_index}-index"
    params = [
        ("url", f"*.{domain}/*"),
        ("output", "json"),
        ("filter", "status:200"),
        ("filter", "mime:text/html"),
        ("collapse", "urlkey"),
    ]
    last_error: requests.RequestException | None = None
    for attempt in range(INDEX_MAX_RETRIES):
        try:
            response = requests.get(url, params=params, timeout=INDEX_TIMEOUT_SECONDS, stream=True)
            response.raise_for_status()
            lines = _read_index_lines(response)
            list(_records_from_lines(lines, source.rate_limit_per_second))
            return lines
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status is not None and 400 <= status < 500 and status != 429:
                raise
            last_error = exc
        except requests.RequestException as exc:
            last_error = exc
        if attempt + 1 < INDEX_MAX_RETRIES:
            time.sleep(INDEX_RETRY_BACKOFF_SECONDS * (2**attempt))
    if last_error is not None:
        raise last_error
    raise RuntimeError("unreachable")


def discover_records(source: SourceConfig, cache_dir: Path) -> Iterator[CrawlRecord]:
    """Discover bounded, cached HTML candidate ranges for each permitted domain."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    blocked = set(source.blocked_domains)
    for domain in source.allowed_domains:
        if domain in blocked:
            continue
        path = _cache_path(cache_dir, source.common_crawl_index, domain)
        try:
            lines = _read_cache(path, source.rate_limit_per_second) if path.exists() else None
        except (OSError, ValueError):
            path.unlink(missing_ok=True)
            lines = None
        if lines is None:
            try:
                lines = _fetch_index_lines(source, domain)
                _write_cache(path, lines)
            except (ValueError, requests.RequestException) as exc:
                # 单个来源失效（索引超限、损坏或重试耗尽）不终止候选采集
                path.unlink(missing_ok=True)
                print(f"discover: skipping {domain}: {exc}", file=sys.stderr)
                continue

        for count, record in enumerate(_records_from_lines(lines, source.rate_limit_per_second), start=1):
            yield record
            if count >= source.max_candidates_per_source:
                break


def _range_bytes(response: object, limit: int) -> bytes:
    headers = getattr(response, "headers")
    content_length = headers.get("Content-Length")
    try:
        if content_length is not None and int(content_length) > limit:
            raise ValueError("WARC response exceeds declared record length")
    except ValueError as exc:
        if "declared record length" in str(exc):
            raise
        raise ValueError("invalid WARC Content-Length") from exc

    payload = bytearray()
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        payload.extend(chunk)
        if len(payload) > limit:
            raise ValueError("WARC response exceeds declared record length")
    return bytes(payload)


def _validate_content_range(response: requests.Response, start: int, end: int) -> None:
    if response.status_code != 206:
        raise ValueError("WARC range request must return HTTP 206")
    match = _CONTENT_RANGE.fullmatch(response.headers.get("Content-Range", ""))
    if match is None or (int(match.group(1)), int(match.group(2))) != (start, end):
        raise ValueError("WARC Content-Range does not match requested range")
    total = match.group(3)
    if total != "*" and int(total) <= end:
        raise ValueError("WARC Content-Range total does not contain requested range")


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
    _validate_content_range(response, record.offset, end)
    response.raise_for_status()
    payload = _range_bytes(response, record.length)
    for warc_record in ArchiveIterator(BytesIO(payload)):
        if warc_record.rec_type != "response":
            continue
        content_type = warc_record.http_headers.get_header("Content-Type") or ""
        if "html" not in content_type.lower():
            continue
        html = warc_record.content_stream().read(MAX_HTML_BYTES + 1)
        if len(html) > MAX_HTML_BYTES:
            raise ValueError("HTML response exceeds decompressed payload limit")
        return html.decode("utf-8", errors="replace")
    raise ValueError("no HTML response found in declared WARC record")