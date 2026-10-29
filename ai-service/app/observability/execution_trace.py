"""Bounded application diagnostics; no dependency on the optional Langfuse exporter.

Captures public inputs/outputs, never provider reasoning or arbitrary objects.
A recorder is request-local and shared with child tasks through ContextVar.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import json
import math
import re
import time
from uuid import uuid4

_current = ContextVar("execution_trace", default=None)
_parent = ContextVar("execution_parent", default=None)
_PRIVATE = re.compile(r"password|passwd|authorization|api[_-]?key|secret|access[_-]?token|refresh[_-]?token|internal[_-]?token|reasoning|thinking|chain_of_thought|additional_kwargs|phone|email|address", re.I)
_NODES = {"intent_router", "agent", "tools", "small_talk", "web_answer", "escalate_node", "finalize_without_tools"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def safe_data(value, depth=0):
    if depth > 6:
        return "[depth limit]"
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        original_length = len(value)
        value = value[:4000]  # Bound work before running redaction regexes.
        value = re.sub(r"(?is)<think>.*?(?:</think>|$)", "[REDACTED]", value)
        text = re.sub(r"(?i)Bearer\s+[^\s,;，；]+", "Bearer [REDACTED]", value)
        text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
        text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[PHONE]", text)
        text = re.sub(r"\b(?:sk-|tvly-)[A-Za-z0-9_-]{8,}", "[SECRET]", text)
        text = re.sub(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[JWT]", text)
        text = re.sub('(?i)(?:api[_-]?key|password|internal[_-]?token)["\']?\\s*[:=]\\s*["\']?[^\\s,;"\']+', "[SECRET]", text)
        return text[:1800] + ("…[truncated]" if original_length > 1800 else "")
    if hasattr(value, "content") and hasattr(value, "type"):
        # Deliberately exclude additional_kwargs/response_metadata (may contain CoT).
        return safe_data({"role":value.type, "content":value.content,
                          "tool_calls":getattr(value, "tool_calls", None)}, depth+1)
    if is_dataclass(value) and not isinstance(value, type):
        return safe_data(asdict(value), depth+1)
    if isinstance(value, dict):
        if value.get("type") in {"reasoning", "thinking"}:
            return "[REDACTED]"
        return {str(k): "[REDACTED]" if _PRIVATE.search(str(k)) else safe_data(v, depth+1)
                for k,v in list(value.items())[:24]}
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        result = [safe_data(v, depth+1) for v in items[:20]]
        if len(items) > 20: result.append({"omittedItems": len(items)-20})
        return result
    return f"[{type(value).__name__}]"


def _bounded(value):
    result = safe_data(value)
    encoded = json.dumps(result, ensure_ascii=False)
    return result if len(encoded) <= 6000 else {"preview":encoded[:6000], "truncated":True}


class TraceRecorder:
    def __init__(self, trace_id):
        self.trace_id = trace_id
        self.started_at = _now()
        self.started = time.perf_counter()
        self.finished = None
        self.stages = []
        self.active = {}
        self.omitted = 0

    def start(self, name, *, kind="stage", input=None, parent_id=None, run_id=None, model=None):
        if len(self.stages) >= 96:
            self.omitted += 1
            return None
        key = str(run_id or uuid4().hex)
        stage = {"id":key, "parentId":parent_id, "name":name, "kind":kind,
                 "status":"RUNNING", "startMs":round((time.perf_counter()-self.started)*1000, 2),
                 "input":_bounded(input), "_started":time.perf_counter()}
        if isinstance(model, str): stage["model"] = model
        self.stages.append(stage)
        self.active[key] = stage
        return key

    def end(self, key, *, output=None, status="SUCCESS", error=None, usage=None):
        stage = self.active.pop(key, None)
        if stage is None: return
        stage["durationMs"] = round((time.perf_counter()-stage.pop("_started"))*1000, 2)
        stage.update(status=status, output=_bounded(output))
        if error: stage["error"] = safe_data(str(error))
        if isinstance(usage, dict): stage["usage"] = safe_data(usage)

    def observe(self, event):
        kind, name = event.get("event", ""), event.get("name", "")
        run_id, data = str(event.get("run_id", "")), event.get("data") or {}
        if not run_id: return
        category = "model" if kind.startswith("on_chat_model_") else "tool" if kind.startswith("on_tool_") else "node"
        if category == "node" and name not in _NODES: return
        if kind.endswith("_start"):
            parent = next((str(p) for p in reversed(event.get("parent_ids") or []) if str(p) in self.active), None)
            model = (event.get("metadata") or {}).get("ls_model_name")
            self.start(name, kind=category, input=data.get("input"), parent_id=parent, run_id=run_id, model=model)
        elif kind.endswith("_end"):
            value = data.get("output")
            usage = getattr(value, "usage_metadata", None)
            if category == "tool" and isinstance(getattr(value, "content", None), str):
                try:
                    value = json.loads(value.content)
                except (TypeError, ValueError):
                    pass
            failure = isinstance(value, dict) and value.get("error")
            self.end(run_id, output=value, usage=usage, status="FAILED" if failure else "SUCCESS")
        elif kind.endswith("_error"):
            self.end(run_id, error=data.get("error", "execution failed"), status="FAILED")

    def snapshot(self, status, *, error=None):
        if self.finished is None:
            self.finished = _now()
            self.duration = round((time.perf_counter()-self.started)*1000, 2)
        for key in list(self.active):
            self.end(key, status="CANCELLED" if status == "CANCELLED" else "FAILED", error=error or "step did not complete")
        stages = [dict(s) for s in self.stages]
        omitted = self.omitted
        while len(json.dumps(stages, ensure_ascii=False).encode()) > 240000:
            stages.pop()
            omitted += 1
        return {"schemaVersion":1, "traceId":self.trace_id, "status":status,
                "startedAt":self.started_at, "finishedAt":self.finished, "updatedAt":_now(),
                "durationMs":self.duration, "stages":stages, "omittedStages":omitted,
                "error":safe_data(error)}


@contextmanager
def activate_trace(record):
    token = _current.set(record)
    parent = _parent.set(None)
    try: yield record
    finally:
        _parent.reset(parent)
        _current.reset(token)


@contextmanager
def trace_span(name, *, kind="stage", input=None, model=None):
    record = _current.get()
    key = record.start(name, kind=kind, input=input, model=model, parent_id=_parent.get()) if record else None
    token = _parent.set(key)
    class Span:
        output = None
        status = "SUCCESS"
        def complete(self, output=None, *, status="SUCCESS"):
            self.output, self.status = output, status
    span = Span()
    try:
        yield span
    except BaseException as exc:
        if record: record.end(key, status="FAILED", error=type(exc).__name__)
        raise
    else:
        if record:
            usage = span.output.get("usage") if isinstance(span.output, dict) else None
            record.end(key, output=span.output, status=span.status, usage=usage)
    finally:
        _parent.reset(token)
