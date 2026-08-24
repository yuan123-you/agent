"""Live replay client and metrics for the deployed AI Mall Agent."""
from __future__ import annotations

import json
import math
import urllib.request
from dataclasses import dataclass
from typing import Iterable


def parse_sse(lines: Iterable[bytes | str]) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    event = "message"
    data: list[str] = []
    for raw in lines:
        line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        line = line.rstrip("\r\n")
        if not line:
            if data:
                events.append((event, json.loads("\n".join(data))))
            event, data = "message", []
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].strip())
    if data:
        events.append((event, json.loads("\n".join(data))))
    return events


@dataclass
class LiveClient:
    base_url: str
    internal_token: str
    user_id: int
    timeout: float = 180.0

    def run(self, text: str, conversation_id: int) -> dict:
        body = json.dumps({
            "conversation_id": conversation_id,
            "user_id": self.user_id,
            "message": text,
            "history": [],
            "options": {"include_eval_metadata": True},
        }, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.base_url.rstrip("/") + "/v1/chat/stream",
            data=body,
            headers={"Content-Type": "application/json", "X-Internal-Token": self.internal_token},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            events = parse_sse(response)
        result = {"tool_calls": [], "tool_results": [], "done": {}}
        for name, payload in events:
            if name == "tool_call":
                result["tool_calls"].append(payload)
            elif name == "tool_result":
                result["tool_results"].append(payload)
            elif name == "done":
                result["done"] = payload
            elif name == "error":
                raise RuntimeError(payload.get("message", "live Agent evaluation failed"))
        return result


def _percentile(values: list[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def evaluate_live(client, datasets: dict[str, list[dict]], conversation_start: int = 900000) -> dict:
    cache: dict[str, dict] = {}

    def replay(text: str) -> dict:
        if text not in cache:
            cache[text] = client.run(text, conversation_start + len(cache))
        return cache[text]

    intents = datasets["intent"]
    intent_hits = sum(replay(case["input"])["done"].get("intent") == case["expected"] for case in intents)

    tool_cases = datasets["tool"]
    tool_hits = arg_hits = 0
    for case in tool_cases:
        calls = replay(case["input"])["tool_calls"]
        expected_tools = set(case.get("expected_tools") or [])
        actual_tools = {call.get("tool") for call in calls}
        tool_hits += expected_tools.issubset(actual_tools)
        expected_args = case.get("expected_args") or {}
        if not expected_args:
            arg_hits += 1
        else:
            arg_hits += any(all(call.get("args", {}).get(k) == str(v) or call.get("args", {}).get(k) == v
                                for k, v in expected_args.items()) for call in calls)

    rag_cases = datasets["rag"]
    rag_hits = 0
    reciprocal_sum = 0.0
    for case in rag_cases:
        results = replay(case["query"])["tool_results"]
        product_lists = [item.get("eval", {}).get("products", []) for item in results
                         if item.get("tool") == "product_search"]
        expected = set(case.get("must_hit") or [])
        expected_category = case.get("expected_category")
        exact_ranks = [product.get("rank", rank) for products in product_lists
                       for rank, product in enumerate(products[:5], 1)
                       if product.get("name") in expected]
        category_ranks = [product.get("rank", rank) for products in product_lists
                          for rank, product in enumerate(products[:5], 1)
                          if expected_category and product.get("category") == expected_category]
        rank = min(exact_ranks or category_ranks, default=None)
        hit = rank is not None
        if not case.get("expect_hit", True):
            hit = not any(product_lists)
        rag_hits += hit
        reciprocal_sum += 1.0 / rank if rank else 0.0

    reply_cases = datasets["reply"]
    reply_total = 0.0
    for case in reply_cases:
        content = replay(case["input"])["done"].get("content", "")
        expected = case.get("expected_keywords") or []
        reply_total += sum(keyword in content for keyword in expected) / len(expected) if expected else 1.0

    citations = [hit for result in cache.values() for item in result["tool_results"]
                 if item.get("tool") == "kb_search" for hit in item.get("eval", {}).get("hits", [])]
    citation_coverage = (sum(bool(hit.get("source")) for hit in citations) / len(citations)) if citations else 0.0
    latencies = [int(result["done"].get("latencyMs") or 0) for result in cache.values()]
    total_tokens = sum(int(result["done"].get("tokenUsage", {}).get("promptTokens") or 0)
                       + int(result["done"].get("tokenUsage", {}).get("completionTokens") or 0)
                       for result in cache.values())

    ratio = lambda hits, cases: round(hits / len(cases), 4) if cases else 0.0
    return {
        "mode": "live",
        "counts": {name: len(cases) for name, cases in datasets.items()},
        "uniqueReplays": len(cache),
        "intentAccuracy": ratio(intent_hits, intents),
        "toolCorrectness": ratio(tool_hits, tool_cases),
        "toolArgumentAccuracy": ratio(arg_hits, tool_cases),
        "ragHitRate": ratio(rag_hits, rag_cases),
        "ragMRR": round(reciprocal_sum / len(rag_cases), 4) if rag_cases else 0.0,
        "replyQuality": round(reply_total / len(reply_cases), 4) if reply_cases else 0.0,
        "citationCoverage": round(citation_coverage, 4),
        "latencyMs": {"p50": _percentile(latencies, 0.5), "p95": _percentile(latencies, 0.95)},
        "totalTokens": total_tokens,
    }
