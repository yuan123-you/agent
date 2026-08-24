from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest

from backend.scripts.product_catalog.importer import (
    ImportSafetyError,
    _seed_digest,
    import_catalog,
    verify_database,
)


class FakeCursor:
    def __init__(self, *, seed_rows=None, active_count=512, source_keys=0, refresh_mismatches=0):
        self.seed_rows = seed_rows or []
        self.active_count = active_count
        self.source_keys = source_keys
        self.refresh_mismatches = refresh_mismatches
        self.calls: list[tuple[str, str, Any]] = []
        self._one = None
        self._all = []
        self.rowcount = 0

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        self.calls.append(("execute", normalized, params))
        self.rowcount = 0
        if "SEED_IDENTITY" in sql:
            self._all = self.seed_rows
        elif "STAGING_VALIDATION" in sql:
            self._one = (2512, 2512, 512, 0, 0, 0, 0)
        elif "DATABASE_STATE" in sql:
            self._one = (self.active_count, self.source_keys)
        elif "REFRESH_MISMATCHES" in sql:
            self._one = (self.refresh_mismatches,)
        elif "DATABASE_VERIFICATION" in sql:
            self._one = (2512, 2512, 0, 0, 0)
        elif normalized.startswith("DELETE FROM product_review"):
            self.rowcount = 10
        return self

    def executemany(self, sql, params):
        values = list(params)
        self.calls.append(("executemany", " ".join(sql.split()), values))
        self.rowcount = len(values)
        return self

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._all

    def close(self):
        self.calls.append(("close", "", None))


class FakeConnection:
    def __init__(self, cursor: FakeCursor):
        self.fake_cursor = cursor
        self.events: list[str] = []

    def cursor(self):
        self.events.append("cursor")
        return self.fake_cursor

    def begin(self):
        self.events.append("begin")

    def commit(self):
        self.events.append("commit")

    def rollback(self):
        self.events.append("rollback")


def products(version="catalog-v1"):
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)
    return [
        {
            "name": f"Real product {index}",
            "brand": "Real brand",
            "category": "PHONE",
            "price": "12.34",
            "currency": "CNY",
            "stock": 10,
            "sales": 20,
            "commerce_values_simulated": True,
            "description": "Real description",
            "selling_points": ["one", "two"],
            "specs": {"color": "black"},
            "origin": None,
            "material": None,
            "production_date": None,
            "source_name": "source",
            "source_url": f"https://shop.example/products/{index}",
            "source_product_id": str(index),
            "source_updated_at": None,
            "collected_at": now.isoformat().replace("+00:00", "Z"),
            "original_image_url": f"https://cdn.example/{index}.jpg",
            "image_url": f"/api/v1/product-images/catalog/{index:064x}.webp",
            "image_sha256": f"{index:064x}",
            "content_hash": f"{index + 3000:064x}",
            "catalog_version": version,
            "replacement_slot": index if index <= 512 else None,
            "image_original_bytes": 100,
            "image_output_bytes": 80,
        }
        for index in range(1, 2513)
    ]


def seed_rows():
    return [
        (index, f"Seed {index}", "PHONE", "Seed brand", Decimal("9.99"), f"/images/seed_{index}.jpg")
        for index in range(1, 513)
    ]


def applied_connection(monkeypatch):
    rows = seed_rows()
    monkeypatch.setattr("backend.scripts.product_catalog.importer.KNOWN_V1_SEED_DIGEST", _seed_digest(rows))
    cursor = FakeCursor(seed_rows=rows)
    return FakeConnection(cursor)


def test_initial_import_stages_parameterized_batches_and_cuts_over_once(monkeypatch):
    connection = applied_connection(monkeypatch)

    result = import_catalog(connection, products())

    calls = connection.fake_cursor.calls
    batches = [call for call in calls if call[0] == "executemany"]
    assert [len(call[2]) for call in batches] == [100] * 25 + [12]
    assert all("%s" in call[1] for call in batches)
    assert all("Real product" not in call[1] for call in batches)
    sql = [call[1] for call in calls if call[0] == "execute"]
    assert next(i for i, value in enumerate(sql) if "CREATE TEMPORARY TABLE" in value) < next(i for i, value in enumerate(sql) if "STAGING_VALIDATION" in value)
    assert "NOT BETWEEN 1 AND 512" in next(value for value in sql if "STAGING_VALIDATION" in value)
    update = next(value for value in sql if value.startswith("UPDATE product"))
    insert = next(value for value in sql if value.startswith("INSERT INTO product"))
    delete = next(value for value in sql if value.startswith("DELETE FROM product_review"))
    assert "replacement_slot" in update and "p.id = s.replacement_slot" in update
    assert "replacement_slot IS NULL" in insert
    assert "ON DUPLICATE KEY UPDATE" in insert
    assert "id = %s" in delete and "content = %s" in delete and "spec_info = %s" in delete
    delete_call = next(call for call in calls if call[0] == "execute" and call[1] == delete)
    assert len(delete_call[2]) == 60
    protected_dml = tuple(
        f"{verb} {table}" for verb in ("DELETE FROM", "UPDATE", "INSERT INTO")
        for table in ("order_item", "favorite", "browse_history")
    )
    assert all(not statement.startswith(protected_dml) for statement in sql)
    assert connection.events == ["cursor", "begin", "commit"]
    assert result.updated == 512
    assert result.inserted == 2000
    assert result.deleted_reviews == 10
    assert result.final_count == 2512


