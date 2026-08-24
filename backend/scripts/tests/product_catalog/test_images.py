from __future__ import annotations

import hashlib
import random
import struct
import zlib
from io import BytesIO
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest
from PIL import Image, PngImagePlugin

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


def test_canonically_reencodes_png_and_jpeg_without_metadata_or_trailing_bytes() -> None:
    trailing = b"UNTRUSTED-TRAILING-BYTES"

    checker = Image.new("RGB", (16, 16))
    for x in range(16):
        for y in range(16):
            checker.putpixel((x, y), (255 if (x + y) % 2 else 0, 0, 0))
    png_info = PngImagePlugin.PngInfo()
    png_info.add_text("Comment", "remove me")
    png = _encoded(checker, "PNG", optimize=True, pnginfo=png_info) + trailing
    processed_png = process_image(png, "image/png")
    assert not processed_png.payload.endswith(trailing)
    with Image.open(BytesIO(processed_png.payload)) as decoded_png:
        assert "Comment" not in decoded_png.info

    metadata_free_png = _encoded(checker, "PNG", optimize=True) + trailing
    safe_metadata_free_png = process_image(metadata_free_png, "image/png")
    assert safe_metadata_free_png.payload != metadata_free_png
    assert not safe_metadata_free_png.payload.endswith(trailing)

    exif = Image.Exif()
    exif[270] = "remove me"
    jpeg = _encoded(Image.new("RGB", (32, 32), "blue"), "JPEG", exif=exif) + trailing
    processed_jpeg = process_image(jpeg, "image/jpeg")
    assert not processed_jpeg.payload.endswith(trailing)
    with Image.open(BytesIO(processed_jpeg.payload)) as decoded_jpeg:
        assert not decoded_jpeg.getexif()


def test_retains_smaller_canonically_encoded_jpeg_format() -> None:
    randomizer = random.Random(1)
    noisy = Image.new("RGB", (64, 64))
    noisy.putdata([
        tuple(randomizer.randrange(256) for _ in range(3))
        for _ in range(64 * 64)
    ])
    original = _encoded(noisy, "JPEG", quality=95) + b"discard me"

    processed = process_image(original, "image/jpeg")

    assert processed.extension == "jpg"
    assert processed.mime_type == "image/jpeg"
    assert processed.payload != original
    assert b"discard me" not in processed.payload


@pytest.mark.parametrize(("format", "content_type"), [("PNG", "image/png"), ("WEBP", "image/webp")])
def test_rejects_animated_png_and_webp(format: str, content_type: str) -> None:
    first = Image.new("RGBA", (8, 8), "red")
    second = Image.new("RGBA", (8, 8), "blue")
    animated = _encoded(first, format, save_all=True, append_images=[second], duration=100, loop=0)

    with pytest.raises(ValueError, match="animated"):
        process_image(animated, content_type)


class FakeResponse:
    def __init__(
        self,
        chunks: list[object],
        *,
        status_code: int = 200,
        content_type: str = "image/png",
        content_length: int | None = None,
        location: str | None = None,
        url: str = "https://cdn.example.test/final.png",
    ):
        self._chunks = chunks
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)
        if location is not None:
            self.headers["Location"] = location
        self.url = url
        self.closed = False

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size: int):
        assert chunk_size <= 64 * 1024
        yield from self._chunks

    def close(self) -> None:
        self.closed = True


class FakeSession:
    def __init__(self, responses: FakeResponse | list[FakeResponse]):
        self.responses = responses if isinstance(responses, list) else [responses]
        self.max_redirects = 99
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        assert self.max_redirects == 99
        self.calls.append((url, kwargs))
        return self.responses[len(self.calls) - 1]


def test_download_follows_redirects_request_locally_and_closes_every_response() -> None:
    payload = (FIXTURES / "opaque.png").read_bytes()
    first = FakeResponse([], status_code=302, location="/second.png", url="https://example.test/start.png")
    second = FakeResponse([], status_code=307, location="https://cdn.example.test/final.png", url="https://example.test/second.png")
    final = FakeResponse([payload])
    session = FakeSession([first, second, final])
    settings = DownloadSettings(timeout_seconds=4.5, max_redirects=2)

    downloaded = download_image("https://example.test/start.png", session, settings)

    request_options = {"stream": True, "timeout": 4.5, "allow_redirects": False}
    assert session.calls == [
        ("https://example.test/start.png", request_options),
        ("https://example.test/second.png", request_options),
        ("https://cdn.example.test/final.png", request_options),
    ]
    assert downloaded.payload == payload
    assert downloaded.final_url == final.url
    assert first.closed and second.closed and final.closed


def test_download_enforces_redirect_limit_before_next_request() -> None:
    first = FakeResponse([], status_code=302, location="/second.png", url="https://example.test/start.png")
    second = FakeResponse([], status_code=302, location="/third.png", url="https://example.test/second.png")
    session = FakeSession([first, second])

    with pytest.raises(ValueError, match="redirect"):
        download_image("https://example.test/start.png", session, DownloadSettings(max_redirects=1))

    assert len(session.calls) == 2
    assert first.closed and second.closed


