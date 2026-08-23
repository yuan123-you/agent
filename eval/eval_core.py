"""eval 自包含评估核心：轻量 BM25 检索 + 离线代理分类器（不依赖 AI 服务的运行期依赖/外部服务）。

设计目标：
- CI/无外部服务时也能产出**可复现**的基线数值（mode=offline_proxy）。
- 有 LLM + Milvus 时用 mode=live 走真实管线，得到真实四指标。
- keyword 召回评测复用与 product_index 一致的 CJK 双字窗 + ASCII 词切分，保证离线结果与线上检索腿同源。
"""
from __future__ import annotations

import math
import re

# 与 ai-service/app/rag/product_index.py 保持一致的切词逻辑
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
_ASCII_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._\-]+")


def tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    tokens: list[str] = []
    for seg in _CJK_RE.findall(text):
        if len(seg) >= 2:
            tokens.extend(seg[i:i + 2] for i in range(len(seg) - 1))
    tokens.extend(_ASCII_RE.findall(text))
    return tokens


class BM25:
    """Okapi BM25，面向关键词召回评测。"""

    def __init__(self, corpus: list[str], k1: float = 1.5, b: float = 0.75):
        self.docs = [tokenize(d) for d in corpus]
        self.n = len(self.docs)
        self.avgdl = sum(len(d) for d in self.docs) / self.n if self.n else 0
        self.df: dict[str, int] = {}
        for d in self.docs:
            for t in set(d):
                self.df[t] = self.df.get(t, 0) + 1
        self.idf = {t: math.log(1 + (self.n - df + 0.5) / (df + 0.5)) for t, df in self.df.items()}
        self.k1, self.b = k1, b

    def score(self, query: str, doc_idx: int) -> float:
        doc = self.docs[doc_idx]
        if not doc:
            return 0.0
        dl = len(doc)
        tf: dict[str, int] = {}
        for t in doc:
            tf[t] = tf.get(t, 0) + 1
        s = 0.0
        for t in tokenize(query):
            if t not in self.idf:
                continue
            f = tf.get(t, 0)
            s += self.idf[t] * (f * (self.k1 + 1)) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
        return s

    def search(self, query: str, top_k: int = 5) -> list[int]:
        scored = sorted(range(self.n), key=lambda i: self.score(query, i), reverse=True)
        return [i for i in scored if self.score(query, i) > 0][:top_k]


# ---------------------------------------------------------------- 离线意图代理
# 规则分类器：仅作 CI 可复现的代理基线，真实准确率以 live 模式为准。
INTENT_RULES: list[tuple[str, list[str]]] = [
    ("HUMAN_REQUEST", ["转人工", "人工客服", "人工", "投诉", "找客服", "人工服务"]),
    ("ORDER_CREATE", ["帮我买", "下单", "购买", "我要买", "给我买", "订一个", "拍下"]),
    ("ORDER_QUERY", ["我的订单", "订单到", "物流", "发货", "到哪了", "送到", "快递", "查询订单"]),
    ("AFTER_SALE_FAQ", ["退货", "退款", "退换货", "保修", "售后", "配送", "运费", "七天", "无理由"]),
    ("SMALL_TALK", ["你好", "您好", "hello", "hi", "在吗", "嗨", "能做什么", "介绍一下自己"]),
    ("PRODUCT_CONSULT", []),  # 兜底
]


def proxy_intent(text: str) -> str:
    t = text.lower()
    for intent, kws in INTENT_RULES:
        if any(k in t for k in kws):
            return intent
    return "PRODUCT_CONSULT"


# ---------------------------------------------------------------- 回复质量代理
def proxy_reply_score(actual: str, expected_keywords: list[str]) -> float:
    """离线代理：命中预期要点数 / 要点数。真实质量请用 live 模式 LLM-as-judge。"""
    if not expected_keywords:
        return 0.0
    a = actual or ""
    hit = sum(1 for kw in expected_keywords if kw and kw in a)
    return round(hit / len(expected_keywords), 4) if expected_keywords else 0.0