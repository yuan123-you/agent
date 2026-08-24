"""Transactional, fail-closed import of a verified real-product catalog."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence

TARGET_COUNT = 2512
REPLACEMENT_COUNT = 512
BATCH_SIZE = 100
KNOWN_V1_SEED_DIGEST = "fad578ccc7a3bc7bf7213ce735fa9998b008888c5be7c577cd8af7faea540c9c"


class ImportSafetyError(RuntimeError):
    """Raised when the database or staged catalog does not meet cutover invariants."""


@dataclass(frozen=True)
class ImportResult:
    dry_run: bool
    catalog_version: str
    updated: int
    inserted: int
    deleted_reviews: int
    final_count: int


@dataclass(frozen=True)
class DatabaseVerification:
    valid: bool
    product_count: int
    source_key_count: int
    invalid_specs: int
    nonpositive_prices: int
    invalid_image_urls: int


_STAGE_COLUMNS = (
    "name", "category", "brand", "price", "stock", "image_url", "currency",
    "source_name", "source_url", "source_product_id", "source_updated_at",
    "collected_at", "original_image_url", "image_sha256",
    "simulated_commerce_fields", "description", "selling_points", "specs",
    "origin", "production_date", "material", "sales", "content_hash",
    "catalog_version", "replacement_slot",
)

_CREATE_STAGE = """
CREATE TEMPORARY TABLE product_catalog_stage (
  name VARCHAR(128) NOT NULL,
  category VARCHAR(32) NOT NULL,
  brand VARCHAR(32) NOT NULL,
  price DECIMAL(10,2) NOT NULL,
  stock INT NOT NULL,
  image_url VARCHAR(512) NOT NULL,
  currency VARCHAR(16) NOT NULL,
  source_name VARCHAR(255) NOT NULL,
  source_url VARCHAR(2048) NOT NULL,
  source_product_id VARCHAR(255) NOT NULL,
  source_updated_at DATETIME(3) NULL,
  collected_at DATETIME(3) NOT NULL,
  original_image_url VARCHAR(2048) NULL,
  image_sha256 CHAR(64) NOT NULL,
  simulated_commerce_fields TINYINT NOT NULL,
  description TEXT NULL,
  selling_points VARCHAR(512) NULL,
  specs JSON NOT NULL,
  origin VARCHAR(128) NULL,
  production_date VARCHAR(64) NULL,
  material VARCHAR(128) NULL,
  sales INT NOT NULL,
  content_hash CHAR(64) NOT NULL,
  catalog_version VARCHAR(128) NOT NULL,
  replacement_slot INT NULL,
  UNIQUE KEY uk_stage_source (source_name, source_product_id),
  UNIQUE KEY uk_stage_slot (replacement_slot)
) ENGINE=InnoDB
"""

_INSERT_STAGE = f"""
INSERT INTO product_catalog_stage ({', '.join(_STAGE_COLUMNS)})
VALUES ({', '.join(['%s'] * len(_STAGE_COLUMNS))})
"""

_STAGE_VALIDATION = """
SELECT /* STAGING_VALIDATION */
  COUNT(*),
  COUNT(DISTINCT source_name, source_product_id),
  COUNT(replacement_slot),
  SUM(CASE WHEN replacement_slot IS NOT NULL AND replacement_slot NOT BETWEEN 1 AND 512 THEN 1 ELSE 0 END),
  SUM(CASE WHEN specs IS NULL OR NOT JSON_VALID(specs) THEN 1 ELSE 0 END),
  SUM(CASE WHEN price <= 0 THEN 1 ELSE 0 END),
  SUM(CASE WHEN image_url NOT LIKE '/%' OR image_url LIKE '//%'
            OR LOWER(image_url) LIKE '%picsum%' OR image_url LIKE '%..%' THEN 1 ELSE 0 END)
FROM product_catalog_stage
"""

_DATABASE_STATE = """
SELECT /* DATABASE_STATE */
  COUNT(*),
  COUNT(DISTINCT CASE WHEN source_name IS NOT NULL AND source_product_id IS NOT NULL
                      THEN source_name END,
                 CASE WHEN source_name IS NOT NULL AND source_product_id IS NOT NULL
                      THEN source_product_id END)
