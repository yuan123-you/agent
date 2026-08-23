"""生成 eval 数据集（四指标种子 + 商品语料），来源：V1__init.sql 真实商品库。

产物（相对 eval/ 目录）：
  dataset/products.json   商品语料（id/name/category/brand/price/selling_points）
  dataset/intent.jsonl    意图准确率种子
  dataset/tool.jsonl      工具调用正确率种子
  dataset/rag.jsonl       RAG 命中率种子
  dataset/reply.jsonl     回复质量种子
输出示例数：intent 70 + tool 45 + rag 40 + reply 35 ≈ 190 条。
全部确定性生成，无需 LLM / 外部服务，CI 可复现。
"""
from __future__ import annotations

import csv
import json
import random
from pathlib import Path

random.seed(20260821)  # 固定种子保证可复现

EVAL_DIR = Path(__file__).resolve().parents[1]
DATASET_DIR = EVAL_DIR / "dataset"
SQL_PATH = Path(__file__).resolve().parents[2] / "backend" / "src" / "main" / "resources" / "db" / "init" / "V1__init.sql"

# ---------------------------------------------------------------- 解析商品
def parse_products(sql_text: str) -> list[dict]:
    products: list[dict] = []
    for stmt in sql_text.split(";"):
        lines = stmt.splitlines()
        # 语句里含商品表头（可能被 -- 注释行或空行包裹）
        if not any(l.lstrip().upper().startswith("INSERT INTO PRODUCT") for l in lines):
            continue
        for line in lines:
            line = line.strip().rstrip(",")
            if not line.startswith("(") or not line.endswith(")"):
                continue
            row = line[1:-1]
            try:
                fields = next(csv.reader([row], delimiter=",", quotechar="'"))
            except Exception:
                continue
            if len(fields) < 6:  # 规格/描述含内嵌引号导致解析残缺的行，跳过
                continue
            products.append({
                "name": fields[0].strip(),
                "category": fields[1].strip(),
                "brand": fields[2].strip(),
                "price": fields[3].strip(),
                "selling_points": fields[5].strip(),
            })
    return products