@pytest.mark.parametrize("location", [None, "ftp://example.test/image.png", "javascript:alert(1)"])
def test_download_rejects_missing_or_non_http_redirect_locations(location: str | None) -> None:
    response = FakeResponse([], status_code=302, location=location, url="https://example.test/start.png")

    with pytest.raises(ValueError, match="redirect"):
        download_image("https://example.test/start.png", FakeSession(response), DownloadSettings())

    assert response.closed


class ExplodingOversizedChunk:
    def __len__(self) -> int:
        return MAX_DOWNLOAD_BYTES + 1

    def __iter__(self):
        raise AssertionError("oversized chunk must not be copied")


def test_download_checks_byte_cap_before_extending_buffer() -> None:
    response = FakeResponse([ExplodingOversizedChunk()])

    with pytest.raises(ValueError, match="10 MiB"):
        download_image("https://example.test/huge.png", FakeSession(response), DownloadSettings())

    assert response.closed


def test_download_rejects_announced_and_streamed_responses_over_ten_mibibytes() -> None:
    oversized = FakeResponse([], content_length=MAX_DOWNLOAD_BYTES + 1)
    with pytest.raises(ValueError, match="10 MiB"):
        download_image("https://example.test/huge.png", FakeSession(oversized), DownloadSettings())
    assert oversized.closed

    streamed = FakeResponse([b"x" * (MAX_DOWNLOAD_BYTES // 2), b"x" * (MAX_DOWNLOAD_BYTES // 2 + 1)])
    with pytest.raises(ValueError, match="10 MiB"):
        download_image("https://example.test/huge.png", FakeSession(streamed), DownloadSettings())
    assert streamed.closed


class FakeMinio:
    def __init__(
        self,
        *,
        existing_size: int | None = None,
        existing_content_type: str | None = None,
        existing_metadata: dict[str, str] | None = None,
    ):
        self.existing_size = existing_size
        self.existing_content_type = existing_content_type
        self.existing_metadata = existing_metadata or {}
        self.puts: list[tuple[str, str, bytes, int, str, dict[str, str]]] = []

    def stat_object(self, bucket: str, object_name: str) -> SimpleNamespace:
        if self.existing_size is None:
            error = RuntimeError("missing")
            error.code = "NoSuchKey"  # type: ignore[attr-defined]
            raise error
        return SimpleNamespace(
            size=self.existing_size,
            content_type=self.existing_content_type,
            metadata=self.existing_metadata,
        )

    def put_object(
        self,
        bucket: str,
        object_name: str,
        data: BytesIO,
        length: int,
        content_type: str,
        metadata: dict[str, str],
    ) -> None:
        self.puts.append((bucket, object_name, data.read(), length, content_type, metadata))


def test_upload_uses_content_addressed_catalog_path_and_sha_metadata() -> None:
    image = process_image((FIXTURES / "opaque.png").read_bytes(), "image/png")
    object_name = f"catalog/{image.sha256}.{image.extension}"
    client = FakeMinio()

    url = upload_image(image, client, "product-images")

    assert url == f"/api/v1/product-images/{object_name}"
    assert client.puts == [(
        "product-images",
        object_name,
        image.payload,
        image.output_bytes,
        image.mime_type,
        {"sha256": image.sha256},
    )]


def test_upload_skips_only_when_size_content_type_and_sha_metadata_match() -> None:
    image = process_image((FIXTURES / "opaque.png").read_bytes(), "image/png")
    matching = FakeMinio(
        existing_size=image.output_bytes,
        existing_content_type=image.mime_type,
        existing_metadata=MappingProxyType({"X-Amz-Meta-Sha256": image.sha256}),
    )

    upload_image(image, matching, "product-images")

    assert matching.puts == []


@pytest.mark.parametrize(
    ("size_delta", "content_type", "metadata"),
    [
        (1, "MATCH", {"sha256": "MATCH"}),
        (0, "image/wrong", {"sha256": "MATCH"}),
        (0, "MATCH", {}),
        (0, "MATCH", {"sha256": "0" * 64}),
    ],
)
def test_upload_overwrites_when_any_existing_identity_field_mismatches(
    size_delta: int,
    content_type: str,
    metadata: dict[str, str],
) -> None:
    image = process_image((FIXTURES / "opaque.png").read_bytes(), "image/png")
    resolved_type = image.mime_type if content_type == "MATCH" else content_type
    resolved_metadata = {
        key: image.sha256 if value == "MATCH" else value
        for key, value in metadata.items()
    }
    client = FakeMinio(
        existing_size=image.output_bytes + size_delta,
        existing_content_type=resolved_type,
        existing_metadata=resolved_metadata,
    )

    upload_image(image, client, "product-images")

    assert len(client.puts) == 1
