"""运行 eval 数据集并产出四项指标基准线（baseline.json）。

用法：
  python -m eval.scripts.run_eval             # 默认离线模式（CI 可复现）
  python -m eval.scripts.run_eval --mode live # （需 LLM+Milvus 真实管线，暂未接入）
  python -m eval.scripts.run_eval --json      # 输出 JSON

指标：
  intentAccuracy     意图准确率
  toolCorrectness    工具调用正确率（期望工具集命中）
  ragHitRate         RAG 命中率（查询 → 期望商品出现在 top-k）
  replyQuality       回复质量（要点覆盖；live 模式可用 LLM-as-judge）

离线模式说明：意图/回复使用规则代理，RAG 命中率用与上线一致的 BM25 关键词召回腿计算，
故 CI 无需 LLM/Milvus 也能产出**可复现**基线；真实数值以 live 模式为准。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # eval/ 入 path
from eval_core import BM25, proxy_intent, proxy_reply_score, tokenize  # noqa: E402
from live_eval import LiveClient, evaluate_live  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parents[1]
DATASET_DIR = EVAL_DIR / "dataset"
RESULTS_DIR = EVAL_DIR / "results"


def _load_lines(name: str) -> list[dict]:
    path = DATASET_DIR / f"{name}.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def evaluate_offline() -> dict:
    products = json.loads((DATASET_DIR / "products.json").read_text(encoding="utf-8"))
    corpus_texts = [f"{p['name']} {p['category']} {p.get('selling_points','')}" for p in products]
    bm25 = BM25(corpus_texts)

    # --- 意图准确率（规则代理） ---
    intent_lines = _load_lines("intent")
    intent_hit = sum(1 for c in intent_lines if proxy_intent(c["input"]) == c["expected"])
    intent_accuracy = round(intent_hit / len(intent_lines), 4)

    # --- 工具调用正确率（规则代理：期望工具集命中） ---
    tool_lines = _load_lines("tool")
    tool_correct = 0
    for c in tool_lines:
        predicted = [t for t in ("product_search", "kb_search", "order_query",
                                 "order_create", "escalate_to_human")
                     if t in c["input"]]
        # 兜底：无法命中任何规则时认为需 product_search
        expected_set = set(c["expected_tools"])
        if not predicted:
            predicted = ["product_search"]
        if set(predicted) & expected_set:
            tool_correct += 1
    tool_correctness = round(tool_correct / len(tool_lines), 4)

    # --- RAG 命中率（BM25 关键词召回腿） ---
    rag_lines = _load_lines("rag")
    rag_hit = 0
    for c in rag_lines:
        top = bm25.search(c["query"], top_k=5)
        top_names = {products[i]["name"] for i in top}
        if any(m in top_names for m in c.get("must_hit", [])):
            rag_hit += 1
    rag_hit_rate = round(rag_hit / len(rag_lines), 4)

    # --- 回复质量（要点覆盖代理） ---
    reply_lines = _load_lines("reply")
    quality_sum = sum(proxy_reply_score(proxy_reply_synth(c["input"]), c["expected_keywords"])
                      for c in reply_lines)
    reply_quality = round(quality_sum / len(reply_lines), 4)

    return {
        "mode": "offline_proxy",
        "generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "counts": {k: len(_load_lines(k)) for k in ("intent", "tool", "rag", "reply")},
        "intentAccuracy": intent_accuracy,
        "toolCorrectness": tool_correctness,
        "ragHitRate": rag_hit_rate,
        "replyQuality": reply_quality,
        "notes": ("offline_proxy 基线：意图/工具/回复为规则代理，RAG 为 BM25 关键词召回腿。"
                  "真实数值请以 live 模式（LLM+Milvus）为准。"),
    }


def proxy_reply_synth(input_text: str) -> str:
    """离线模式无真实模型，用输入里的期望痕迹模拟回复用于代理打分（仅反映可复现基线）。"""
    from eval_core import INTENT_RULES
    for intent, kws in INTENT_RULES:
        for k in kws:
            if k and k in input_text:
                return f"关于「{k}」的说明，请参考页面详情。" + k
    return "推荐如下商品,点击商品名可查看详情。"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["offline", "live"], default="offline")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--base-url", default=os.getenv("AI_BASE_URL", "http://localhost:8000"))
    ap.add_argument("--internal-token", default=os.getenv("INTERNAL_TOKEN", ""))
    ap.add_argument("--user-id", type=int, default=int(os.getenv("EVAL_USER_ID", "1")))
    ap.add_argument("--conversation-start", type=int, default=900000)
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--limit", type=int, default=0, help="每个数据集最多回放条数；0 表示全量")
    args = ap.parse_args()

    if args.mode == "live":
        if not args.internal_token:
            ap.error("live mode requires --internal-token or INTERNAL_TOKEN")
        datasets = {name: _load_lines(name) for name in ("intent", "tool", "rag", "reply")}
        if args.limit > 0:
            datasets = {name: cases[:args.limit] for name, cases in datasets.items()}
        client = LiveClient(args.base_url, args.internal_token, args.user_id, args.timeout)
        baseline = evaluate_live(client, datasets, args.conversation_start)
        baseline["generated_at"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
        out_name = "live.json"
    else:
        baseline = evaluate_offline()
        out_name = "baseline.json"

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / out_name
    out.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(baseline, ensure_ascii=False, indent=2))
    else:
        print(f"== eval ({baseline['mode']}) ==")
        for k, v in baseline["counts"].items():
            print(f"  {k}: {v}")
        print(f"  intentAccuracy : {baseline['intentAccuracy']}")
        print(f"  toolCorrectness: {baseline['toolCorrectness']}")
        print(f"  ragHitRate     : {baseline['ragHitRate']}")
        print(f"  replyQuality   : {baseline['replyQuality']}")
        print(f"  -> saved to {out}")


if __name__ == "__main__":
    main()
