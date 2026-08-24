from __future__ import annotations

import ast
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal
from typing import Any

import pytest

from backend.scripts.product_catalog.importer import (
    ImportSafetyError,
    KNOWN_V1_SEED_DIGEST,
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
        self.rowcounts = {"UPDATE product": 512, "INSERT INTO product (": 2000}

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
        else:
            for prefix, count in self.rowcounts.items():
                if normalized.startswith(prefix):
                    self.rowcount = count
                    break
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


def final_v1_seed_rows():
    migration = Path(__file__).parents[3] / "src/main/resources/db/migration/V1__baseline.sql"
    rows = []
    in_products = False
    for line in migration.read_text(encoding="utf-8").splitlines():
        if line.startswith("INSERT INTO product ("):
            in_products = True
            continue
        value = line.strip()
        if in_products and value.startswith("("):
            rows.append(ast.literal_eval(value.rstrip(",;")))
            if value.endswith(";"):
                in_products = False
        elif in_products and value.startswith("--"):
            in_products = False
    assert len(rows) == 512
    return [
        (index, row[0], row[1], row[2], Decimal(str(row[3])),
         f"https://picsum.photos/seed/aimall{index}/600/600")
        for index, row in enumerate(rows, 1)
    ]


def applied_connection():
    rows = final_v1_seed_rows()
    return FakeConnection(FakeCursor(seed_rows=rows))


def test_known_seed_digest_matches_final_v1_rows_after_picsum_update():
    assert KNOWN_V1_SEED_DIGEST == "04ba4c06c06868894529f50c0e0c34643697f754bc27f6cc38574d21dfcce34d"
    assert _seed_digest(final_v1_seed_rows()) == KNOWN_V1_SEED_DIGEST


def test_initial_import_stages_parameterized_batches_and_cuts_over_once():
    connection = applied_connection()

    result = import_catalog(connection, products())

    calls = connection.fake_cursor.calls
    batches = [call for call in calls if call[0] == "executemany"]
    assert [len(call[2]) for call in batches] == [100] * 25 + [12]
    assert all("%s" in call[1] for call in batches)
    assert all("Real product" not in call[1] for call in batches)
    sql = [call[1] for call in calls if call[0] == "execute"]
    assert next(i for i, value in enumerate(sql) if "CREATE TEMPORARY TABLE" in value) < next(i for i, value in enumerate(sql) if "STAGING_VALIDATION" in value)
    assert "NOT BETWEEN 1 AND 512" in next(value for value in sql if "STAGING_VALIDATION" in value)
    lock_index = next(i for i, value in enumerate(sql) if "FOR UPDATE" in value)
    assert lock_index < next(i for i, value in enumerate(sql) if "DATABASE_STATE" in value)
    assert lock_index < next(i for i, value in enumerate(sql) if "SEED_IDENTITY" in value)
    assert sql[-1] == "DROP TEMPORARY TABLE IF EXISTS product_catalog_stage"
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


def test_stage_converts_manifest_timestamps_to_naive_utc_datetimes():
    connection = applied_connection()
    manifest = products()
    manifest[0]["collected_at"] = "2026-08-24T08:30:00.123456+08:00"
    manifest[0]["source_updated_at"] = "2026-08-23T20:15:00.654321-04:00"

    import_catalog(connection, manifest, dry_run=True)

    first = next(call for call in connection.fake_cursor.calls if call[0] == "executemany")[2][0]
    assert first[10] == datetime(2026, 8, 24, 0, 15, 0, 654321)
    assert first[11] == datetime(2026, 8, 24, 0, 30, 0, 123456)
    assert first[10].tzinfo is None and first[11].tzinfo is None


@pytest.mark.parametrize("field,value", [
    ("collected_at", "2026-08-24T00:00:00"),
    ("collected_at", []),
    ("source_updated_at", "not-a-time"),
])
def test_stage_rejects_timestamps_that_task5_rejects(field, value):
    manifest = products()
    manifest[0][field] = value

    with pytest.raises(ImportSafetyError, match=f"invalid {field}"):
        import_catalog(FakeConnection(FakeCursor()), manifest)


def test_stage_rejects_row_when_both_task5_freshness_timestamps_are_stale():
    manifest = products()
    manifest[0]["collected_at"] = "2024-12-31T23:59:59Z"
    manifest[0]["source_updated_at"] = None

    with pytest.raises(ImportSafetyError, match="stale time"):
        import_catalog(FakeConnection(FakeCursor()), manifest)


def test_initial_cutover_rejects_update_or_insert_affected_row_mismatch():
    for statement, count in (("UPDATE product", 511), ("INSERT INTO product (", 1999)):
        connection = applied_connection()
        connection.fake_cursor.rowcounts[statement] = count

        with pytest.raises(ImportSafetyError, match="affected"):
            import_catalog(connection, products())

        assert connection.events == ["cursor", "begin", "rollback"]
        sql = [call[1] for call in connection.fake_cursor.calls if call[0] == "execute"]
        assert sql[-1] == "DROP TEMPORARY TABLE IF EXISTS product_catalog_stage"


def test_dry_run_stages_and_validates_but_never_cuts_over_or_commits():
    connection = applied_connection()

    result = import_catalog(connection, products(), dry_run=True)

    sql = [call[1] for call in connection.fake_cursor.calls if call[0] == "execute"]
    assert not any(value.startswith(("UPDATE product", "INSERT INTO product (", "DELETE FROM")) for value in sql)
    assert connection.events == ["cursor", "begin", "rollback"]
    assert sql[-1] == "DROP TEMPORARY TABLE IF EXISTS product_catalog_stage"
    assert result.dry_run and result.final_count == 512


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda cursor: setattr(cursor, "active_count", 511), "exactly the known 512"),
        (lambda cursor: cursor.seed_rows.__setitem__(0, (1, "changed", "PHONE", "Seed brand", Decimal("9.99"), "/images/seed_1.jpg")), "known V1 seed"),
    ],
)
def test_initial_import_refuses_unknown_database_and_rolls_back(mutate, message):
    connection = applied_connection()
    mutate(connection.fake_cursor)

    with pytest.raises(ImportSafetyError, match=message):
        import_catalog(connection, products())

    assert connection.events == ["cursor", "begin", "rollback"]


