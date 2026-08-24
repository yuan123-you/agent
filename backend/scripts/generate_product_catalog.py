"""Safe, auditable, repeatable CLI for the real-product catalog pipeline.

Commands: ``discover``, ``build``, ``upload-images``, ``import``, ``verify``,
``all``.  The tool refuses unsafe operations: ``build`` without a discovery
cache, ``import`` without ``--apply`` or an unverified manifest, and never
reads credentials outside the ``MYSQL_*``/``MINIO_*`` allowlist.  Log output
redacts secret values.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from backend.scripts.product_catalog import catalog, commoncrawl, images, jsonld, normalize
    from backend.scripts.product_catalog.config import load_source_config
    from backend.scripts.product_catalog.importer import import_catalog, verify_database
    from backend.scripts.product_catalog.model import CatalogProduct, CatalogProductCandidate, ImageCandidate, RawProduct
except ModuleNotFoundError:  # pragma: no cover - plain-script fallback
    from product_catalog import catalog, commoncrawl, images, jsonld, normalize
    from product_catalog.config import load_source_config
    from product_catalog.importer import import_catalog, verify_database
    from product_catalog.model import CatalogProduct, CatalogProductCandidate, ImageCandidate, RawProduct

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # backend/
CACHE_ROOT = PROJECT_ROOT / ".catalog-cache"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "src/main/resources/product-catalog"
DEFAULT_CONFIG = PROJECT_ROOT / "scripts" / "product_sources.json"
DEFAULT_CATALOG_VERSION = "catalog-2026-08-24"
_CREDENTIAL_PREFIXES = ("MYSQL_", "MINIO_")


def _credentials(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return only allowlisted ``MYSQL_*``/``MINIO_*`` credential variables."""
    environment = os.environ if env is None else env
    return {
        key: value for key, value in environment.items()
        if key.startswith(_CREDENTIAL_PREFIXES)
    }


def redact(message: str, secrets: Mapping[str, str] | None = None) -> str:
    """Mask every known secret value so logs never leak credentials."""
    for value in (_credentials() if secrets is None else secrets).values():
        if value:
            message = message.replace(value, "***")
    return message


def _log(message: str) -> None:
    print(redact(message))


def _error(message: str) -> None:
    print(redact(f"error: {message}"), file=sys.stderr)


def _cache_paths(cache_root: Path) -> tuple[Path, Path, Path, Path, Path]:
    index = cache_root / "index"
    warc = cache_root / "warc"
    images_dir = cache_root / "images"
    return index, warc, images_dir, warc / "raw-products.jsonl", warc / "candidates.jsonl"


def _stamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_stamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _raw_json(raw: RawProduct) -> dict[str, Any]:
    return {
        "name": raw.name,
        "brand": raw.brand,
        "category": raw.category,
        "price": str(raw.price) if raw.price is not None else None,
        "currency": raw.currency,
        "description": raw.description,
        "selling_points": list(raw.selling_points),
        "specs": dict(raw.specs),
        "source_name": raw.source_name,
        "source_url": raw.source_url,
        "source_product_id": raw.source_product_id,
        "source_updated_at": _stamp(raw.source_updated_at),
        "collected_at": _stamp(raw.collected_at),
        "image_candidates": [
            {"original_url": image.original_url, "alt_text": image.alt_text, "mime_type": image.mime_type}
            for image in raw.image_candidates
        ],
        "origin": raw.origin,
        "material": raw.material,
        "production_date": raw.production_date,
    }


def _parse_raw(payload: Mapping[str, Any]) -> RawProduct:
    return RawProduct(
        name=payload.get("name"),
        brand=payload.get("brand"),
        category=payload.get("category"),
        price=Decimal(payload["price"]) if payload.get("price") is not None else None,
        currency=payload.get("currency"),
        description=payload.get("description"),
        selling_points=tuple(payload.get("selling_points") or ()),
        specs=payload.get("specs") or {},
        source_name=payload.get("source_name"),
        source_url=payload.get("source_url"),
        source_product_id=payload.get("source_product_id"),
        source_updated_at=_parse_stamp(payload.get("source_updated_at")),
        collected_at=_parse_stamp(payload.get("collected_at")),
        image_candidates=tuple(
            ImageCandidate(image.get("original_url"), image.get("alt_text"), image.get("mime_type"))
            for image in payload.get("image_candidates") or ()
        ),
        origin=payload.get("origin"),
        material=payload.get("material"),
        production_date=payload.get("production_date"),
    )


