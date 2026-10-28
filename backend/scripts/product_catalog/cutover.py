"""Append verified real goods and retire only the exact known V1/V12 demo set.

Never overwrite product identities, delete reviews, or modify merchant-created
products, orders, carts, SKUs or historical snapshots. All writes are atomic.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
from urllib.parse import urlsplit
from PIL import Image
from .importer import (ImportSafetyError, KNOWN_V1_SEED_DIGEST, _seed_digest,
                       _TARGET_COLUMNS, _CREATE_STAGE, _INSERT_STAGE, _stage_row)

KNOWN_V12_SEED_DIGEST = "d832843e581726625a0373b6ed195794972e0b11011a6f51a223c0d11e6197d8"


def _validated_rows(products):
    if not products:
        raise ImportSafetyError("catalog cannot be empty")
    identities = set()
    for p in products:
        key = (p.get("source_name"), p.get("source_product_id"))
        try:
            price = Decimal(str(p.get("price", "0")))
            if not price.is_finite() or price <= 0:
                raise ValueError("invalid price")
        except (ValueError, InvalidOperation) as exc:
            raise ImportSafetyError("catalog requires a positive CNY price") from exc
        photo = str(p.get("image_url", ""))
        match = re.fullmatch(r"/api/v1/product-images/catalog/([0-9a-f]{64})\.(jpg|png|webp)", photo)
        if (not match or match[1] != p.get("image_sha256")
                or p.get("currency") != "CNY" or not isinstance(p.get("specs"), dict)
                or p.get("specs", {}).get("产品型号") != key[1]
                or p.get("category") not in {"PHONE", "LAPTOP", "BAGS"}
                or p.get("replacement_slot") is not None
                or p.get("source_name") != "www.apple.com.cn" or not key[1]
                or urlsplit(str(p.get("source_url", ""))).hostname != "www.apple.com.cn"
                or urlsplit(str(p.get("original_image_url", ""))).hostname != "store.storeimages.cdn-apple.com"
                or urlsplit(str(p.get("source_url", ""))).scheme != "https"
                or urlsplit(str(p.get("original_image_url", ""))).scheme != "https"
                or urlsplit(str(p.get("source_url", ""))).path.lower() != "/shop/product/" + str(key[1]).lower()
                or key in identities):
            raise ImportSafetyError("catalog requires unique official CNY facts and matching content-addressed photographs")
        identities.add(key)
    return [_stage_row(p) for p in products]


def validate_catalog_images(products, directory):
    """Check every referenced local raster file, not just a URL or HTTP status."""
    _validated_rows(products)
    checked = set()
    for p in products:
        name = p["image_url"].rsplit("/", 1)[-1]
        if name in checked:
            continue
        try:
            data = (Path(directory) / name).read_bytes()
            if sha256(data).hexdigest() != p["image_sha256"]:
                raise ValueError("image checksum mismatch")
            with Image.open(BytesIO(data)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"} or min(image.size) < 100:
                    raise ValueError("invalid product photograph")
                image.load()
        except Exception as exc:
            raise ImportSafetyError(f"unverified product photograph: {name}") from exc
        checked.add(name)
    return len(checked)


def replace_demo_catalog(connection, products, *, dry_run=True):
    products = list(products)
    rows = _validated_rows(products)
    cursor = connection.cursor()
    try:
        connection.begin()
        cursor.execute("DROP TEMPORARY TABLE IF EXISTS product_catalog_stage")
        cursor.execute(_CREATE_STAGE)
        for start in range(0, len(rows), 100):
            cursor.executemany(_INSERT_STAGE, rows[start:start + 100])
        cursor.execute("""SELECT /* LOCK_KNOWN_DEMO */ id, name, category, brand, price, image_url
            FROM product WHERE id BETWEEN 1 AND 512 AND deleted = 0 AND status = 'ON_SALE'
              AND source_name IS NULL AND source_product_id IS NULL AND (merchant_id <=> CASE
                WHEN category IN ('PHONE','LAPTOP') THEN 1
                WHEN category = 'FOOD' THEN 2
                WHEN category = 'SPORTS' THEN 3 ELSE NULL END)
            ORDER BY id FOR UPDATE""")
        seeds = cursor.fetchall()
        if len(seeds) != 512 or _seed_digest(seeds) not in {KNOWN_V1_SEED_DIGEST, KNOWN_V12_SEED_DIGEST}:
            raise ImportSafetyError("known demo identity does not match; refusing to overwrite merchant edits or reapply cutover")
        cursor.execute("""SELECT /* SOURCE_COLLISIONS */ COUNT(*) FROM product p
            JOIN product_catalog_stage s ON p.source_name = s.source_name AND p.source_product_id = s.source_product_id""")
        if cursor.fetchone()[0]:
            raise ImportSafetyError("catalog source identities already exist")
        if dry_run:
            connection.rollback()
            return {"retired": 0, "inserted": 0, "dry_run": True}
        cursor.execute("""INSERT INTO mall_brand (name)
            SELECT DISTINCT s.brand FROM product_catalog_stage s
            WHERE NOT EXISTS (SELECT 1 FROM mall_brand b WHERE b.name = s.brand AND b.deleted = 0)""")
        columns = ", ".join(_TARGET_COLUMNS)
        values = ", ".join("s." + c for c in _TARGET_COLUMNS)
        cursor.execute(f"""INSERT /* INSERT_VERIFIED_PRODUCTS */ INTO product ({columns}, category_id, brand_id)
            SELECT {values},
              (SELECT MIN(c.id) FROM mall_category c WHERE c.name = s.category AND c.level = 1 AND c.deleted = 0),
              (SELECT MIN(b.id) FROM mall_brand b WHERE b.name = s.brand AND b.deleted = 0)
            FROM product_catalog_stage s ORDER BY s.source_product_id""")
        inserted = cursor.rowcount
        if inserted != len(products):
            raise ImportSafetyError("unexpected inserted product count")
        cursor.execute("""UPDATE /* RETIRE_KNOWN_DEMO */ product SET status = 'OFF_SHELF'
            WHERE id BETWEEN 1 AND 512 AND deleted = 0 AND status = 'ON_SALE'
              AND source_name IS NULL AND source_product_id IS NULL AND (merchant_id <=> CASE
                WHEN category IN ('PHONE','LAPTOP') THEN 1
                WHEN category = 'FOOD' THEN 2
                WHEN category = 'SPORTS' THEN 3 ELSE NULL END)""")
        retired = cursor.rowcount
        if retired != 512:
            raise ImportSafetyError("unexpected retired demo count")
        cursor.execute("""SELECT /* VERIFY_CUTOVER */ COUNT(*),
            SUM(p.image_url = s.image_url AND p.name = s.name AND p.currency = 'CNY'
                AND p.category_id IS NOT NULL AND p.brand_id IS NOT NULL AND p.status = 'ON_SALE')
            FROM product p JOIN product_catalog_stage s
              ON p.source_name = s.source_name AND p.source_product_id = s.source_product_id
            WHERE p.deleted = 0""")
        if tuple(cursor.fetchone()) != (len(products), len(products)):
            raise ImportSafetyError("post-cutover verification failed")
        connection.commit()
        return {"retired": retired, "inserted": inserted, "dry_run": False}
    except BaseException:
        connection.rollback()
        raise
    finally:
        cursor.close()