def test_refresh_requires_exact_existing_catalog_identity_and_version():
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


def test_malformed_staging_rolls_back_before_cutover():
    connection = applied_connection()
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


def test_review_guard_mismatch_rolls_back_the_whole_cutover():
    connection = applied_connection()
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

class StatefulCursor:
    def __init__(self, connection):
        self.connection = connection
        self.calls = []
        self._one = None
        self._all = []
        self.rowcount = 0
        self.drop_count = 0

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        self.calls.append(("execute", normalized, params))
        self.connection.timeline.append(normalized)
        self.rowcount = 0
        if normalized.startswith("DROP TEMPORARY TABLE"):
            self.drop_count += 1
            self.connection.stage = None
            if self.connection.fail_final_drop and self.drop_count > 1:
                raise RuntimeError("cleanup exploded")
        elif "CREATE TEMPORARY TABLE" in normalized:
            self.connection.stage = []
        elif "STAGING_VALIDATION" in sql:
            rows = self.connection.stage or []
            slots = [row[24] for row in rows if row[24] is not None]
            self._one = (len(rows), len({(row[7], row[9]) for row in rows}), len(slots),
                         sum(not 1 <= slot <= 512 for slot in slots), 0, 0, 0)
        elif "FOR UPDATE" in normalized:
            self._all = [(row["id"],) for row in self.connection.products]
        elif "DATABASE_STATE" in sql:
            active = [row for row in self.connection.products if row["status"] == "ON_SALE" and row["deleted"] == 0]
            keys = {(row.get("source_name"), row.get("source_product_id")) for row in active
                    if row.get("source_name") is not None and row.get("source_product_id") is not None}
            self._one = (len(active), len(keys))
        elif "SEED_IDENTITY" in sql:
            self._all = [(row["id"], row["name"], row["category"], row["brand"], row["price"], row["image_url"])
                         for row in sorted(self.connection.products, key=lambda item: item["id"])]
        elif normalized.startswith("UPDATE product"):
            if self.connection.no_op_update:
                self.rowcount = 0
            else:
                by_id = {row["id"]: row for row in self.connection.products}
                replacements = [row for row in self.connection.stage if row[24] is not None]
                for staged in replacements:
                    target = by_id[staged[24]]
                    target.update(source_name=staged[7], source_product_id=staged[9], image_url=staged[5])
                self.rowcount = len(replacements)
        elif normalized.startswith("INSERT INTO product ("):
            if self.connection.no_op_insert:
                self.rowcount = 0
            else:
                new_rows = [row for row in self.connection.stage if row[24] is None]
                next_id = max(row["id"] for row in self.connection.products) + 1
                for offset, staged in enumerate(new_rows):
                    self.connection.products.append({
                        "id": next_id + offset, "name": staged[0], "category": staged[1],
                        "brand": staged[2], "price": Decimal(str(staged[3])), "image_url": staged[5],
                        "source_name": staged[7], "source_product_id": staged[9],
                        "status": "ON_SALE", "deleted": 0,
                    })
                self.rowcount = len(new_rows)
        elif normalized.startswith("DELETE FROM product_review"):
            self.rowcount = len(self.connection.reviews)
            self.connection.reviews.clear()
        elif "DATABASE_VERIFICATION" in sql:
            active = [row for row in self.connection.products if row["status"] == "ON_SALE" and row["deleted"] == 0]
            keys = {(row.get("source_name"), row.get("source_product_id")) for row in active
                    if row.get("source_name") is not None and row.get("source_product_id") is not None}
            self._one = (len(active), len(keys), 0, 0, 0)
        return self

    def executemany(self, sql, params):
        values = list(params)
        self.calls.append(("executemany", " ".join(sql.split()), values))
        self.connection.stage.extend(values)
        self.rowcount = len(values)
        return self

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._all

    def close(self):
        self.connection.timeline.append("cursor.close")


