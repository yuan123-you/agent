# Task 4 Report — Safe Image Processing and MinIO Storage

## Status
Complete.

## Files
- `backend/scripts/product_catalog/images.py`
- `backend/scripts/tests/product_catalog/test_images.py`
- `backend/scripts/tests/product_catalog/fixtures/opaque.png`
- `backend/scripts/tests/product_catalog/fixtures/transparent.png`

## Commit
`feat: compress and store catalog images`

## RED-GREEN
- **RED:** `python -m pytest backend/scripts/tests/product_catalog/test_images.py -q` failed during collection with `ModuleNotFoundError: No module named 'backend.scripts.product_catalog.images'`.
- **GREEN:** focused image suite passed with `9 passed` and pristine output.
- **REGRESSION:** full product-catalog suite passed with `62 passed` and pristine output.

## Boundary Coverage
- Downloads are streamed with a timeout, a caller-selected redirect cap, and a hard 10 MiB ceiling enforced from both `Content-Length` and accumulated chunks; responses are always closed.
- Only declared JPEG/PNG/WebP media types proceed to Pillow, and the actual decoded format must independently be JPEG, PNG, or WebP.
- The 40,000,000-pixel cap is checked from decoded dimensions before pixel loading, EXIF orientation, conversion, thumbnailing, or encoding.
- EXIF orientation is applied; longest edge is limited to 1200 pixels with Lanczos and images are never upscaled.
- Opaque images use WebP quality 82/method 6; alpha images use lossless WebP/method 6. Metadata-bearing or transformed originals are re-encoded without metadata. A safe unchanged JPEG/PNG is retained only when no larger than WebP.
- SHA-256 is calculated from final stored bytes. MinIO keys are `catalog/{sha256}.{ext}` in the supplied `product-images` bucket, with the public path `/api/v1/product-images/catalog/{sha256}.{ext}`; `stat_object` skips an existing same-sized content-addressed object.
- Tests use in-memory HTTP and MinIO fakes only; no real network or object store is contacted.

## Self-review
- Confirmed the route path and lowercase `jpg|png|webp` extension contract matches Task 8 and remains valid under `CatalogProduct.image_url`.
- Confirmed no credential values are accepted, emitted, or logged by this module.
- Confirmed changes are limited to Task 4 implementation, tests, fixtures, and this report.

## Concerns
- Idempotent existence checks rely on the SHA-256 object name plus stored byte length; an externally corrupted object with the same key and length is outside this pipeline's normal write model and would require object retrieval to detect.

## Fix Round 1 — RED-GREEN
- This section supersedes the initial raw-retention, same-size MinIO skip, and related concern statements above.
- **RED:** `python -m pytest backend/scripts/tests/product_catalog/test_images.py -q` produced the expected boundary failures (`15 failed, 9 passed`): JPEG canonical retention, animated PNG/WebP rejection, request-local redirects, pre-allocation byte enforcement, and MinIO metadata identity were not implemented.
- **RED (real metadata mapping):** after the first green pass, a regression using immutable mapping metadata failed (`1 failed, 23 passed`), proving MinIO's mapping-compatible metadata container was not recognized by a `dict`-only check.
- **GREEN:** focused image suite passed with `24 passed` and pristine output.
- **REGRESSION:** full product-catalog suite passed with `77 passed` and pristine output.

### Fixes
- JPEG and PNG candidates are now always canonically re-encoded; no source bytes, trailing data, EXIF, text chunks, or unknown ancillary bytes are copied into stored payloads. The safe same-format candidate is compared with WebP, including deterministic JPEG retention when smaller.
- Animated PNG and WebP inputs are rejected before frame loading or transforms.
- Redirects use `allow_redirects=False`, are resolved one hop at a time, and never mutate shared session redirect state. The configured hop limit is checked before another request; every response is closed, and missing or non-HTTP(S) targets are rejected.
- Streamed chunks are checked against remaining capacity before `bytearray.extend`, so the accumulation buffer never crosses the configured maximum.
- Existing MinIO objects are skipped only when size, content type, and SHA-256 metadata all match. Uploads include `sha256` user metadata; missing or mismatched identity fields cause overwrite without downloading the object.
- The object key and public path contracts remain `catalog/{sha256}.{jpg|png|webp}` and `/api/v1/product-images/catalog/{sha256}.{jpg|png|webp}`.

### Concerns
- None identified for this fix round.