def _jsonl(rows: Iterable[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
        for row in rows
    )


def _load_raw_products(path: Path) -> list[RawProduct]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [_parse_raw(row) for row in rows]


def _load_built_candidates(path: Path) -> list[CatalogProductCandidate]:
    candidates: list[CatalogProductCandidate] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        candidates.append(CatalogProductCandidate(
            raw=_parse_raw(payload["raw"]),
            stock=payload["stock"],
            sales=payload["sales"],
        ))
    return candidates


def _load_manifest_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _http_session() -> Any:
    import requests
    return requests.Session()


def _mysql_connection(credentials: Mapping[str, str]) -> Any:
    import pymysql
    return pymysql.connect(
        host=credentials.get("MYSQL_HOST", "127.0.0.1"),
        port=int(credentials.get("MYSQL_PORT", "3306")),
        user=credentials.get("MYSQL_USER"),
        password=credentials.get("MYSQL_PASSWORD", ""),
        database=credentials.get("MYSQL_DATABASE"),
        charset="utf8mb4",
        autocommit=False,
    )


def _minio_client(credentials: Mapping[str, str]) -> Any:
    from minio import Minio
    return Minio(
        credentials.get("MINIO_ENDPOINT", "127.0.0.1:9000"),
        access_key=credentials.get("MINIO_ACCESS_KEY"),
        secret_key=credentials.get("MINIO_SECRET_KEY"),
        secure=str(credentials.get("MINIO_USE_SSL", "false")).lower() in {"1", "true", "yes"},
    )


def _domain(url: str) -> str:
    from urllib.parse import urlsplit
    return urlsplit(url).hostname or "source"


# 结构化的商品页 URL 模式：命中任意一条即视为候选商品页。
# 依据 Common Crawl 缓存索引实测：adidas/{region}/{lang}/{slug}/{SKU}.html、
# apple/shop/product/{SKU}、petsmart -{5-8位}.html、target /p/、samsung 分类路径。
_PRODUCT_URL_PATTERNS = (
    re.compile(r"/shop/product/"),
    re.compile(r"/shop/buy-"),
    re.compile(r"/p/"),
    re.compile(r"\.p$"),
    re.compile(r"/product"),
    re.compile(r"/products/"),
    re.compile(r"-\d{5,8}\.html$"),
    re.compile(r"/[^/]+/[A-Z0-9]{5,10}\.html$"),
    re.compile(r"/(smartphones|business|tv|appliances|monitors|audio|wearables|tablets|watches|wearable)/"),
    re.compile(r"/item/"),
    re.compile(r"/ip/"),
    re.compile(r"/pd/"),
)


def _is_product_page_url(url: str) -> bool:
    """True when ``url`` looks like a structured product page worth fetching."""
    from urllib.parse import urlparse
    path = urlparse(url).path
    return any(pattern.search(path) for pattern in _PRODUCT_URL_PATTERNS)


# Apple 商店商品页 URL 形如 /shop/product/{SKU}/slug/...；SKU 跨地区一致。
_APPLE_PRODUCT_SKU = re.compile(r"/shop/product/([A-Z0-9]+(?:/[A-Z0-9]+)?)/", re.IGNORECASE)


def _is_apple_url(url: str) -> bool:
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").casefold()
    return host == "apple.com" or host.endswith(".apple.com")


def collect_raw_products(config: Any, cache_dir: Path, session: Any) -> list[RawProduct]:
    """Discover cached WARC pages and extract raw JSON-LD products per domain."""
    collected: list[RawProduct] = []
    checked = 0
    fetched = 0
    next_progress = 0
    # Apple 商店同一 SKU 会跨地区重复出现；抓取前按 URL 中的 SKU 预去重，
    # 与 build 阶段的 (source_name, source_product_id) 去重结果一致。
    seen_apple_skus: set[str] = set()
    for record in commoncrawl.discover_records(config, cache_dir):
        checked += 1
        if not _is_product_page_url(record.url):
            continue
        if _is_apple_url(record.url):
            match = _APPLE_PRODUCT_SKU.search(record.url)
            if match:
                sku = match.group(1)
                if sku in seen_apple_skus:
                    continue
                seen_apple_skus.add(sku)
        try:
            html = commoncrawl.fetch_warc_html(record, session)
            fetched += 1
        except Exception:
            continue
        try:
            raw = jsonld.extract_products(html, record.url, record.collected_at, _domain(record.url))
        except Exception:
            continue
        collected.extend(raw)
        if fetched >= next_progress:
            next_progress = fetched + 500
            print(
                f"discover: fetched={fetched} products={len(collected)} "
                f"domain={_domain(record.url)} url={record.url[:100]}",
                file=sys.stderr,
            )
    return collected


def cmd_discover(args: argparse.Namespace) -> int:
    config = load_source_config(Path(args.config))
    index, warc, images_dir, raw, _ = _cache_paths(Path(args.cache_root))
    for directory in (index, warc, images_dir):
        directory.mkdir(parents=True, exist_ok=True)
    session = _http_session()
    try:
        products = collect_raw_products(config, index, session)
    finally:
        session.close()
    raw.write_text(_jsonl([_raw_json(product) for product in products]), encoding="utf-8", newline="\n")
    sources: dict[str, int] = {}
    for product in products:
        sources[product.source_name or "unknown"] = sources.get(product.source_name or "unknown", 0) + 1
    _log(f"discover: candidates={len(products)}")
    for source, count in sorted(sources.items()):
        _log(f"discover:   {source}: {count}")
    if len(products) < args.minimum_candidates:
        _error(f"discover: only {len(products)} candidates; need at least {args.minimum_candidates}")
        return 1
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    _, _, _, raw, built = _cache_paths(Path(args.cache_root))
    if not raw.exists():
        _error("no cached candidates; run 'discover' first")
        return 1
    raws = _load_raw_products(raw)
    candidates: list[CatalogProductCandidate] = []
    for raw_product in raws:
        try:
            candidate = normalize.normalize(raw_product, None)
            if normalize.validation_errors(candidate, catalog.MINIMUM_TIME):
                continue
            candidates.append(candidate)
        except Exception:
            continue
    candidates = normalize.deduplicate(candidates)
    if len(candidates) < args.target:
        _error(f"build: only {len(candidates)} valid candidates; need at least {args.target}")
        return 1
    payload = _jsonl({
        "raw": _raw_json(candidate.raw),
        "stock": candidate.stock,
        "sales": candidate.sales,
    } for candidate in candidates)
    built.write_text(payload, encoding="utf-8", newline="\n")
    _log(f"build: raw={len(raws)} valid={len(candidates)}")
    return 0


def _build_product(candidate: CatalogProductCandidate, processed: Any, url: str, version: str) -> CatalogProduct:
    raw = candidate.raw
    row = {
        "name": raw.name,
        "brand": raw.brand,
        "category": raw.category,
        "price": str(raw.price),
        "currency": raw.currency,
        "stock": candidate.stock,
        "sales": candidate.sales,
        "commerce_values_simulated": True,
        "description": raw.description,
        "selling_points": list(raw.selling_points),
        "specs": dict(raw.specs),
        "origin": raw.origin,
        "material": raw.material,
        "production_date": raw.production_date,
        "source_name": raw.source_name,
        "source_url": raw.source_url,
        "source_product_id": raw.source_product_id,
        "source_updated_at": _stamp(raw.source_updated_at),
        "collected_at": _stamp(raw.collected_at),
        "original_image_url": raw.image_candidates[0].original_url if raw.image_candidates else None,
        "image_url": url,
        "image_sha256": processed.sha256,
        "catalog_version": version,
        "image_original_bytes": processed.original_bytes,
        "image_output_bytes": processed.output_bytes,
    }
    content_hash = hashlib.sha256(
        json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    return CatalogProduct(
        raw=raw,
        stock=candidate.stock,
        sales=candidate.sales,
        image_url=url,
        image_sha256=processed.sha256,
        content_hash=content_hash,
        catalog_version=version,
        image_original_bytes=processed.original_bytes,
        image_output_bytes=processed.output_bytes,
    )


def _process_candidate(candidate: CatalogProductCandidate, session: Any, client: Any, bucket: str, version: str) -> CatalogProduct:
    raw = candidate.raw
    if not raw.image_candidates:
        raise ValueError("no image candidates")
    last_error: Exception | None = None
    for image in raw.image_candidates:
        try:
            downloaded = images.download_image(image.original_url, session, images.DownloadSettings())
            processed = images.process_image(downloaded.payload, downloaded.content_type)
            url = images.upload_image(processed, client, bucket)
            return _build_product(candidate, processed, url, version)
        except Exception as exc:
            last_error = exc
    raise ValueError(f"all image candidates failed: {last_error}")


def cmd_upload_images(args: argparse.Namespace) -> int:
    _, _, images_dir, _, built = _cache_paths(Path(args.cache_root))
    if not built.exists():
        _error("no built candidates; run 'build' first")
        return 1
    images_dir.mkdir(parents=True, exist_ok=True)
    candidates = _load_built_candidates(built)
    credentials = _credentials()
    client = _minio_client(credentials)
    bucket = args.bucket or credentials.get("MINIO_BUCKET", "aimall")
    session = _http_session()
    products: list[CatalogProduct] = []
    try:
        for candidate in candidates:
            if len(products) >= args.target:
                break
            try:
                products.append(_process_candidate(candidate, session, client, bucket, args.catalog_version))
            except Exception as exc:
                _log(f"upload-images: skipped {candidate.raw.source_name}/{candidate.raw.source_product_id}: {exc}")
    finally:
        session.close()
    if len(products) < args.target:
        _error(f"upload-images: only {len(products)} products with images; need {args.target}")
        return 1
    report = catalog.write_catalog(products, Path(args.output))
    _log(f"upload-images: wrote {args.output} with {report.product_count} products")
    return 0


def _verify_minio_missing(manifest: Path, client: Any, bucket: str) -> int:
    missing = 0
    for row in _load_manifest_rows(manifest):
        name = str(row["image_url"]).rsplit("/", 1)[-1]
        try:
            client.stat_object(bucket, f"catalog/{name}")
        except Exception:
            missing += 1
    return missing


def cmd_verify(args: argparse.Namespace) -> int:
    manifest = Path(args.manifest)
    report = Path(args.report)
    result = catalog.verify_catalog(manifest, report)
    errors = 0
    if not result.passed:
        _error(f"verify: manifest failed: {'; '.join(result.errors)}")
        errors += 1
    if args.database:
        connection = _mysql_connection(_credentials())
        try:
            database = verify_database(connection)
        finally:
            connection.close()
        if not database.valid:
            _error(f"verify: database failed: {database}")
            errors += 1
        _log(f"verify: database products={database.product_count} source_keys={database.source_key_count}")
    if args.minio:
        credentials = _credentials()
        client = _minio_client(credentials)
        bucket = args.bucket or credentials.get("MINIO_BUCKET", "aimall")
        missing = _verify_minio_missing(manifest, client, bucket)
        if missing:
            _error(f"verify: {missing} image objects missing from MinIO")
            errors += 1
    if errors:
        return 1
    _log(f"verify: PASS products={result.product_count} replacement_slots={result.replacement_slots}")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    if not args.apply:
        _error("refusing to import without --apply")
        return 1
    manifest = Path(args.manifest)
    report = Path(args.report)
    result = catalog.verify_catalog(manifest, report)
    if not result.passed:
        _error(f"refusing to import unverified manifest: {'; '.join(result.errors)}")
        return 1
    products = _load_manifest_rows(manifest)
    connection = _mysql_connection(_credentials())
    try:
        imported = import_catalog(
            connection,
            products,
            dry_run=args.dry_run,
            refresh_existing_catalog=args.refresh_existing_catalog,
        )
    finally:
        connection.close()
    state = "DRY RUN" if imported.dry_run else "APPLIED"
    _log(f"import: {state} updated={imported.updated} inserted={imported.inserted} "
         f"deleted_reviews={imported.deleted_reviews} final={imported.final_count}")
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    for step in (cmd_discover, cmd_build, cmd_upload_images, cmd_verify):
        code = step(args)
        if code:
            return code
    if not args.apply:
        _log("all: dry run complete; add --apply to import the catalog")
        return 0
    return cmd_import(args)


def _add_shared_options(target: argparse.ArgumentParser, *, suppress_default: bool = False) -> None:
    """Register cache/output options; subparsers use SUPPRESS so an option given
    before the subcommand is never overwritten by the subparser default."""
    default = argparse.SUPPRESS if suppress_default else str(CACHE_ROOT)
    target.add_argument("--cache-root", default=default,
                        help="working cache directory (default: backend/.catalog-cache)")
    default = argparse.SUPPRESS if suppress_default else str(DEFAULT_OUTPUT_DIR)
    target.add_argument("--output", default=default,
                        help="directory for committed catalog outputs (JSONL + reports)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate_product_catalog",
        description="Discover, build, verify, and import the real-product catalog.",
    )
    _add_shared_options(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    p_discover = sub.add_parser("discover", help="discover and cache candidate products from Common Crawl")
    _add_shared_options(p_discover, suppress_default=True)
    p_discover.add_argument("--config", default=str(DEFAULT_CONFIG))
    p_discover.add_argument("--minimum-candidates", type=int, default=4000)

    p_build = sub.add_parser("build", help="normalize, validate, and deduplicate cached candidates")
    _add_shared_options(p_build, suppress_default=True)
    p_build.add_argument("--target", type=int, default=catalog.TARGET_COUNT)

    p_upload = sub.add_parser("upload-images", help="download, process, and upload images; write the manifest")
    _add_shared_options(p_upload, suppress_default=True)
    p_upload.add_argument("--target", type=int, default=catalog.TARGET_COUNT)
    p_upload.add_argument("--bucket")
    p_upload.add_argument("--catalog-version", default=DEFAULT_CATALOG_VERSION)

    p_import = sub.add_parser("import", help="transactionally import the verified manifest (requires --apply)")
    _add_shared_options(p_import, suppress_default=True)
    p_import.add_argument("--manifest", default=str(DEFAULT_OUTPUT_DIR / "products.jsonl"))
    p_import.add_argument("--report", default=str(DEFAULT_OUTPUT_DIR / "catalog-report.json"))
    p_import.add_argument("--apply", action="store_true")
    p_import.add_argument("--dry-run", action="store_true")
    p_import.add_argument("--refresh-existing-catalog", action="store_true")

    p_verify = sub.add_parser("verify", help="verify the manifest and reports without writing anything")
    _add_shared_options(p_verify, suppress_default=True)
    p_verify.add_argument("--manifest", default=str(DEFAULT_OUTPUT_DIR / "products.jsonl"))
    p_verify.add_argument("--report", default=str(DEFAULT_OUTPUT_DIR / "catalog-report.json"))
    p_verify.add_argument("--database", action="store_true", help="also verify the database (read-only)")
    p_verify.add_argument("--minio", action="store_true", help="also verify MinIO image objects (read-only)")
    p_verify.add_argument("--bucket")

    p_all = sub.add_parser("all", help="run discover, build, upload-images, verify; import only with --apply")
    _add_shared_options(p_all, suppress_default=True)
    p_all.add_argument("--config", default=str(DEFAULT_CONFIG))
    p_all.add_argument("--minimum-candidates", type=int, default=4000)
    p_all.add_argument("--target", type=int, default=catalog.TARGET_COUNT)
    p_all.add_argument("--bucket")
    p_all.add_argument("--catalog-version", default=DEFAULT_CATALOG_VERSION)
    p_all.add_argument("--manifest", default=str(DEFAULT_OUTPUT_DIR / "products.jsonl"))
    p_all.add_argument("--report", default=str(DEFAULT_OUTPUT_DIR / "catalog-report.json"))
    p_all.add_argument("--apply", action="store_true")
    p_all.add_argument("--dry-run", action="store_true")
    p_all.add_argument("--refresh-existing-catalog", action="store_true")
    p_all.add_argument("--database", action="store_true")
    p_all.add_argument("--minio", action="store_true")
    return parser


_COMMANDS = {
    "discover": cmd_discover,
    "build": cmd_build,
    "upload-images": cmd_upload_images,
    "import": cmd_import,
    "verify": cmd_verify,
    "all": cmd_all,
}


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return _COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
