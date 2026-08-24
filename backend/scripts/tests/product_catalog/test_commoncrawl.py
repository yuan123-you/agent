import gzip
import io
from datetime import datetime, timezone
from pathlib import Path

import pytest
from warcio.warcwriter import WARCWriter

from backend.scripts.product_catalog.commoncrawl import CrawlRecord, MAX_INDEX_RESPONSE_BYTES, discover_records, fetch_warc_html
from backend.scripts.product_catalog.model import SourceConfig


class FakeResponse:
    def __init__(self, lines=(), content=b"", headers=None):
        self._lines = lines
        self._content = content
        self.headers = headers or {}
        self.status_code = 200
        self.encoding = "utf-8"

    def raise_for_status(self):
        assert self.status_code == 200

    def iter_lines(self, decode_unicode=False):
        yield from self._lines

    def iter_content(self, chunk_size=8192):
        for offset in range(0, len(self._content), chunk_size):
            yield self._content[offset : offset + chunk_size]

    @property
    def content(self):
        return self._content


def source_config(limit=1):
    return SourceConfig(
        common_crawl_index="CC-MAIN-2025-30",
        minimum_source_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        rate_limit_per_second=2,
        max_candidates_per_source=limit,
        allowed_domains=("example.com",),
        blocked_domains=(),
    )


def test_discover_records_caches_index_response_and_limits_candidates(monkeypatch, tmp_path: Path):
    lines = [
        '{"url":"https://www.example.com/a","filename":"crawl-data/CC-MAIN-2025-30/segments/a.warc.gz","offset":"10","length":"20","timestamp":"20250701123456"}',
        '{"url":"https://www.example.com/b","filename":"crawl-data/CC-MAIN-2025-30/segments/b.warc.gz","offset":"30","length":"40","timestamp":"20250701123457"}',
    ]
    calls = []

    def fake_get(url, *, params, timeout, stream):
        calls.append((url, params, timeout, stream))
        return FakeResponse(lines=lines)

    monkeypatch.setattr("backend.scripts.product_catalog.commoncrawl.requests.get", fake_get)

    records = list(discover_records(source_config(), tmp_path))
    cached_records = list(discover_records(source_config(), tmp_path))

    assert len(calls) == 1
    assert calls[0][0] == "https://index.commoncrawl.org/CC-MAIN-2025-30-index"
    assert calls[0][1] == [
        ("url", "*.example.com/*"),
        ("output", "json"),
        ("filter", "status:200"),
        ("filter", "mime:text/html"),
        ("collapse", "urlkey"),
    ]
    assert records == cached_records
    assert len(records) == 1
    assert records[0].url == "https://www.example.com/a"
    assert records[0].collected_at == datetime(2025, 7, 1, 12, 34, 56, tzinfo=timezone.utc)
    assert len(list(tmp_path.glob("*.jsonl"))) == 1


def test_discover_records_rejects_index_responses_over_cap(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "backend.scripts.product_catalog.commoncrawl.requests.get",
        lambda *_, **__: FakeResponse(headers={"Content-Length": str(MAX_INDEX_RESPONSE_BYTES + 1)}),
    )

    with pytest.raises(ValueError, match="response cap"):
        list(discover_records(source_config(), tmp_path))


def test_fetch_warc_html_uses_declared_byte_range_and_decodes_one_record():
    payload = io.BytesIO()
    writer = WARCWriter(payload, gzip=True)
    writer.write_record(writer.create_warc_record("https://www.example.com/a", "response", payload=io.BytesIO(
        b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n<html><body>Product</body></html>"
    )))
    warc_bytes = payload.getvalue()
    calls = []

    class Session:
        def get(self, url, *, headers, timeout, stream):
            calls.append((url, headers, timeout, stream))
            return FakeResponse(content=warc_bytes, headers={"Content-Length": str(len(warc_bytes))})

    record = CrawlRecord(
        url="https://www.example.com/a",
        filename="crawl-data/CC-MAIN-2025-30/segments/a.warc.gz",
        offset=10,
        length=len(warc_bytes),
        collected_at=datetime(2025, 7, 1, tzinfo=timezone.utc),
        rate_limit_per_second=2,
    )

    assert fetch_warc_html(record, Session()) == "<html><body>Product</body></html>"
    assert calls == [(
        "https://data.commoncrawl.org/crawl-data/CC-MAIN-2025-30/segments/a.warc.gz",
        {"Range": f"bytes=10-{10 + len(warc_bytes) - 1}"},
        30,
        True,
    )]