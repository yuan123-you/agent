"""SPEC-06: incomplete live replays must never become successful eval results."""
import json

import pytest

from eval import live_eval


class SseResponse:
    def __init__(self, lines):
        self.lines = lines

    def __enter__(self):
        return iter(self.lines)

    def __exit__(self, *args):
        return False


def frame(event, payload):
    return [f"event: {event}\n", "data: " + json.dumps(payload) + "\n", "\n"]


def run_response(monkeypatch, lines):
    monkeypatch.setattr(live_eval.urllib.request, "urlopen", lambda *args, **kwargs: SseResponse(lines))
    return live_eval.LiveClient("http://offline.invalid", "synthetic-token", 7).run("query", 900000)


@pytest.mark.parametrize("lines", [
    [],
    frame("token", {"content": "partial answer"}),
    frame("tool_call", {"tool": "product_search", "args": {"category": "PHONE"}}),
    frame("tool_call", {"tool": "product_search"}) + frame("tool_result", {"tool": "product_search"}),
])
def test_live_client_rejects_eof_without_terminal_done(monkeypatch, lines):
    with pytest.raises(RuntimeError, match="terminal done"):
        run_response(monkeypatch, lines)


def test_incomplete_replay_cannot_report_perfect_tool_metrics(monkeypatch):
    lines = frame("tool_call", {"tool": "product_search", "args": {"category": "PHONE"}})
    monkeypatch.setattr(live_eval.urllib.request, "urlopen", lambda *args, **kwargs: SseResponse(lines))
    client = live_eval.LiveClient("http://offline.invalid", "synthetic-token", 7)
    datasets = {"intent": [], "rag": [], "reply": [], "tool": [{
        "input": "query", "expected_tools": ["product_search"], "expected_args": {"category": "PHONE"},
    }]}

    with pytest.raises(RuntimeError, match="terminal done"):
        live_eval.evaluate_live(client, datasets)


def test_live_client_rejects_timed_out_done_instead_of_scoring_partial_output(monkeypatch):
    with pytest.raises(RuntimeError, match="timed out"):
        run_response(monkeypatch, frame("done", {"content": "partial", "timedOut": True}))


def test_live_client_preserves_explicit_provider_error(monkeypatch):
    with pytest.raises(RuntimeError, match="provider unavailable"):
        run_response(monkeypatch, frame("error", {"message": "provider unavailable"}))


def test_live_client_preserves_malformed_final_payload_error(monkeypatch):
    with pytest.raises(json.JSONDecodeError):
        run_response(monkeypatch, ["event: done\n", 'data: {"content":'])


def test_live_client_accepts_explicit_done_at_eof_and_keeps_metadata(monkeypatch):
    done = {"content": "complete", "intent": "PRODUCT_CONSULT", "latencyMs": 123,
            "tokenUsage": {"promptTokens": 4, "completionTokens": 2}}
    lines = frame("tool_call", {"tool": "product_search", "args": {"category": "PHONE"}})
    lines += frame("done", done)[:-1]

    result = run_response(monkeypatch, lines)

    assert result["done"] == done
    assert result["tool_calls"] == [{"tool": "product_search", "args": {"category": "PHONE"}}]
