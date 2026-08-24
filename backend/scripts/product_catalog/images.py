"""Safe decoding, normalization, downloading, and storage of catalog images."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from typing import Any
from urllib.parse import urljoin, urlsplit

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024
MAX_DECODED_PIXELS = 40_000_000
MAX_EDGE = 1200
_CHUNK_BYTES = 64 * 1024
_FORMATS = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
}
_ALLOWED_CONTENT_TYPES = frozenset(mime for _, mime in _FORMATS.values())
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


@dataclass(frozen=True)
class DownloadSettings:
    """Network limits used while retrieving one untrusted image."""

    timeout_seconds: float = 10.0
    max_redirects: int = 3
    max_bytes: int = MAX_DOWNLOAD_BYTES

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if type(self.max_redirects) is not int or self.max_redirects < 0:
            raise ValueError("max_redirects must be a non-negative integer")
        if type(self.max_bytes) is not int or not 0 < self.max_bytes <= MAX_DOWNLOAD_BYTES:
            raise ValueError("max_bytes must be between 1 byte and 10 MiB")


@dataclass(frozen=True)
class DownloadedImage:
    payload: bytes
    content_type: str
    final_url: str

    @property
    def data(self) -> bytes:
        return self.payload

    @property
    def byte_count(self) -> int:
        return len(self.payload)


@dataclass(frozen=True)
class ProcessedImage:
    sha256: str
    extension: str
    mime_type: str
    width: int
    height: int
    original_bytes: int
    output_bytes: int
    payload: bytes

    @property
    def hash(self) -> str:
        return self.sha256

    @property
    def original_byte_count(self) -> int:
        return self.original_bytes

    @property
    def output_byte_count(self) -> int:
        return self.output_bytes


def _normalized_content_type(content_type: str) -> str:
    if not isinstance(content_type, str):
        return ""
    return content_type.partition(";")[0].strip().lower()


def _save(image: Image.Image, format: str) -> bytes:
    output = BytesIO()
    if format == "WEBP":
        if "A" in image.getbands():
            image.save(output, "WEBP", lossless=True, method=6)
        else:
            image.save(output, "WEBP", quality=82, method=6)
    elif format == "PNG":
        image.save(output, "PNG", optimize=True)
    else:
        image.save(output, "JPEG", quality=82, optimize=True)
    return output.getvalue()


def process_image(data: bytes, content_type: str) -> ProcessedImage:
    """Decode and normalize untrusted JPEG/PNG/WebP bytes within fixed resource caps."""
    if _normalized_content_type(content_type) not in _ALLOWED_CONTENT_TYPES:
        raise ValueError("image must be a supported JPEG, PNG, or WebP")
    if not isinstance(data, bytes) or not data:
        raise ValueError("image must contain a decodable supported JPEG, PNG, or WebP")

    try:
        with Image.open(BytesIO(data)) as source:
            format = source.format
            if format not in _FORMATS:
                raise ValueError("image must be a supported JPEG, PNG, or WebP")
            width, height = source.size
            if width <= 0 or height <= 0 or width * height > MAX_DECODED_PIXELS:
                raise ValueError("decoded image must not exceed 40,000,000 pixels")
            if getattr(source, "is_animated", False) or getattr(source, "n_frames", 1) > 1:
                raise ValueError("animated images are not supported")

            orientation = source.getexif().get(274, 1)
            source.load()
            transposed = ImageOps.exif_transpose(source)
            has_alpha = "A" in transposed.getbands() or "transparency" in source.info
            normalized = transposed.convert("RGBA" if has_alpha else "RGB")
            normalized.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)

            webp = _save(normalized, "WEBP")
            extension, mime_type = _FORMATS["WEBP"]
            payload = webp

            if format in ("JPEG", "PNG"):
                safe_original_format = _save(normalized, format)
                if len(safe_original_format) <= len(webp):
                    payload = safe_original_format
                    extension, mime_type = _FORMATS[format]

            output_hash = sha256(payload).hexdigest()
            width, height = normalized.size
    except ValueError:
        raise
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValueError("image must contain a decodable supported JPEG, PNG, or WebP") from exc

    return ProcessedImage(
        sha256=output_hash,
        extension=extension,
        mime_type=mime_type,
        width=width,
        height=height,
        original_bytes=len(data),
        output_bytes=len(payload),
        payload=payload,
    )


def _http_url(url: str) -> bool:
    parsed = urlsplit(url)
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.hostname)


def download_image(url: str, session: Any, settings: DownloadSettings) -> DownloadedImage:
    """Stream one image through a caller-provided HTTP session with local redirect limits."""
    current_url = url
    for redirects_followed in range(settings.max_redirects + 1):
        if not _http_url(current_url):
            raise ValueError("image URL must use HTTP or HTTPS")

        response = session.get(
            current_url,
            stream=True,
            timeout=settings.timeout_seconds,
            allow_redirects=False,
        )
        try:
            if getattr(response, "status_code", 200) in _REDIRECT_STATUSES:
                location = response.headers.get("Location")
                if not location:
                    raise ValueError("image redirect is missing Location")
                if redirects_followed >= settings.max_redirects:
                    raise ValueError("image download exceeded redirect limit")
                next_url = urljoin(getattr(response, "url", current_url), location)
                if not _http_url(next_url):
                    raise ValueError("image redirect must use HTTP or HTTPS")
                current_url = next_url
                continue

            response.raise_for_status()
            content_length = response.headers.get("Content-Length")
            if content_length is not None:
                try:
                    announced_bytes = int(content_length)
                except (TypeError, ValueError) as exc:
                    raise ValueError("image response has an invalid Content-Length") from exc
                if announced_bytes < 0 or announced_bytes > settings.max_bytes:
                    raise ValueError("image response exceeds 10 MiB")

            payload = bytearray()
            for chunk in response.iter_content(chunk_size=_CHUNK_BYTES):
                if not chunk:
                    continue
                if len(chunk) > settings.max_bytes - len(payload):
                    raise ValueError("image response exceeds 10 MiB")
                payload.extend(chunk)

            return DownloadedImage(
                payload=bytes(payload),
                content_type=_normalized_content_type(response.headers.get("Content-Type", "")),
                final_url=getattr(response, "url", current_url),
            )
        finally:
            response.close()

    raise AssertionError("redirect loop must return or raise")


def _stored_sha256(metadata: Any) -> str | None:
    if not isinstance(metadata, Mapping):
        return None
    for key, value in metadata.items():
        if str(key).lower() in {"sha256", "x-amz-meta-sha256"}:
            return str(value)
    return None


def upload_image(image: ProcessedImage, client: Any, bucket: str) -> str:
    """Idempotently upload final bytes under their SHA-256-derived object name."""
    object_name = f"catalog/{image.sha256}.{image.extension}"
    try:
        existing = client.stat_object(bucket, object_name)
    except Exception as exc:
        if getattr(exc, "code", None) not in {"NoSuchKey", "NoSuchObject"}:
            raise
    else:
        metadata = getattr(existing, "metadata", {})
        content_type = getattr(existing, "content_type", None)
        if content_type is None and isinstance(metadata, Mapping):
            content_type = metadata.get("content-type") or metadata.get("Content-Type")
        if (
            existing.size == image.output_bytes
            and content_type == image.mime_type
            and _stored_sha256(metadata) == image.sha256
        ):
            return f"/api/v1/product-images/{object_name}"

    client.put_object(
        bucket,
        object_name,
        BytesIO(image.payload),
        image.output_bytes,
        content_type=image.mime_type,
        metadata={"sha256": image.sha256},
    )
    return f"/api/v1/product-images/{object_name}"