def main() -> None:
    if not SQL_PATH.exists():
        raise SystemExit(f"not found: {SQL_PATH}")
    products = parse_products(SQL_PATH.read_text(encoding="utf-8"))
    if len(products) < 20:
        raise SystemExit(f"parsed too few products: {len(products)}")
    # 生成稳定的语料 id
    corpus = [{"id": i + 1, **p} for i, p in enumerate(products)]
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    (DATASET_DIR / "products.json").write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8")

    by_cat: dict[str, list[dict]] = {}
    for p in corpus:
        by_cat.setdefault(p["category"], []).append(p)

    # -------------------------------------------------- 意图 intent.jsonl
    intent_cases: list[dict] = []
    def add_intent(text, intent, note=""):
        intent_cases.append({"input": text, "expected": intent, "note": note})

    # PRODUCT_CONSULT
    cats = list(by_cat.keys())
    for cat in cats[:12]:
        add_intent(f"推荐几款{cat}给我", "PRODUCT_CONSULT", cat)
        add_intent(f"有没有 {cat} 性价比高的", "PRODUCT_CONSULT", cat)
    for p in corpus[:10]:
        add_intent(f"{p['name']}怎么样", "PRODUCT_CONSULT")
        add_intent(f"{p['name']}和别的比哪个好", "PRODUCT_CONSULT")
    # ORDER_QUERY
    for q in ["我的订单到哪了", "看看我的物流", "发货没有", "快递到哪了", "查询最新订单",
              "我买的手机发货了吗", "订单显示待支付", "我的售后订单进展"]:
        add_intent(q, "ORDER_QUERY")
    # ORDER_CREATE
    for q in ["帮我下单", "我要买这款", "买个 {0}".format(corpus[0]['name']), "下单一个",
              "立刻购买", "拍下这款", "替我买了吧"]:
        add_intent(q, "ORDER_CREATE")
    # AFTER_SALE_FAQ
    for q in ["支持退换货吗", "保修多久", "怎么退款", "退换货的规则是什么", "配送要多久",
              "运费多少", "七天无理由退货吗", "商品保修政策"]:
        add_intent(q, "AFTER_SALE_FAQ")
    # SMALL_TALK
    for q in ["你好", "嗨", "早上好", "你能做什么", "介绍下你自己", "在的在的", "hello"]:
        add_intent(q, "SMALL_TALK")
    # HUMAN_REQUEST
    for q in ["转人工客服", "我要投诉", "给我转人工", "人工服务", "帮我找真人客服", "你们人工在哪"]:
        add_intent(q, "HUMAN_REQUEST")

    # -------------------------------------------------- 工具 tool.jsonl
    tool_cases: list[dict] = []
    def add_tool(text, expected_tools, expected_args=None, note=""):
        tool_cases.append({"input": text, "expected_tools": expected_tools,
                           "expected_args": expected_args or {}, "note": note})

    sample = {c: lst[0] for c, lst in by_cat.items()}
    for cat, p in sample.items():
        add_tool(f"推荐一款{cat}", ["product_search"], {"category": cat}, cat)
        add_tool(f"预算内买{cat}", ["product_search"], {"category": cat})
    for p in corpus[:8]:
        add_tool(f"这款{p['name']}的价格", ["product_search"], {"keyword": p["name"]})
    add_tool("我的订单", ["order_query"], {})
    add_tool("我最近的订单状态", ["order_query"], {})
    add_tool("发货了没", ["order_query"], {})
    for q in ["支持七天无理由退货吗", "保修政策", "退换货规则", "配送说明", "售后政策"]:
        add_tool(q, ["kb_search"], {"doc_type": "AFTER_SALE" if "售后" in q or "保修" in q or "退货" in q or "退换" in q else "ALL"}, q)
    add_tool("我要转人工", ["escalate_to_human"], {})
    add_tool("帮我把收藏的那款下单", ["order_create", "product_search"], {})

    # -------------------------------------------------- RAG rag.jsonl
    rag_cases: list[dict] = []
    for cat, lst in by_cat.items():
        names = [p["name"] for p in lst[:3]]
        rag_cases.append({"query": f"{cat} 推荐", "must_hit": names[:2], "expect_hit": True,
                          "expected_category": cat, "note": f"{cat} 类目应有命中"})
    for p in corpus[:10]:
        rag_cases.append({"query": p["name"], "must_hit": [p["name"]], "expect_hit": True,
                          "expected_category": p["category"], "note": "按商品名检索应召回自身"})
    for p in corpus[10:20]:
        kw = p["selling_points"][:6] if p["selling_points"] else p["name"]
        rag_cases.append({"query": kw, "must_hit": [p["name"]], "expect_hit": True,
                          "expected_category": p["category"], "note": "卖点词应召回该商品"})

    # -------------------------------------------------- 回复 reply.jsonl  (质量=是否覆盖要点)
    reply_cases: list[dict] = []
    def add_reply(text, expected_keywords, note=""):
        reply_cases.append({"input": text, "expected_keywords": expected_keywords, "note": note})

    for p in corpus[:15]:
        add_reply(f"给我介绍下{p['name']}", [p["name"]], "应提及商品名")
    for cat, p in list(sample.items())[:6]:
        add_reply(f"推荐一款{cat}", [p["name"]], f"应推荐{cat}类目商品")
    add_reply("运费多少", ["运费"], "应给出运费说明")
    add_reply("支持退货吗", ["退货", "七天"], "应说明退货政策")
    add_reply("你好", ["你好", "购物"], "应友好回应并引导")
    add_reply("转账人工", ["人工"], "应引导转人工")

    # -------------------------------------------------- 写盘
    _write("intent.jsonl", intent_cases)
    _write("tool.jsonl", tool_cases)
    _write("rag.jsonl", rag_cases)
    _write("reply.jsonl", reply_cases)

    print(f"products={len(corpus)} intent={len(intent_cases)} tool={len(tool_cases)} "
          f"rag={len(rag_cases)} reply={len(reply_cases)} total={sum(len(c) for c in [intent_cases, tool_cases, rag_cases, reply_cases])}")


def _write(name: str, rows: list[dict]) -> None:
    path = DATASET_DIR / name
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()