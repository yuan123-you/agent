"""Local TCP evidence and fail-closed publication tests; no model/config imports."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from hashlib import sha256
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


def evidence_module():
    return importlib.import_module("eval.retry_evidence")


@pytest.fixture(scope="module")
def wire_report():
    async def collect():
        existing = set(asyncio.all_tasks())
        report = await evidence_module().collect_report()
        await asyncio.sleep(0)
        assert not [task for task in asyncio.all_tasks() - existing if not task.done()]
        return report

    return asyncio.run(collect())


def test_actual_loopback_observations_prove_all_eight_scenarios(wire_report):
    evidence_module().validate_report(wire_report)
    assert wire_report["evidence_kind"] == "actual_loopback_tcp_fault_injection"
    assert wire_report["scope"] == {
        "business_ledger": "synthetic_in_memory",
        "external_services_used": False,
        "live_model_accuracy": False,
        "production_outage_or_sla": False,
        "time_basis": "relative_monotonic_seconds",
    }
    expected = {
        "read_503": (3, 0, "success"),
        "auth_401": (1, 0, "rejected"),
        "bad_model_json": (1, 0, "malformed_json"),
        "unsafe_write": (1, 1, "unresolved"),
        "keyed_write": (2, 1, "resolved"),
        "parallel_nested": (5, 0, "bounded_failure"),
        "deadline": (1, 0, "deadline_exceeded"),
        "sse_partial": (1, 0, "partial_stream_failed"),
    }
    assert set(wire_report["cases"]) == set(expected)
    for name, (requests, effects, outcome) in expected.items():
        case = wire_report["cases"][name]
        assert (case["physical_requests"], case["effects"], case["outcome"]) == (requests, effects, outcome)
        assert len(case["wire"]) == len(case["attempt_timeouts_s"]) == requests
    assert sum(case["physical_requests"] for case in wire_report["cases"].values()) == 15


def test_shared_permits_bound_nested_parallel_requests_not_nine(wire_report):
    case = wire_report["cases"]["parallel_nested"]
    assert case["root_operations"] == 3
    assert case["initial_retry_tokens"] == 2
    assert case["remaining_retry_tokens"] == 0
    assert {row["root"] for row in case["wire"]} == {0, 1, 2}
    assert len(case["waits_s"]) == 2
    inner = [row for row in case["events"] if ".inner." in row["operation"]]
    assert sum(row["outcome"] == "attempt" for row in inner) == 5
    assert all(row["attempt"] == 1 for row in inner)
    assert not any(row["outcome"] == "retry_wait" for row in inner)


def test_parse_outside_retry_and_accepted_sse_are_not_replayed(wire_report):
    malformed = wire_report["cases"]["bad_model_json"]
    assert malformed["errors"] == ["JSONDecodeError"]
    assert sum(row["outcome"] == "success" for row in malformed["events"]) == 1
    assert not any(row["outcome"] == "failure" for row in malformed["events"])
    stream = wire_report["cases"]["sse_partial"]
    assert stream["accepted_stream"] is True
    assert stream["sse_chunks"] == 1
    assert stream["physical_requests"] == 1
    assert stream["errors"] and stream["waits_s"] == []
    assert sum(row["outcome"] == "stream_open" for row in stream["events"]) == 1
    assert not any(row["outcome"] == "success" for row in stream["events"])


def test_deadline_clips_actual_wire_attempt_and_cleans_delayed_server_task(wire_report):
    case = wire_report["cases"]["deadline"]
    assert case["deadline_s"] == 0.04
    assert case["injected_delay_s"] == 0.2
    assert 0 < case["attempt_timeouts_s"][0] <= 0.04
    assert case["elapsed_s"] < 0.2
    assert case["physical_requests"] == 1 and case["waits_s"] == []
    assert wire_report["server_cleanup"]["pending_handlers"] == 0
    assert wire_report["server_cleanup"]["open_connections"] == 0
    assert wire_report["server_cleanup"]["unexpected_errors"] == []
    assert wire_report["server_cleanup"]["cancelled_handlers"] >= 1


def test_jitter_waits_and_remaining_permits_are_actual_core_events(wire_report):
    for case in wire_report["cases"].values():
        waits = [row["wait_s"] for row in case["events"] if row["outcome"] == "retry_wait"]
        assert case["waits_s"] == waits
        assert all(0 <= wait <= 0.01 for wait in waits)
        assert case["remaining_retry_tokens"] == 2 - len(waits)
    assert len(wire_report["cases"]["read_503"]["waits_s"]) == 2
    assert wire_report["cases"]["keyed_write"]["same_key"] is True


@pytest.mark.parametrize("case,field,value", [
    ("keyed_write", "effects", 2),
    ("keyed_write", "same_key", False),
    ("unsafe_write", "effects", 0),
    ("unsafe_write", "outcome", "resolved"),
    ("unsafe_write", "physical_requests", 2),
    ("auth_401", "physical_requests", 2),
    ("bad_model_json", "physical_requests", 2),
    ("parallel_nested", "physical_requests", 9),
    ("deadline", "physical_requests", 2),
    ("sse_partial", "physical_requests", 2),
    ("sse_partial", "sse_chunks", 0),
    ("read_503", "remaining_retry_tokens", -1),
    ("read_503", "physical_requests", True),
    ("read_503", "elapsed_s", float("nan")),
])
def test_report_rejects_duplicate_effects_improper_retry_and_invalid_counts(wire_report, case, field, value):
    report = deepcopy(wire_report)
    report["cases"][case][field] = value
    with pytest.raises(ValueError):
        evidence_module().validate_report(report)


def test_report_rejects_second_commit_even_with_self_consistent_wire_counts(wire_report):
    report = deepcopy(wire_report)
    case = report["cases"]["keyed_write"]
    case["wire"][1]["committed"] = True
    case["effects"] = 2
    with pytest.raises(ValueError):
        evidence_module().validate_report(report)


@pytest.mark.parametrize("mutation", ["missing_case", "source_hash", "cleanup", "url", "body", "event_url", "wait_nan", "live_claim"])
def test_report_rejects_incomplete_or_sensitive_evidence(wire_report, mutation):
    report = deepcopy(wire_report)
    case = report["cases"]["read_503"]
    if mutation == "missing_case":
        del report["cases"]["sse_partial"]
    elif mutation == "source_hash":
        report["sources_sha256"]["ai-service/app/resilience.py"] = "0" * 64
    elif mutation == "cleanup":
        report["server_cleanup"]["pending_handlers"] = 1
    elif mutation in ("url", "body"):
        case[mutation] = "http://private-address/credential-sentinel"
    elif mutation == "event_url":
        case["events"][0]["operation"] = "http://private-address/credential-sentinel"
    elif mutation == "wait_nan":
        case["waits_s"][0] = float("nan")
    else:
        report["scope"]["live_model_accuracy"] = True
    with pytest.raises(ValueError):
        evidence_module().validate_report(report)


def test_source_and_runtime_provenance_and_bounded_sanitized_output(wire_report):
    for path in ("eval/retry_evidence.py", "eval/tests/test_retry_evidence.py", "ai-service/app/resilience.py"):
        assert wire_report["sources_sha256"][path] == sha256((ROOT / path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    assert set(wire_report["versions"]) == {"python", "httpx", "httpcore", "anyio"}
    rendered = json.dumps(wire_report, allow_nan=False)
    assert len(rendered.encode()) < 65536
    assert not any(secret in rendered.lower() for secret in (
        "127.0.0.1", "localhost", "http://", "https://", "credential-sentinel", "bearer ", "data:",
    ))


def test_cli_is_isolated_from_config_models_credentials_and_proxy_settings(tmp_path):
    env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP") if key in os.environ}
    env.update({
        "HTTP_PROXY": "http://credential-sentinel@invalid.example:9",
        "HTTPS_PROXY": "http://credential-sentinel@invalid.example:9",
        "ALL_PROXY": "http://credential-sentinel@invalid.example:9",
        "SSL_CERT_FILE": "credential-sentinel-not-a-certificate",
        "OPENAI_API_KEY": "credential-sentinel",
        "PYTHONIOENCODING": "utf-8",
    })
    result = subprocess.run([sys.executable, "-B", str(ROOT / "eval/retry_evidence.py")],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=12)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    evidence_module().validate_report(report)
    assert len(result.stdout.encode()) < 65536
    assert "credential-sentinel" not in result.stdout + result.stderr
    # A guarded import also proves the runner has no application/config dependencies.
    script = f'''
import asyncio, importlib.abc, sys
sys.path.insert(0, {str(ROOT)!r})
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith("app.") and fullname != "app.resilience":
            raise AssertionError("forbidden application dependency")
sys.meta_path.insert(0, Guard())
from eval.retry_evidence import collect_report
asyncio.run(collect_report())
assert "app.config" not in sys.modules
print("isolated")
'''
    isolated = subprocess.run([sys.executable, "-B", "-c", script], cwd=tmp_path, env=env,
                              capture_output=True, text=True, timeout=12)
    assert isolated.returncode == 0, isolated.stderr
    assert isolated.stdout.strip() == "isolated"


def test_main_revalidates_and_publishes_nothing_on_corrupt_report(wire_report, monkeypatch, capsys):
    module = evidence_module()
    report = deepcopy(wire_report)
    report["cases"]["keyed_write"]["effects"] = 2

    async def corrupted():
        return report

    monkeypatch.setattr(module, "collect_report", corrupted)
    assert module.main([]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "ValueError" in captured.err


def test_main_does_not_leak_runtime_error_details(monkeypatch, capsys):
    module = evidence_module()

    async def broken():
        raise RuntimeError("http://private-address:123/credential-sentinel Bearer secret")

    monkeypatch.setattr(module, "collect_report", broken)
    assert module.main([]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "RuntimeError" in captured.err
    assert "private-address" not in captured.err and "secret" not in captured.err

@pytest.mark.parametrize("mutation", ["nested_attempt", "success_for_partial_stream", "uncorrelated_wait", "unclipped_timeout", "missing_wire"])
def test_report_rejects_unproven_core_events_even_when_top_counts_look_valid(wire_report, mutation):
    report = deepcopy(wire_report)
    if mutation == "nested_attempt":
        event = next(row for row in report["cases"]["parallel_nested"]["events"] if ".inner." in row["operation"])
        event["attempt"] = 2
    elif mutation == "success_for_partial_stream":
        event = next(row for row in report["cases"]["sse_partial"]["events"] if row["outcome"] == "stream_open")
        event["outcome"] = "success"
    elif mutation == "uncorrelated_wait":
        report["cases"]["keyed_write"]["waits_s"] = [0.0099]
    elif mutation == "unclipped_timeout":
        report["cases"]["deadline"]["attempt_timeouts_s"] = [0.2]
    else:
        report["cases"]["read_503"]["wire"] = []
    with pytest.raises(ValueError):
        evidence_module().validate_report(report)


def test_cancelled_collection_cleans_server_connections_and_child_tasks(monkeypatch):
    module = evidence_module()
    original = module._case
    holder = {}

    async def observed_case(server, name):
        if name == "deadline":
            holder["server"] = server
        return await original(server, name)

    monkeypatch.setattr(module, "_case", observed_case)

    async def scenario():
        existing = set(asyncio.all_tasks())
        collection = asyncio.create_task(module.collect_report())
        async with asyncio.timeout(3):
            while "server" not in holder or not holder["server"].wire["deadline"]:
                await asyncio.sleep(0)
        collection.cancel()
        with pytest.raises(asyncio.CancelledError):
            await collection
        await asyncio.sleep(0)
        assert not [task for task in asyncio.all_tasks() - existing if not task.done()]
        assert holder["server"].cleanup()["pending_handlers"] == 0
        assert holder["server"].cleanup()["open_connections"] == 0

    asyncio.run(scenario())

@pytest.mark.parametrize("value", ["credential-sentinel", "0.0.0"])
def test_report_rejects_unverified_runtime_version_metadata(wire_report, value):
    report = deepcopy(wire_report)
    report["versions"]["httpx"] = value
    with pytest.raises(ValueError):
        evidence_module().validate_report(report)


def test_source_fingerprints_and_validator_accept_lf_crlf_but_not_content_changes(wire_report, tmp_path, monkeypatch):
    module = evidence_module()
    originals = {path: (ROOT / path).read_bytes().replace(b"\r\n", b"\n")
                 for path in wire_report["sources_sha256"]}
    for path, data in originals.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module.resilience, "__file__", str(tmp_path / "ai-service/app/resilience.py"))
    expected = {path: sha256(data).hexdigest() for path, data in originals.items()}
    assert module._source_hashes() == expected
    module.validate_report(wire_report)
    for path, data in originals.items():
        (tmp_path / path).write_bytes(data.replace(b"\n", b"\r\n"))
    assert module._source_hashes() == expected
    module.validate_report(wire_report)
    target = tmp_path / "ai-service/app/resilience.py"
    target.write_bytes(target.read_bytes() + b"# real source change\r\n")
    assert module._source_hashes() != expected
    with pytest.raises(ValueError, match="source provenance"):
        module.validate_report(wire_report)


@pytest.mark.parametrize("mode", [None, "raw-bytes", "utf8", True])
def test_report_rejects_missing_or_unsupported_source_hash_mode(wire_report, mode):
    report = deepcopy(wire_report)
    if mode is None:
        report.pop("source_hash_mode", None)
    else:
        report["source_hash_mode"] = mode
    with pytest.raises(ValueError):
        evidence_module().validate_report(report)


def test_collected_report_declares_utf8_lf_source_hash_mode(wire_report):
    assert wire_report["source_hash_mode"] == "utf8-lf"
