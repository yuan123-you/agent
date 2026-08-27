import json

from eval.live_eval import evaluate_live, parse_sse


def test_parse_sse_collects_named_json_events():
    events = parse_sse([
        b"event: tool_call\n", b'data: {"tool":"product_search"}\n', b"\n",
        b"event: done\n", b'data: {"intent":"PRODUCT_CONSULT"}\n', b"\n",
    ])
    assert events == [
        ("tool_call", {"tool": "product_search"}),
        ("done", {"intent": "PRODUCT_CONSULT"}),
    ]


class FakeClient:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def run(self, text, conversation_id):
        self.calls.append((text, conversation_id))
        return self.results[text]


def result(intent, *, tools=(), products=(), hits=(), content="", latency=100, tokens=10):
    tool_calls = [{"tool": name, "args": args} for name, args in tools]
    tool_results = []
    if products:
        tool_results.append({"tool": "product_search", "eval": {"products": [
            {"name": name, "rank": rank} for rank, name in enumerate(products, 1)
        ]}})
    if hits:
        tool_results.append({"tool": "kb_search", "eval": {"hits": [
            {"source": source, "rank": rank} for rank, source in enumerate(hits, 1)
        ]}})
    return {"tool_calls": tool_calls, "tool_results": tool_results, "done": {
        "intent": intent, "content": content, "latencyMs": latency,
        "tokenUsage": {"promptTokens": tokens - 2, "completionTokens": 2},
    }}


def test_evaluate_live_scores_actual_agent_outputs():
    client = FakeClient({
        "推荐手机": result("PRODUCT_CONSULT", tools=(("product_search", {"category": "PHONE"}),),
                         products=("其他", "星耀 X5"), content="推荐星耀 X5", latency=100, tokens=12),
        "退货吗": result("AFTER_SALE_FAQ", tools=(("kb_search", {"doc_type": "AFTER_SALE"}),),
                       hits=("退换货政策",), content="支持七天退货", latency=300, tokens=8),
    })
    datasets = {
        "intent": [{"input": "推荐手机", "expected": "PRODUCT_CONSULT"}],
        "tool": [{"input": "推荐手机", "expected_tools": ["product_search"], "expected_args": {"category": "PHONE"}}],
        "rag": [{"query": "推荐手机", "must_hit": ["星耀 X5"], "expect_hit": True}],
        "reply": [{"input": "退货吗", "expected_keywords": ["七天"]}],
    }

    metrics = evaluate_live(client, datasets, conversation_start=9000)

    assert metrics["intentAccuracy"] == 1.0
    assert metrics["toolCorrectness"] == 1.0
    assert metrics["toolArgumentAccuracy"] == 1.0
    assert metrics["ragHitRate"] == 1.0
    assert metrics["ragMRR"] == 0.5
    assert metrics["replyQuality"] == 1.0
    assert metrics["citationCoverage"] == 1.0
    assert metrics["latencyMs"] == {"p50": 100, "p95": 300}
    assert metrics["totalTokens"] == 20
    assert len(client.calls) == 2


def test_rag_metric_accepts_current_catalog_category_when_seed_names_change():
    live_result = result("PRODUCT_CONSULT", tools=(("product_search", {"category": "PHONE"}),))
    live_result["tool_results"] = [{"tool": "product_search", "eval": {"products": [
        {"name": "新款手机", "category": "PHONE", "rank": 1}
    ]}}]
    client = FakeClient({"PHONE 推荐": live_result})
    datasets = {
        "intent": [], "tool": [],
        "rag": [{"query": "PHONE 推荐", "must_hit": ["旧种子手机"],
                 "expected_category": "PHONE", "expect_hit": True}],
        "reply": [],
    }

    metrics = evaluate_live(client, datasets)

    assert metrics["ragHitRate"] == 1.0
    assert metrics["ragMRR"] == 1.0
