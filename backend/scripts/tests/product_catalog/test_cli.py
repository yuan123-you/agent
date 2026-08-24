from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.scripts import generate_product_catalog as cli
from backend.scripts.product_catalog import catalog
from backend.scripts.product_catalog.model import CatalogProduct, ImageCandidate, RawProduct


def _catalog_products() -> list[CatalogProduct]:
    """A deterministic, valid 2,512-product catalog for read-only verify tests."""
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)
    products = []
    for index in range(1, 2513):
        raw = RawProduct(
            name=f"Real product {index}",
            brand="Real brand",
            category="PHONE",
            price=Decimal("12.34"),
            currency="CNY",
            description="Real description",
            selling_points=("one", "two"),
            specs={"color": "black"},
            source_name="source",
            source_url=f"https://shop.example/products/{index}",
            source_product_id=str(index),
            source_updated_at=None,
            collected_at=now,
            image_candidates=(ImageCandidate(f"https://cdn.example/{index}.jpg"),),
        )
        products.append(CatalogProduct(
            raw=raw,
            stock=10,
            sales=20,
            image_url=f"/api/v1/product-images/catalog/{index:064x}.webp",
            image_sha256=f"{index:064x}",
            content_hash=f"{index + 3000:064x}",
            catalog_version="catalog-v1",
            image_original_bytes=100,
            image_output_bytes=80,
        ))
    return products


def test_help_lists_commands(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["--help"])
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    for command in ("discover", "build", "upload-images", "import", "verify", "all"):
        assert command in help_text


def test_build_requires_discovery_cache(tmp_path):
    code = cli.main(["build", "--cache-root", str(tmp_path / "cache")])
    assert code == 1


def test_upload_images_requires_built_candidates(tmp_path):
    code = cli.main(["upload-images", "--cache-root", str(tmp_path / "cache")])
    assert code == 1


def test_import_refuses_without_apply(tmp_path):
    manifest = tmp_path / "products.jsonl"
    report = tmp_path / "catalog-report.json"
    manifest.write_text("")
    report.write_text("")
    code = cli.main(["import", "--manifest", str(manifest), "--report", str(report)])
    assert code == 1


def test_import_refuses_unverified_manifest_even_with_apply(tmp_path):
    manifest = tmp_path / "products.jsonl"
    report = tmp_path / "catalog-report.json"
    manifest.write_text("not valid json")
    report.write_text("{}")
    code = cli.main(["import", "--apply", "--manifest", str(manifest), "--report", str(report)])
    assert code == 1


def test_verify_is_read_only(tmp_path):
    output = tmp_path / "catalog"
    catalog.write_catalog(_catalog_products(), output)
    manifest = output / "products.jsonl"
    report = output / "catalog-report.json"
    before = {path.name: path.read_bytes() for path in output.iterdir()}

    code = cli.main(["verify", "--manifest", str(manifest), "--report", str(report)])

    assert code == 0
    after = {path.name: path.read_bytes() for path in output.iterdir()}
    assert after == before
    assert sorted(after) == ["catalog-report.json", "catalog-report.md", "products.jsonl"]


def test_credentials_only_allow_mysql_and_minio():
    env = {
        "MYSQL_HOST": "db",
        "MYSQL_PASSWORD": "secret-db",
        "MINIO_ENDPOINT": "minio:9000",
        "MINIO_SECRET_KEY": "secret-minio",
        "AWS_SECRET_ACCESS_KEY": "nope",
        "DB_PASSWORD": "nope",
        "PATH": "nope",
    }
    credentials = cli._credentials(env)
    assert set(credentials) == {"MYSQL_HOST", "MYSQL_PASSWORD", "MINIO_ENDPOINT", "MINIO_SECRET_KEY"}


def test_logs_redact_secrets():
    secrets = {"MYSQL_PASSWORD": "hunter2", "MINIO_SECRET_KEY": "supersecret"}
    message = cli.redact("connecting with hunter2 and supersecret", secrets)
    assert "hunter2" not in message
    assert "supersecret" not in message
    assert message.count("***") == 2


def test_all_stops_after_verify_unless_apply(monkeypatch):
    calls: list[str] = []

    def fake_step(name):
        def impl(_args):
            calls.append(name)
            return 0
        return impl

    for name in ("cmd_discover", "cmd_build", "cmd_upload_images", "cmd_verify", "cmd_import"):
        monkeypatch.setattr(cli, name, fake_step(name))

    code = cli.main(["all"])
    assert code == 0
    assert calls == ["cmd_discover", "cmd_build", "cmd_upload_images", "cmd_verify"]

    calls.clear()
    code = cli.main(["all", "--apply"])
    assert code == 0
    assert calls == ["cmd_discover", "cmd_build", "cmd_upload_images", "cmd_verify", "cmd_import"]