FROM product
WHERE deleted = 0 AND status = 'ON_SALE'
"""

_SEED_IDENTITY = """
SELECT /* SEED_IDENTITY */ id, name, category, brand, price, image_url
FROM product
WHERE deleted = 0 AND status = 'ON_SALE'
ORDER BY id
"""

_REFRESH_MISMATCHES = """
SELECT /* REFRESH_MISMATCHES */
  (SELECT COUNT(*)
     FROM product p
     LEFT JOIN product_catalog_stage s
       ON s.source_name = p.source_name AND s.source_product_id = p.source_product_id
    WHERE p.deleted = 0 AND p.status = 'ON_SALE'
      AND (s.source_name IS NULL OR NOT (
        p.name <=> s.name AND p.category <=> s.category AND p.brand <=> s.brand
        AND p.price <=> s.price AND p.stock <=> s.stock AND p.image_url <=> s.image_url
        AND p.currency <=> s.currency AND p.source_url <=> s.source_url
        AND p.source_updated_at <=> s.source_updated_at AND p.collected_at <=> s.collected_at
        AND p.original_image_url <=> s.original_image_url AND p.image_sha256 <=> s.image_sha256
        AND p.simulated_commerce_fields <=> s.simulated_commerce_fields
        AND p.description <=> s.description AND p.selling_points <=> s.selling_points
        AND p.specs <=> s.specs AND p.origin <=> s.origin
        AND p.production_date <=> s.production_date AND p.material <=> s.material
        AND p.sales <=> s.sales)))
  +
  (SELECT COUNT(*)
     FROM product_catalog_stage s
     LEFT JOIN product p
       ON p.source_name = s.source_name AND p.source_product_id = s.source_product_id
      AND p.deleted = 0 AND p.status = 'ON_SALE'
    WHERE p.id IS NULL)
"""

_TARGET_ASSIGNMENTS = """
p.name = s.name, p.category = s.category, p.brand = s.brand, p.price = s.price,
p.stock = s.stock, p.image_url = s.image_url, p.currency = s.currency,
p.source_name = s.source_name, p.source_url = s.source_url,
p.source_product_id = s.source_product_id, p.source_updated_at = s.source_updated_at,
p.collected_at = s.collected_at, p.original_image_url = s.original_image_url,
p.image_sha256 = s.image_sha256,
p.simulated_commerce_fields = s.simulated_commerce_fields,
p.description = s.description, p.selling_points = s.selling_points, p.specs = s.specs,
p.origin = s.origin, p.production_date = s.production_date, p.material = s.material,
p.sales = s.sales, p.status = 'ON_SALE', p.deleted = 0
"""

_UPDATE_REPLACEMENTS = f"""
UPDATE product p
JOIN product_catalog_stage s ON p.id = s.replacement_slot
SET {_TARGET_ASSIGNMENTS}
WHERE s.replacement_slot IS NOT NULL
"""

_TARGET_COLUMNS = _STAGE_COLUMNS[:22]
_INSERT_NEW = f"""
INSERT INTO product ({', '.join(_TARGET_COLUMNS)})
SELECT {', '.join('s.' + column for column in _TARGET_COLUMNS)}
FROM product_catalog_stage s
WHERE s.replacement_slot IS NULL
ON DUPLICATE KEY UPDATE
  {", ".join(f"{column} = VALUES({column})" for column in _TARGET_COLUMNS)}
"""

_DATABASE_VERIFICATION = """
SELECT /* DATABASE_VERIFICATION */
  COUNT(*),
  COUNT(DISTINCT source_name, source_product_id),
  SUM(CASE WHEN specs IS NULL OR NOT JSON_VALID(specs) THEN 1 ELSE 0 END),
  SUM(CASE WHEN price <= 0 THEN 1 ELSE 0 END),
  SUM(CASE WHEN image_url IS NULL OR image_url NOT LIKE '/%' OR image_url LIKE '//%'
            OR LOWER(image_url) LIKE '%picsum%' OR image_url LIKE '%..%' THEN 1 ELSE 0 END)
