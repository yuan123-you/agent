"""Actual local TCP fault injection, not live-model accuracy or production SLA evidence.

Safe default: ``python eval/retry_evidence.py`` emits validated JSON to stdout.
There are no destination, credential, model, or output-file options. Business
writes affect only a synthetic in-memory ledger. Fault schedules/counts are
reproducible; elapsed times and Full Jitter samples are measured, not seeded.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import suppress
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
import math
from pathlib import Path
import platform
import sys
from time import monotonic

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai-service"))
from app import resilience

MAX_REPORT_BYTES = 65536
_SCOPE = {
    "business_ledger": "synthetic_in_memory",
    "external_services_used": False,
    "live_model_accuracy": False,
    "production_outage_or_sla": False,
    "time_basis": "relative_monotonic_seconds",
}
# Expected physical observations, not values substituted into collected evidence.
_EXPECTED = {
    "read_503": (3, 0, "success", [503, 503, 200], 2),
    "auth_401": (1, 0, "rejected", [401], 0),
    "bad_model_json": (1, 0, "malformed_json", [200], 0),
    "unsafe_write": (1, 1, "unresolved", [None], 0),
    "keyed_write": (2, 1, "resolved", [None, 200], 1),
    "parallel_nested": (5, 0, "bounded_failure", [503] * 5, 2),
    "sse_partial": (1, 0, "partial_stream_failed", [200], 0),
    "deadline": (1, 0, "deadline_exceeded", [None], 0),
}


def _source_hashes():
    if Path(resilience.__file__).resolve() != ROOT / "ai-service/app/resilience.py":
        raise ValueError("unexpected resilience module")
    return {path: sha256((ROOT / path).read_bytes().replace(b"\r\n", b"\n")).hexdigest() for path in (
        "eval/retry_evidence.py", "eval/tests/test_retry_evidence.py", "ai-service/app/resilience.py",
    )}


def _runtime_versions():
    return {"python": platform.python_version(), **{name: version(name) for name in ("httpx", "httpcore", "anyio")}}


class _LoopbackServer:
    """A deliberately tiny, bounded HTTP/1.1 peer; never a general-purpose server."""

    def __init__(self):
        self.wire = {name: [] for name in _EXPECTED}
        self.effects = {name: 0 for name in _EXPECTED}
        self.keys = []
        self.ledger = set()
        self.tasks = set()
        self.writers = set()
        self.cancelled_handlers = 0
        self.unexpected_errors = []

    async def __aenter__(self):
        self.server = await asyncio.start_server(self._accept, "127.0.0.1", 0, limit=8192)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    def _accept(self, reader, writer):
        self.writers.add(writer)
        task = asyncio.create_task(self._handle(reader, writer))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def __aexit__(self, *exc):
        self.server.close()
        # Newer asyncio servers wait for active transports in wait_closed().
        # Cancel delayed handlers first so cleanup does not wait out injected faults.
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        async with asyncio.timeout(1.0):
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await self.server.wait_closed()
        await asyncio.sleep(0)

    def cleanup(self):
        return {
            "pending_handlers": sum(not task.done() for task in self.tasks),
            "open_connections": len(self.writers),
            "cancelled_handlers": self.cancelled_handlers,
            "unexpected_errors": list(self.unexpected_errors),
        }

    def url(self, name, root=0):
        if name not in _EXPECTED or type(root) is not int or not 0 <= root < 3:
            raise ValueError("unknown local scenario")
        return f"http://127.0.0.1:{self.port}/{name}/{root}"

    async def _handle(self, reader, writer):
        try:
            async with asyncio.timeout(0.5):
                head = await reader.readuntil(b"\r\n\r\n")
                lines = head.split(b"\r\n")
                method, path, protocol = lines[0].decode("ascii").split()
                headers = dict(line.decode("ascii").split(":", 1) for line in lines[1:] if line)
                headers = {key.lower(): value.strip() for key, value in headers.items()}
                length = int(headers.get("content-length", "0"))
                if not 0 <= length <= 512 or protocol != "HTTP/1.1":
                    raise ValueError("invalid local request")
                await reader.readexactly(length)
                _, name, raw_root = path.split("/")
                root = int(raw_root)
                if name not in _EXPECTED or not 0 <= root < 3:
                    raise ValueError("invalid local route")
                key = headers.get("idempotency-key")
                row = {"root": root, "method": method, "status": None,
                       "committed": False, "key_present": key is not None}
                self.wire[name].append(row)
                number = len(self.wire[name])

                if name in ("unsafe_write", "keyed_write"):
                    if name == "unsafe_write" or key not in self.ledger:
                        self.effects[name] += 1
                        row["committed"] = True
                        if name == "keyed_write":
                            self.ledger.add(key)
                            self.keys.append(key)
                        # The synthetic effect is committed; no HTTP acknowledgement.
                        return
                    self.keys.append(key)
                if name == "deadline":
                    await asyncio.sleep(0.2)
                if name == "sse_partial":
                    row["status"] = 200
                    first = b"data: synthetic-first\n\n"
                    writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
                                 b"Transfer-Encoding: chunked\r\nConnection: close\r\n\r\n"
                                 + f"{len(first):x}\r\n".encode() + first + b"\r\n")
                    await writer.drain()
                    await asyncio.sleep(0.005)
                    # A second chunk is truncated and there is no terminating zero chunk.
                    writer.write(b"40\r\ndata: truncated")
                    await writer.drain()
                    return

                status = 503 if name == "parallel_nested" or name == "read_503" and number <= 2 else 200
                if name == "auth_401":
                    status = 401
                body = b"not-json" if name == "bad_model_json" else b'{"ok":true}'
                row["status"] = status
                writer.write(f"HTTP/1.1 {status} Local\r\nContent-Type: application/json\r\n"
                             f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode() + body)
                await writer.drain()
        except asyncio.CancelledError:
            self.cancelled_handlers += 1
            raise
        except Exception as error:
            self.unexpected_errors.append(type(error).__name__)
        finally:
            writer.close()
            with suppress(ConnectionError, TimeoutError):
                async with asyncio.timeout(0.1):
                    await writer.wait_closed()
            self.writers.discard(writer)


class _ObservedTransport(httpx.AsyncBaseTransport):
    """Real HTTP transport with a hard local-only guard and numeric observations."""

    def __init__(self, server):
        self.port = server.port
        self.timeouts = []
        self.inner = httpx.AsyncHTTPTransport(retries=0, trust_env=False)

    async def handle_async_request(self, request):
        if request.url.scheme != "http" or request.url.host != "127.0.0.1" or request.url.port != self.port:
            raise ValueError("non-loopback destination prohibited")
        self.timeouts.append(request.extensions["timeout"]["read"])
        return await self.inner.handle_async_request(request)

    async def aclose(self):
        await self.inner.aclose()


async def _case(server, name):
    deadline = 0.04 if name == "deadline" else 1.0
    observed = _ObservedTransport(server)
    transport = observed
    if name == "sse_partial":
        transport = resilience.ResilientAsyncTransport(
            "evidence.sse_partial", replay_safe=True, timeout_s=0.5, transport=observed,
        )
    errors = []
    outcome = "unexpected"
    accepted_stream, chunks = False, 0
    async with httpx.AsyncClient(transport=transport, trust_env=False, timeout=0.5) as client:
        with resilience.budget_scope(deadline, retry_tokens=2, inherit=False) as budget:
            started = monotonic()

            async def request(timeout, root=0):
                if name in ("unsafe_write", "keyed_write"):
                    headers = {"Idempotency-Key": "synthetic-stable-key"} if name == "keyed_write" else {}
                    response = await client.post(server.url(name, root), headers=headers,
                                                 content=b"synthetic-effect", timeout=timeout)
                else:
                    response = await client.get(server.url(name, root), timeout=timeout)
                response.raise_for_status()
                return response

            async def policy(operation, call, *, safe=True, attempt_timeout=0.5):
                return await resilience.run(operation, call, replay_safe=safe, max_attempts=3,
                                            attempt_timeout_s=attempt_timeout, total_timeout_s=deadline,
                                            base_delay_s=0.005, max_delay_s=0.01)

            if name == "parallel_nested":
                async def root_operation(root):
                    async def outer(timeout):
                        async def inner(inner_timeout):
                            return await request(inner_timeout, root)
                        return await policy(f"evidence.parallel_nested.inner.{root}", inner,
                                            attempt_timeout=timeout)
                    return await policy(f"evidence.parallel_nested.root.{root}", outer)

                results = await asyncio.gather(*(root_operation(root) for root in range(3)), return_exceptions=True)
                errors = [type(result).__name__ for result in results if isinstance(result, BaseException)]
                outcome = "bounded_failure" if len(errors) == 3 else "unexpected"
            else:
                try:
                    if name == "sse_partial":
                        async with client.stream("GET", server.url(name)) as response:
                            response.raise_for_status()
                            accepted_stream = True
                            async for line in response.aiter_lines():
                                if line.startswith("data:"):
                                    chunks += 1
                        outcome = "unexpected"
                    else:
                        response = await policy("evidence." + name, request, safe=name != "unsafe_write")
                        if name == "bad_model_json":
                            # A completed HTTP attempt has already left the retry owner.
                            response.json()
                        outcome = "resolved" if name == "keyed_write" else "success"
                except (httpx.HTTPError, resilience.DeadlineExceeded, json.JSONDecodeError) as error:
                    errors.append(type(error).__name__)
                    outcome = {
                        "auth_401": "rejected", "bad_model_json": "malformed_json",
                        "unsafe_write": "unresolved", "deadline": "deadline_exceeded",
                        "sse_partial": "partial_stream_failed",
                    }.get(name, "unexpected")
            elapsed = monotonic() - started
            remaining = budget.remaining()

    return {
        "physical_requests": len(server.wire[name]), "wire": server.wire[name],
        "effects": server.effects[name], "outcome": outcome, "errors": errors,
        "root_operations": 3 if name == "parallel_nested" else 1,
        "same_key": bool(server.keys and len(set(server.keys)) == 1) if name == "keyed_write" else None,
        "accepted_stream": accepted_stream, "sse_chunks": chunks,
        "deadline_s": deadline, "injected_delay_s": 0.2 if name == "deadline" else 0.0,
        "elapsed_s": elapsed, "remaining_s": remaining,
        "initial_retry_tokens": 2, "remaining_retry_tokens": budget.retry_tokens_remaining,
        "attempt_timeouts_s": observed.timeouts,
        "waits_s": [row["wait_s"] for row in budget.events if row["outcome"] == "retry_wait"],
        "events": list(budget.events),
    }


async def collect_report():
    """Exercise fixed local faults; publish nothing unless all invariants hold."""
    sources = _source_hashes()
    started = monotonic()
    async with asyncio.timeout(5.0):
        async with _LoopbackServer() as server:
            cases = {name: await _case(server, name) for name in _EXPECTED}
    report = {
        "schema_version": 1, "evidence_kind": "actual_loopback_tcp_fault_injection",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "scope": dict(_SCOPE),
        "sources_sha256": sources, "source_hash_mode": "utf8-lf",
        "versions": _runtime_versions(),
        "total_elapsed_s": monotonic() - started, "cases": cases, "server_cleanup": server.cleanup(),
    }
    validate_report(report)
    return report


def _require(condition, invariant):
    if not condition:
        raise ValueError("retry evidence rejected: " + invariant)


def _keys(value, expected, invariant):
    _require(type(value) is dict and set(value) == set(expected), invariant)


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def _number(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def validate_report(report):
    """Fail closed on wrong effects/retries, unproven claims, or sensitive fields."""
    try:
        _validate_report(report)
    except (KeyError, TypeError, AttributeError, OverflowError):
        raise ValueError("retry evidence rejected: invalid schema") from None


def _validate_report(report):
    _keys(report, ("schema_version", "evidence_kind", "generated_at_utc", "scope", "sources_sha256", "source_hash_mode",
                   "versions", "total_elapsed_s", "cases", "server_cleanup"), "report fields")
    _require(type(report["schema_version"]) is int and report["schema_version"] == 1, "schema version")
    _require(report["evidence_kind"] == "actual_loopback_tcp_fault_injection", "wire evidence kind")
    _require(report["scope"] == _SCOPE, "synthetic/local scope")
    stamp = datetime.fromisoformat(report["generated_at_utc"])
    _require(stamp.utcoffset() is not None and stamp.utcoffset().total_seconds() == 0, "UTC timestamp")
    _require(report["source_hash_mode"] == "utf8-lf", "source hash mode")
    _require(report["sources_sha256"] == _source_hashes(), "source provenance")
    _keys(report["versions"], ("python", "httpx", "httpcore", "anyio"), "runtime versions")
    _require(report["versions"] == _runtime_versions(), "runtime provenance")
    _require(all(type(value) is str and 0 < len(value) <= 64 and all(c.isalnum() or c in ".+-" for c in value)
                 for value in report["versions"].values()), "bounded version values")
    _require(_number(report["total_elapsed_s"], 0, 6.0), "total deadline")
    _keys(report["cases"], _EXPECTED, "complete scenario set")
    cleanup = report["server_cleanup"]
    _keys(cleanup, ("pending_handlers", "open_connections", "cancelled_handlers", "unexpected_errors"), "cleanup fields")
    _require(type(cleanup["pending_handlers"]) is int and cleanup["pending_handlers"] == 0
             and type(cleanup["open_connections"]) is int and cleanup["open_connections"] == 0
             and _integer(cleanup["cancelled_handlers"], 1, 15) and cleanup["unexpected_errors"] == [], "clean server shutdown")
    fields = ("physical_requests", "wire", "effects", "outcome", "errors", "root_operations", "same_key",
              "accepted_stream", "sse_chunks", "deadline_s", "injected_delay_s", "elapsed_s", "remaining_s",
              "initial_retry_tokens", "remaining_retry_tokens", "attempt_timeouts_s", "waits_s", "events")
    for name, (requests, effects, outcome, statuses, retries) in _EXPECTED.items():
        case = report["cases"][name]
        _keys(case, fields, "scenario fields")
        _require(type(case["physical_requests"]) is int and case["physical_requests"] == requests, "physical request bound")
        _require(type(case["effects"]) is int and case["effects"] == effects, "synthetic effect count")
        _require(case["outcome"] == outcome, "honest outcome")
        _require(type(case["wire"]) is list and len(case["wire"]) == requests, "wire count")
        for index, row in enumerate(case["wire"]):
            _keys(row, ("root", "method", "status", "committed", "key_present"), "wire fields")
            _require(_integer(row["root"], 0, 2 if name == "parallel_nested" else 0), "wire root")
            _require(row["method"] == ("POST" if name in ("unsafe_write", "keyed_write") else "GET"), "HTTP method")
            _require(row["status"] is None if statuses[index] is None else type(row["status"]) is int
                     and row["status"] == statuses[index], "wire status sequence")
            _require(row["committed"] is (name in ("unsafe_write", "keyed_write") and index == 0), "ledger commit sequence")
            _require(row["key_present"] is (name == "keyed_write"), "key usage")
        _require(sum(row["committed"] for row in case["wire"]) == effects, "observed ledger effects")
        _require(case["same_key"] is (True if name == "keyed_write" else None), "stable replay key")
        roots = 3 if name == "parallel_nested" else 1
        _require(type(case["root_operations"]) is int and case["root_operations"] == roots, "root operation count")
        _require(case["accepted_stream"] is (name == "sse_partial") and type(case["sse_chunks"]) is int
                 and case["sse_chunks"] == (1 if name == "sse_partial" else 0), "accepted partial SSE")
        deadline = 0.04 if name == "deadline" else 1.0
        _require(_number(case["deadline_s"], deadline, deadline)
                 and _number(case["injected_delay_s"], 0.2 if name == "deadline" else 0, 0.2 if name == "deadline" else 0), "configured deadline/fault")
        _require(_number(case["elapsed_s"], 0, 0.199 if name == "deadline" else 1.05)
                 and _number(case["remaining_s"], 0, deadline), "measured deadline")
        _require(type(case["initial_retry_tokens"]) is int and case["initial_retry_tokens"] == 2
                 and type(case["remaining_retry_tokens"]) is int and case["remaining_retry_tokens"] == 2 - retries, "shared permit ledger")
        _require(type(case["attempt_timeouts_s"]) is list and len(case["attempt_timeouts_s"]) == requests
                 and all(_number(value, 0, min(0.5, deadline)) and value > 0 for value in case["attempt_timeouts_s"]), "clipped wire timeouts")
        _validate_events(name, case, requests, retries, deadline)
        errors = case["errors"]
        _require(type(errors) is list, "error types")
        if name in ("read_503", "keyed_write"):
            _require(errors == [], "recovered outcome")
        elif name == "parallel_nested":
            _require(len(errors) == 3 and all(error in ("HTTPStatusError", "RetryBudgetExhausted") for error in errors)
                     and "RetryBudgetExhausted" in errors, "bounded parallel failures")
            _require({row["root"] for row in case["wire"]} == {0, 1, 2}
                     and all(sum(row["root"] == root for row in case["wire"]) <= 3 for root in range(3)), "three bounded roots")
        else:
            allowed = {"auth_401": ("HTTPStatusError",), "bad_model_json": ("JSONDecodeError",),
                       "unsafe_write": ("RemoteProtocolError", "ReadError"), "deadline": ("DeadlineExceeded",),
                       "sse_partial": ("RemoteProtocolError", "ReadError")}[name]
            _require(len(errors) == 1 and errors[0] in allowed, "observed failure type")
    _require(len(json.dumps(report, allow_nan=False, indent=2, sort_keys=True).encode("utf-8")) + 1 <= MAX_REPORT_BYTES, "bounded report size")


def _validate_events(name, case, requests, retries, deadline):
    events = case["events"]
    _require(type(events) is list and 1 <= len(events) <= 64, "bounded core events")
    permits = 2
    for row in events:
        _keys(row, ("operation", "attempt", "outcome", "category", "wait_s", "remaining_s", "retry_tokens_remaining"), "event fields")
        operations = {"evidence." + name} if name != "parallel_nested" else {
            f"evidence.parallel_nested.{kind}.{root}" for kind in ("root", "inner") for root in range(3)
        }
        _require(row["operation"] in operations and _integer(row["attempt"], 1, 3), "bounded operation/attempt")
        _require(row["outcome"] in ("attempt", "success", "stream_open", "failure", "retry_wait", "permits_exhausted", "deadline_refused"), "event outcome")
        _require(row["category"] in (None, "transport", "disconnect_before_response", "timeout", "unsafe_replay", "http_401", "http_503"), "event category")
        _require(_number(row["remaining_s"], 0, deadline) and _integer(row["retry_tokens_remaining"], 0, permits), "event budget")
        permits = row["retry_tokens_remaining"]
        cap = min(0.01, 0.005 * 2 ** (row["attempt"] - 1)) if row["outcome"] == "retry_wait" else 0
        _require(_number(row["wait_s"], 0, cap), "jitter cap")
        if ".inner." in row["operation"]:
            _require(row["attempt"] == 1 and row["outcome"] != "retry_wait", "nested single ownership")
    waits = [row["wait_s"] for row in events if row["outcome"] == "retry_wait"]
    _require(type(case["waits_s"]) is list and case["waits_s"] == waits and len(waits) == retries
             and permits == case["remaining_retry_tokens"], "raw waits/permits")
    multiplier = 2 if name == "parallel_nested" else 1
    _require(sum(row["outcome"] == "attempt" for row in events) == requests * multiplier, "core versus wire attempts")
    successes = 1 if name in ("read_503", "bad_model_json", "keyed_write") else 0
    streams = 1 if name == "sse_partial" else 0
    _require(sum(row["outcome"] == "success" for row in events) == successes
             and sum(row["outcome"] == "stream_open" for row in events) == streams
             and sum(row["outcome"] == "failure" for row in events) == requests * multiplier - successes - streams,
             "HTTP outcomes before parsing/stream consumption")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        report = asyncio.run(collect_report())
        validate_report(report)  # Also defend the publication boundary.
        rendered = json.dumps(report, allow_nan=False, indent=2, sort_keys=True) + "\n"
        _require(len(rendered.encode("utf-8")) <= MAX_REPORT_BYTES, "bounded publication")
    except Exception as error:
        # Exception messages/tracebacks can include destinations or request bodies.
        print("Retry evidence failed: " + type(error).__name__, file=sys.stderr)
        return 1
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
