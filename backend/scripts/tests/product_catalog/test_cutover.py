"""Guarded replacement tests: old IDs, merchant goods and transactions must survive."""
from copy import deepcopy
from pathlib import Path
import re
import pytest
from backend.scripts.product_catalog.cutover import replace_demo_catalog, validate_catalog_images
from backend.scripts.product_catalog.importer import ImportSafetyError
from backend.scripts.tests.product_catalog.test_importer import final_v1_seed_rows, products


def seeded_rows():
    sql = (Path(__file__).parents[3] / "src/main/resources/db/migration/V12__category_images.sql").read_text(encoding="utf-8")
    images = dict(re.findall(r"WHEN '([^']+)' THEN '([^']+)'", sql))
    return [(*r[:5], images[r[2]]) for r in final_v1_seed_rows()]


def catalog():
    rows = products()[:2]
    for row in rows:
        row.update(currency="CNY", replacement_slot=None, source_name="www.apple.com.cn", brand="Apple",
                   source_url="https://www.apple.com.cn/shop/product/" + row["source_product_id"].lower(), category="PHONE",
                   original_image_url="https://store.storeimages.cdn-apple.com/1/as-images.apple.com/is/ABC",
                   specs={"产品型号": row["source_product_id"]}, sales=0)
    return rows


class Cursor:
    def __init__(self, seeds=None):
        self.seeds = seeded_rows() if seeds is None else seeds
        self.calls = []
        self.rowcount = 0
    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        self.rowcount = 512 if "RETIRE_KNOWN_DEMO" in sql else 2 if "INSERT_VERIFIED_PRODUCTS" in sql else 0
        if "LOCK_KNOWN_DEMO" in sql: self.rows = self.seeds
        elif "SOURCE_COLLISIONS" in sql: self.rows = [(0,)]
        elif "VERIFY_CUTOVER" in sql: self.rows = [(2, 2)]
        else: self.rows = []
    def executemany(self, sql, params): self.calls.append((sql, list(params)))
    def fetchall(self): return self.rows
    def fetchone(self): return self.rows[0]
    def close(self): pass


class Connection:
    def __init__(self, seeds=None): self.cur = Cursor(seeds); self.events = []
    def cursor(self): return self.cur
    def begin(self): self.events.append("begin")
    def commit(self): self.events.append("commit")
    def rollback(self): self.events.append("rollback")


def test_appends_real_products_retires_only_exact_demo_and_never_reuses_old_ids():
    db = Connection()
    result = replace_demo_catalog(db, catalog(), dry_run=False)
    sql = "\n".join(q for q, _ in db.cur.calls)
    assert result == {"retired": 512, "inserted": 2, "dry_run": False}
    assert db.events == ["begin", "commit"]
    assert "WHERE id BETWEEN 1 AND 512" in sql
    assert "merchant_id <=> CASE" in sql and "FOR UPDATE" in sql
    assert "WHEN category IN ('PHONE','LAPTOP') THEN 1" in sql
    assert "WHEN category = 'FOOD' THEN 2" in sql
    assert "WHEN category = 'SPORTS' THEN 3" in sql
    insert = next(q for q, _ in db.cur.calls if "INSERT_VERIFIED_PRODUCTS" in q)
    assert "replacement_slot" not in insert and "ON DUPLICATE KEY UPDATE" not in insert
    assert "category_id" in insert and "brand_id" in insert
    assert not re.search(r"(?:DELETE FROM|UPDATE|INSERT INTO)\s+(?:order_item|order_info|product_review|favorite|cart_item|browse_history|mall_sku)\b", sql, re.I)
    assert "UPDATE product p" not in sql


def test_dry_run_rolls_back_without_retiring_or_inserting_products():
    db = Connection(); result = replace_demo_catalog(db, catalog())
    assert result["dry_run"] is True and db.events == ["begin", "rollback"]
    assert not any("RETIRE_KNOWN_DEMO" in q or "INSERT_VERIFIED_PRODUCTS" in q for q, _ in db.cur.calls)


@pytest.mark.parametrize("change", ["name", "price", "image", "missing"])
def test_refuses_to_replace_modified_or_missing_seed_products(change):
    rows = seeded_rows()
    if change == "missing": rows.pop()
    else:
        r = list(rows[0]); r[{"name": 1, "price": 4, "image": 5}[change]] = {"name": "Merchant edited", "price": 1, "image": "/uploaded.jpg"}[change]; rows[0] = tuple(r)
    db = Connection(rows)
    with pytest.raises(ImportSafetyError): replace_demo_catalog(db, catalog(), dry_run=False)
    assert db.events == ["begin", "rollback"]
    assert not any("RETIRE_KNOWN_DEMO" in q for q, _ in db.cur.calls)


@pytest.mark.parametrize("changes", [{"currency": "USD"}, {"image_url": "data:image/svg+xml,emoji"},
    {"image_sha256": "bad"}, {"specs": {}}, {"original_image_url": "https://picsum.photos/random"},
    {"source_url": "https://other.example/p"}, {"replacement_slot": 1}, {"price": "-1"}, {"price": "NaN"},
    {"specs": {"产品型号": "different sku"}}, {"category": "NOT_REAL"},
    {"source_url": "https://www.apple.com.cn/shop/product/wrong/a"},
    {"source_url": "http://www.apple.com.cn/shop/product/1"},
    {"original_image_url": "http://store.storeimages.cdn-apple.com/1/as-images.apple.com/is/ABC"}])
def test_rejects_unverified_manifest_before_any_database_write(changes):
    rows = catalog(); rows[0].update(changes); db = Connection()
    with pytest.raises(ImportSafetyError): replace_demo_catalog(db, rows, dry_run=False)
    assert not db.events and not db.cur.calls


def test_rejects_missing_or_mismatched_local_photo_bytes(tmp_path):
    rows = catalog()
    with pytest.raises(ImportSafetyError): validate_catalog_images(rows, tmp_path)
    (tmp_path / rows[0]["image_url"].split("/")[-1]).write_bytes(b"not a photo")
    with pytest.raises(ImportSafetyError): validate_catalog_images(rows, tmp_path)
