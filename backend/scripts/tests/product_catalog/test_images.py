from __future__ import annotations

import hashlib
import struct
import zlib
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from backend.scripts.product_catalog.images import (
    MAX_DOWNLOAD_BYTES,
    DownloadSettings,
    download_image,
    process_image,
    upload_image,
)

FIXTURES = Path(__file__).with_name("fixtures")


def _encoded(image: Image.Image, format: str, **options: object) -> bytes:
    output = BytesIO()
    image.save(output, format=format, **options)
    return output.getvalue()


def _png_with_dimensions(width: int, height: int) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IEND", b"")


def test_resizes_long_edge_without_upscaling_and_hashes_final_bytes() -> None:
    original = _encoded(Image.new("RGB", (1600, 800), "navy"), "JPEG", quality=95)

    first = process_image(original, "image/jpeg")
    second = process_image(original, "image/jpeg")

    assert first.width <= 1200
    assert first.height <= 600
    assert first.original_bytes == len(original)
    assert first.output_bytes == len(first.payload)
    assert first.sha256 == hashlib.sha256(first.payload).hexdigest()
    assert first.sha256 == second.sha256
    with Image.open(BytesIO(first.payload)) as decoded:
        assert decoded.size == (first.width, first.height)
        assert "exif" not in decoded.info

    small = process_image((FIXTURES / "opaque.png").read_bytes(), "image/png")
    assert (small.width, small.height) == (32, 24)


def test_preserves_alpha_and_uses_lossless_output() -> None:
    processed = process_image((FIXTURES / "transparent.png").read_bytes(), "image/png")

    with Image.open(BytesIO(processed.payload)) as decoded:
        rgba = decoded.convert("RGBA")
        assert rgba.getextrema()[3] == (0, 255)


def test_applies_exif_orientation_before_reporting_dimensions() -> None:
    image = Image.new("RGB", (80, 40), "red")
    exif = Image.Exif()
    exif[274] = 6
    original = _encoded(image, "JPEG", quality=90, exif=exif)

    processed = process_image(original, "image/jpeg")

    assert (processed.width, processed.height) == (40, 80)
    with Image.open(BytesIO(processed.payload)) as decoded:
        assert decoded.size == (40, 80)
        assert decoded.getexif().get(274) is None


@pytest.mark.parametrize(
    ("payload", "content_type"),
    [
        (b'<svg xmlns="http://www.w3.org/2000/svg"/>', "image/svg+xml"),
        (b'<svg xmlns="http://www.w3.org/2000/svg"/>', "image/png"),
    ],
)
def test_rejects_svg_by_declared_and_actual_content(payload: bytes, content_type: str) -> None:
    with pytest.raises(ValueError, match="supported JPEG, PNG, or WebP"):
        process_image(payload, content_type)


def test_rejects_decoded_images_over_forty_million_pixels_before_loading() -> None:
    oversized_header = _png_with_dimensions(8001, 5000)

    with pytest.raises(ValueError, match="40,000,000 pixels"):
        process_image(oversized_header, "image/png")


def test_retains_smaller_browser_safe_png_instead_of_larger_webp() -> None:
    checker = Image.new("RGB", (16, 16))
    for x in range(16):
        for y in range(16):
            checker.putpixel((x, y), (255 if (x + y) % 2 else 0, 0, 0))
    original = _encoded(checker, "PNG", optimize=True)

    processed = process_image(original, "image/png")

    assert processed.extension == "png"
    assert processed.mime_type == "image/png"
    assert processed.output_bytes <= len(original)


class FakeResponse:
    def __init__(self, chunks: list[bytes], *, content_type: str = "image/png", content_length: int | None = None, redirects: int = 0):
        self._chunks = chunks
        self.headers = {"Content-Type": content_type}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)
        self.history = [object()] * redirects
        self.url = "https://cdn.example.test/final.png"
        self.closed = False

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):
        assert chunk_size <= 64 * 1024
        yield from self._chunks

    def close(self) -> None:
        self.closed = True


class FakeSession:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.max_redirects = 99
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append((url, kwargs))
        return self.response


def test_download_streams_with_timeout_redirect_and_ten_mibibyte_caps() -> None:
    payload = (FIXTURES / "opaque.png").read_bytes()
    response = FakeResponse([payload], redirects=2)
    session = FakeSession(response)
    settings = DownloadSettings(timeout_seconds=4.5, max_redirects=2)

    downloaded = download_image("https://example.test/image.png", session, settings)

    assert downloaded.payload == payload
    assert downloaded.content_type == "image/png"
    assert downloaded.final_url == response.url
    assert session.calls == [("https://example.test/image.png", {"stream": True, "timeout": 4.5, "allow_redirects": True})]
    assert session.max_redirects == 99
    assert response.closed

    too_many_redirects = FakeResponse([payload], redirects=3)
    with pytest.raises(ValueError, match="redirect"):
        download_image("https://example.test/image.png", FakeSession(too_many_redirects), settings)

    oversized = FakeResponse([], content_length=MAX_DOWNLOAD_BYTES + 1)
    with pytest.raises(ValueError, match="10 MiB"):
        download_image("https://example.test/huge.png", FakeSession(oversized), settings)
    assert oversized.closed

    streamed_oversized = FakeResponse([b"x" * (MAX_DOWNLOAD_BYTES // 2), b"x" * (MAX_DOWNLOAD_BYTES // 2 + 1)])
    with pytest.raises(ValueError, match="10 MiB"):
        download_image("https://example.test/huge.png", FakeSession(streamed_oversized), settings)


class FakeMinio:
    def __init__(self, existing_size: int | None = None):
        self.existing_size = existing_size
        self.puts: list[tuple[str, str, bytes, int, str]] = []

    def stat_object(self, bucket: str, object_name: str) -> SimpleNamespace:
        if self.existing_size is None:
            error = RuntimeError("missing")
            error.code = "NoSuchKey"  # type: ignore[attr-defined]
            raise error
        return SimpleNamespace(size=self.existing_size)

    def put_object(self, bucket: str, object_name: str, data: BytesIO, length: int, content_type: str) -> None:
        self.puts.append((bucket, object_name, data.read(), length, content_type))


def test_upload_uses_content_addressed_catalog_path_and_is_idempotent() -> None:
    image = process_image((FIXTURES / "opaque.png").read_bytes(), "image/png")
    object_name = f"catalog/{image.sha256}.{image.extension}"

    client = FakeMinio()
    url = upload_image(image, client, "product-images")

    assert url == f"/api/v1/product-images/{object_name}"
    assert client.puts == [("product-images", object_name, image.payload, image.output_bytes, image.mime_type)]

    existing = FakeMinio(existing_size=image.output_bytes)
    assert upload_image(image, existing, "product-images") == url
    assert existing.puts == []