FROM product
WHERE deleted = 0 AND status = 'ON_SALE'
"""

_DEMO_REVIEWS = (
    (1, 1, 3, 5, "拍照真的绝了，夜景模式完全碾压我上一部手机，电池续航一天半没问题！", "黑色 12+256G"),
    (2, 1001, 4, 4, "手感不错，就是发热控制一般，玩游戏久了会烫。整体满意。", "白色 12+512G"),
    (3, 5, 3, 5, "性价比之王！这个价位有OIS防抖真的良心，日常拍照完全够用。", "蓝色 8+128G"),
    (4, 41, 3, 5, "大米很新鲜，煮出来的饭香喷喷，家里老人都说好，回购第二次了！", "10kg装"),
    (5, 44, 4, 5, "苹果很甜很多汁，包装也很扎实，一个坏果都没有，物流隔天就到。", "5kg装"),
    (6, 81, 3, 5, "跑鞋轻若无物，缓震回弹很棒，跑了10公里脚不酸，强烈推荐！", "42码 黑色"),
    (7, 83, 3, 4, "鞋子很帅气，就是码数偏小，建议大家买大半码。", "43码 白色"),
    (8, 61, 3, 5, "面霜保湿效果很好，吸收快不油腻，敏感肌用着也没问题。", "50g标准装"),
    (9, 91, 3, 5, "三体yyds！典藏版装帧太精美了，送礼自留都合适。", "精装三册"),
    (10, 95, 4, 5, "床垫软硬适中，睡了一周腰不酸了，这个价格买到就是赚到。", "180×200cm"),
)
_REVIEW_GUARD = "(id = %s AND product_id = %s AND user_id = %s AND rating = %s AND content = %s AND spec_info = %s AND order_item_id IS NULL AND merchant_reply IS NULL AND deleted = 0)"
_DELETE_DEMO_REVIEWS = "DELETE FROM product_review WHERE " + " OR ".join([_REVIEW_GUARD] * len(_DEMO_REVIEWS))


def _seed_digest(rows: Iterable[Sequence[Any]]) -> str:
    canonical = []
    for product_id, name, category, brand, price, image_url in rows:
        normalized_price = format(Decimal(str(price)).quantize(Decimal("0.01")), "f")
        canonical.append(json.dumps(
            [product_id, name, category, brand, normalized_price, image_url],
            ensure_ascii=False,
            separators=(",", ":"),
        ))
    return hashlib.sha256("\n".join(canonical).encode("utf-8")).hexdigest()


def _as_mapping(product: Any) -> Mapping[str, Any]:
    value = product.to_json() if hasattr(product, "to_json") else product
    if not isinstance(value, Mapping):
        raise ImportSafetyError("products must contain catalog mappings or CatalogProduct values")
    return value


def _stage_row(product: Mapping[str, Any]) -> tuple[Any, ...]:
    try:
        selling_points = " ".join(product["selling_points"])
        specs = json.dumps(product["specs"], ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        values = {
            **product,
            "selling_points": selling_points,
            "specs": specs,
            "simulated_commerce_fields": product["commerce_values_simulated"],
        }
        return tuple(values[column] for column in _STAGE_COLUMNS)
    except (KeyError, TypeError, ValueError) as exc:
        raise ImportSafetyError(f"invalid catalog row: {exc}") from exc


def _prepare_products(products: Iterable[Any]) -> tuple[list[tuple[Any, ...]], str]:
    rows = [_stage_row(_as_mapping(product)) for product in products]
    versions = {row[_STAGE_COLUMNS.index("catalog_version")] for row in rows}
    if len(rows) != TARGET_COUNT or len(versions) != 1 or not next(iter(versions), None):
        raise ImportSafetyError("catalog must contain 2512 rows with one nonblank catalog version")
    return rows, str(next(iter(versions)))


def _fetch_database_state(cursor: Any) -> tuple[int, int]:
    cursor.execute(_DATABASE_STATE)
    row = cursor.fetchone()
    return int(row[0]), int(row[1])


def _verification_from_cursor(cursor: Any) -> DatabaseVerification:
    cursor.execute(_DATABASE_VERIFICATION)
    row = cursor.fetchone()
    product_count, source_key_count, invalid_specs, nonpositive_prices, invalid_image_urls = (
        int(value or 0) for value in row
    )
    return DatabaseVerification(
        valid=(product_count == TARGET_COUNT and source_key_count == TARGET_COUNT
               and invalid_specs == nonpositive_prices == invalid_image_urls == 0),
        product_count=product_count,
        source_key_count=source_key_count,
        invalid_specs=invalid_specs,
        nonpositive_prices=nonpositive_prices,
        invalid_image_urls=invalid_image_urls,
    )

def verify_database(connection: Any) -> DatabaseVerification:
    """Read active catalog safety metrics without mutating the connection."""
    cursor = connection.cursor()
    try:
        return _verification_from_cursor(cursor)
    finally:
        cursor.close()


def import_catalog(
    connection: Any,
    products: Iterable[Any],
    dry_run: bool = False,
    *,
    refresh_existing_catalog: bool = False,
) -> ImportResult:
    """Stage, validate, and atomically cut over exactly 2,512 products."""
    rows, catalog_version = _prepare_products(products)
    cursor = connection.cursor()
    began = False
    try:
        connection.begin()
        began = True
        cursor.execute("DROP TEMPORARY TABLE IF EXISTS product_catalog_stage")
        cursor.execute(_CREATE_STAGE)
        for start in range(0, len(rows), BATCH_SIZE):
            cursor.executemany(_INSERT_STAGE, rows[start:start + BATCH_SIZE])

        cursor.execute(_STAGE_VALIDATION)
        staged = tuple(int(value or 0) for value in cursor.fetchone())
        if staged != (TARGET_COUNT, TARGET_COUNT, REPLACEMENT_COUNT, 0, 0, 0, 0):
            raise ImportSafetyError(f"staging validation failed: {staged}")

        active_count, source_key_count = _fetch_database_state(cursor)
        if refresh_existing_catalog:
            if (active_count, source_key_count) != (TARGET_COUNT, TARGET_COUNT):
                raise ImportSafetyError("refresh requires exactly 2512 active products with provenance")
            cursor.execute(_REFRESH_MISMATCHES)
            if int(cursor.fetchone()[0]) != 0:
                raise ImportSafetyError("refresh catalog identity/version does not match the database")
        else:
            if (active_count, source_key_count) != (REPLACEMENT_COUNT, 0):
                raise ImportSafetyError("initial import requires exactly the known 512 active seed products")
            cursor.execute(_SEED_IDENTITY)
            if _seed_digest(cursor.fetchall()) != KNOWN_V1_SEED_DIGEST:
                raise ImportSafetyError("active products do not match the known V1 seed catalog")

        if dry_run:
            cursor.execute("DROP TEMPORARY TABLE product_catalog_stage")
            connection.rollback()
            began = False
            return ImportResult(True, catalog_version, 0, 0, 0, active_count)

        cursor.execute(_UPDATE_REPLACEMENTS)
        cursor.execute(_INSERT_NEW)
        deleted_reviews = 0
        if not refresh_existing_catalog:
            cursor.execute(_DELETE_DEMO_REVIEWS, tuple(value for row in _DEMO_REVIEWS for value in row))
            deleted_reviews = int(cursor.rowcount)
            if deleted_reviews != len(_DEMO_REVIEWS):
                raise ImportSafetyError("known V1 demo reviews did not match exactly")

        verification = _verification_from_cursor(cursor)
        if not verification.valid:
            raise ImportSafetyError(f"post-cutover database verification failed: {verification}")
        cursor.execute("DROP TEMPORARY TABLE product_catalog_stage")
        connection.commit()
        began = False
        return ImportResult(False, catalog_version, REPLACEMENT_COUNT, TARGET_COUNT - REPLACEMENT_COUNT,
                            deleted_reviews, verification.product_count)
    except BaseException as exc:
        if began:
            try:
                connection.rollback()
            except BaseException as rollback_exc:
                exc.add_note(f"rollback also failed: {rollback_exc!r}")
        raise
    finally:
        cursor.close()