class StatefulConnection:
    def __init__(self, *, no_op_update=False, no_op_insert=False, commit_error=False, fail_final_drop=False):
        self.products = [
            {"id": row[0], "name": row[1], "category": row[2], "brand": row[3], "price": row[4],
             "image_url": row[5], "source_name": None, "source_product_id": None,
             "status": "ON_SALE", "deleted": 0}
            for row in final_v1_seed_rows()
        ]
        self.reviews = list(range(1, 11))
        self.stage = None
        self.no_op_update = no_op_update
        self.no_op_insert = no_op_insert
        self.commit_error = commit_error
        self.fail_final_drop = fail_final_drop
        self.timeline = []
        self._snapshot = None
        self.fake_cursor = StatefulCursor(self)

    def cursor(self):
        return self.fake_cursor

    def begin(self):
        self.timeline.append("begin")
        self._snapshot = (deepcopy(self.products), deepcopy(self.reviews))

    def commit(self):
        self.timeline.append("commit")
        if self.commit_error:
            raise RuntimeError("commit exploded")
        self._snapshot = None

    def rollback(self):
        self.timeline.append("rollback")
        if self._snapshot is not None:
            self.products, self.reviews = deepcopy(self._snapshot)
            self._snapshot = None


def test_stateful_transaction_commits_exact_final_state_and_cleans_temp_table():
    connection = StatefulConnection()

    result = import_catalog(connection, products())

    assert result.final_count == len(connection.products) == 2512
    assert len(connection.reviews) == 0
    assert connection.stage is None
    assert connection.timeline.index("commit") < connection.timeline.index("DROP TEMPORARY TABLE IF EXISTS product_catalog_stage", 2)


@pytest.mark.parametrize("failure", ["update", "insert"])
def test_stateful_no_op_dml_rolls_back_products_reviews_and_cleans_temp(failure):
    connection = StatefulConnection(no_op_update=failure == "update", no_op_insert=failure == "insert")
    before_products = deepcopy(connection.products)
    before_reviews = deepcopy(connection.reviews)

    with pytest.raises(ImportSafetyError, match="affected"):
        import_catalog(connection, products())

    assert connection.products == before_products
    assert connection.reviews == before_reviews
    assert connection.stage is None
    assert connection.timeline.index("rollback") < connection.timeline.index("DROP TEMPORARY TABLE IF EXISTS product_catalog_stage", 2)


def test_stateful_commit_exception_rolls_back_and_then_cleans_temp_table():
    connection = StatefulConnection(commit_error=True)
    before_products = deepcopy(connection.products)

    with pytest.raises(RuntimeError, match="commit exploded"):
        import_catalog(connection, products())

    assert connection.products == before_products
    assert connection.reviews == list(range(1, 11))
    assert connection.stage is None
    assert connection.timeline.index("commit") < connection.timeline.index("rollback")
    assert connection.timeline.index("rollback") < connection.timeline.index("DROP TEMPORARY TABLE IF EXISTS product_catalog_stage", 2)


def test_cleanup_failure_does_not_mask_primary_cutover_failure():
    connection = StatefulConnection(no_op_update=True, fail_final_drop=True)

    with pytest.raises(ImportSafetyError, match="affected") as raised:
        import_catalog(connection, products())

    assert any("cleanup exploded" in note for note in raised.value.__notes__)
    assert len(connection.products) == 512
    assert connection.reviews == list(range(1, 11))