def test_dry_run_stages_and_validates_but_never_cuts_over_or_commits(monkeypatch):
    connection = applied_connection(monkeypatch)

    result = import_catalog(connection, products(), dry_run=True)

    sql = [call[1] for call in connection.fake_cursor.calls if call[0] == "execute"]
    assert not any(value.startswith(("UPDATE product", "INSERT INTO product (", "DELETE FROM")) for value in sql)
    assert connection.events == ["cursor", "begin", "rollback"]
    assert result.dry_run and result.final_count == 512


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda cursor: setattr(cursor, "active_count", 511), "exactly the known 512"),
        (lambda cursor: cursor.seed_rows.__setitem__(0, (1, "changed", "PHONE", "Seed brand", Decimal("9.99"), "/images/seed_1.jpg")), "known V1 seed"),
    ],
)
def test_initial_import_refuses_unknown_database_and_rolls_back(monkeypatch, mutate, message):
    connection = applied_connection(monkeypatch)
    mutate(connection.fake_cursor)

    with pytest.raises(ImportSafetyError, match=message):
        import_catalog(connection, products())

    assert connection.events == ["cursor", "begin", "rollback"]


def test_refresh_requires_exact_existing_catalog_identity_and_version(monkeypatch):
    cursor = FakeCursor(active_count=2512, source_keys=2512, refresh_mismatches=1)
    connection = FakeConnection(cursor)

    with pytest.raises(ImportSafetyError, match="identity/version"):
        import_catalog(connection, products(), refresh_existing_catalog=True)

    assert connection.events == ["cursor", "begin", "rollback"]
    assert not any(call[1].startswith(("UPDATE product", "INSERT INTO product (")) for call in cursor.calls)


def test_refresh_of_same_catalog_is_idempotent_and_remains_2512():
    cursor = FakeCursor(active_count=2512, source_keys=2512, refresh_mismatches=0)
    connection = FakeConnection(cursor)

    result = import_catalog(connection, products(), refresh_existing_catalog=True)

    assert result.final_count == 2512
    assert connection.events == ["cursor", "begin", "commit"]


def test_malformed_staging_rolls_back_before_cutover(monkeypatch):
    connection = applied_connection(monkeypatch)
    original_execute = connection.fake_cursor.execute

    def execute(sql, params=None):
        result = original_execute(sql, params)
        if "STAGING_VALIDATION" in sql:
            connection.fake_cursor._one = (2511, 2511, 511, 1, 1, 1, 1)
        return result

    connection.fake_cursor.execute = execute

    with pytest.raises(ImportSafetyError, match="staging validation"):
        import_catalog(connection, products())

    assert connection.events == ["cursor", "begin", "rollback"]


def test_review_guard_mismatch_rolls_back_the_whole_cutover(monkeypatch):
    connection = applied_connection(monkeypatch)
    original_execute = connection.fake_cursor.execute

    def execute(sql, params=None):
        result = original_execute(sql, params)
        if "DELETE FROM product_review" in sql:
            connection.fake_cursor.rowcount = 9
        return result

    connection.fake_cursor.execute = execute

    with pytest.raises(ImportSafetyError, match="demo reviews"):
        import_catalog(connection, products())

    sql = [call[1] for call in connection.fake_cursor.calls if call[0] == "execute"]
    assert any(value.startswith("UPDATE product") for value in sql)
    assert any(value.startswith("INSERT INTO product (") for value in sql)
    assert connection.events == ["cursor", "begin", "rollback"]


def test_verify_database_is_read_only_and_reports_hard_errors():
    cursor = FakeCursor(active_count=2512, source_keys=2512)
    connection = FakeConnection(cursor)

    result = verify_database(connection)

    assert result.valid
    assert result.product_count == 2512
    assert result.source_key_count == 2512
    assert connection.events == ["cursor"]
    assert [call[0] for call in cursor.calls] == ["execute", "close"]
