"""Safe decoding, normalization, downloading, and storage of catalog images."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from typing import Any

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
        image.save(output, "JPEG", quality=95, optimize=True)
    return output.getvalue()


def _can_retain_input(image: Image.Image, format: str, orientation: int, resized: bool) -> bool:
    if resized or orientation not in (None, 1):
        return False
    metadata = set(image.info)
    if format == "JPEG":
        metadata -= {"jfif", "jfif_version", "jfif_unit", "jfif_density"}
    return not metadata


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

            orientation = source.getexif().get(274, 1)
            source.load()
            transposed = ImageOps.exif_transpose(source)
            has_alpha = "A" in transposed.getbands() or "transparency" in source.info
            normalized = transposed.convert("RGBA" if has_alpha else "RGB")
            before_size = normalized.size
            normalized.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
            resized = normalized.size != before_size

            webp = _save(normalized, "WEBP")
            extension, mime_type = _FORMATS["WEBP"]
            payload = webp

            if format in ("JPEG", "PNG"):
                if _can_retain_input(source, format, orientation, resized):
                    original_format = data
                else:
                    original_format = _save(normalized, format)
                if len(original_format) <= len(webp):
                    payload = original_format
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


def download_image(url: str, session: Any, settings: DownloadSettings) -> DownloadedImage:
    """Stream one image through a caller-provided HTTP session without real I/O in tests."""
    previous_redirect_limit = getattr(session, "max_redirects", None)
    has_redirect_limit = hasattr(session, "max_redirects")
    if has_redirect_limit:
        session.max_redirects = settings.max_redirects
    try:
        response = session.get(
            url,
            stream=True,
            timeout=settings.timeout_seconds,
            allow_redirects=True,
        )
    finally:
        if has_redirect_limit:
            session.max_redirects = previous_redirect_limit

    try:
        response.raise_for_status()
        if len(getattr(response, "history", ())) > settings.max_redirects:
            raise ValueError("image download exceeded redirect limit")

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
            payload.extend(chunk)
            if len(payload) > settings.max_bytes:
                raise ValueError("image response exceeds 10 MiB")

        return DownloadedImage(
            payload=bytes(payload),
            content_type=_normalized_content_type(response.headers.get("Content-Type", "")),
            final_url=getattr(response, "url", url),
        )
    finally:
        response.close()


def upload_image(image: ProcessedImage, client: Any, bucket: str) -> str:
    """Idempotently upload final bytes under their SHA-256-derived object name."""
    object_name = f"catalog/{image.sha256}.{image.extension}"
    try:
        existing = client.stat_object(bucket, object_name)
    except Exception as exc:
        if getattr(exc, "code", None) not in {"NoSuchKey", "NoSuchObject"}:
            raise
    else:
        if existing.size == image.output_bytes:
            return f"/api/v1/product-images/{object_name}"

    client.put_object(
        bucket,
        object_name,
        BytesIO(image.payload),
        image.output_bytes,
        content_type=image.mime_type,
    )
    return f"/api/v1/product-images/{object_name}"
