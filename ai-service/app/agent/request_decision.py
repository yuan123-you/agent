"""Semantic intent + next-step decisions; no business-word matching or tool execution."""
from __future__ import annotations

import asyncio
import contextvars
import logging
import math
from dataclasses import asdict, dataclass
from functools import lru_cache

from app.clients.llm import get_embeddings
from app.config import settings

logger = logging.getLogger(__name__)
INTENTS = frozenset({"PRODUCT_CONSULT", "ORDER_QUERY", "ORDER_CREATE", "AFTER_SALE_FAQ",
                     "SMALL_TALK", "ASSISTANT_META", "HUMAN_REQUEST"})
CLARIFICATIONS = {
    "after_sale_goal": "您是想退换货，还是商品存在质量问题？",
    "product": "您咨询的是哪款商品？",
    "issue": "商品具体出现了什么问题？",
    "request": "您希望咨询商品或规则、查询订单，还是办理售后？",
}


def _model_confident(data: object) -> bool:
    if not isinstance(data, dict):
        return False
    value = data.get("confidence")
    return value is None or (not isinstance(value, bool) and isinstance(value, (float, int))
                             and math.isfinite(value) and .6 <= value <= 1)


@dataclass(frozen=True, slots=True)
class RequestDecision:
    intent: str
    next_step: str
    missing: str | None = None
    source: str = "model"
    score: float | None = None
    margin: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_model(cls, data: object) -> RequestDecision | None:
        if not isinstance(data, dict):
            return None
        if not _model_confident(data):
            return None
        if "route" in data:
            card = data["route"]
            return _MODEL_CARDS.get(card) if isinstance(card, str) else None
        if not isinstance(data.get("intent"), str) or data["intent"] not in INTENTS:
            return None
        intent, step, missing = data["intent"], data.get("next_step"), data.get("missing")
        if step is None and intent in {"SMALL_TALK", "ASSISTANT_META"}:
            step = "assist"
        if not isinstance(step, str) or step not in {"assist", "retrieve", "clarify"}:
            return None
        if step == "clarify":
            if not isinstance(missing, str) or missing not in CLARIFICATIONS:
                return None
        elif missing is not None:
            return None
        if step == "retrieve" and intent not in {"AFTER_SALE_FAQ", "PRODUCT_CONSULT"}:
            return None
        if step == "assist" and intent == "AFTER_SALE_FAQ":
            return None
        if missing == "after_sale_goal" and intent != "AFTER_SALE_FAQ":
            return None
        return cls(intent, step, missing)


# Compact single-label output avoids fragile multi-field generation on the existing small model.
_MODEL_CARDS = {
    "HELP": RequestDecision("AFTER_SALE_FAQ", "clarify", "after_sale_goal"),
    "RULE": RequestDecision("AFTER_SALE_FAQ", "retrieve"),
    "ORDER": RequestDecision("ORDER_QUERY", "assist"),
    "SHOP": RequestDecision("PRODUCT_CONSULT", "assist"),
    "MIXED": RequestDecision("PRODUCT_CONSULT", "retrieve"),
    "BUY": RequestDecision("ORDER_CREATE", "assist"),
    "CHAT": RequestDecision("SMALL_TALK", "assist"),
    "WEB": RequestDecision("SMALL_TALK", "assist"),
    "IDENTITY": RequestDecision("ASSISTANT_META", "assist"),
    "HUMAN": RequestDecision("HUMAN_REQUEST", "assist"),
    "UNKNOWN": RequestDecision("SMALL_TALK", "clarify", "request"),
}


def validated_focus(payload: object) -> dict | None:
    """Conversation continuity is never inherited human/purchase authorization."""
    if not isinstance(payload, dict) or not isinstance(payload.get("topic"), str) or not payload["topic"].strip():
        return None
    decision = RequestDecision.from_model(payload)
    if not decision or decision.intent not in {"ORDER_QUERY", "PRODUCT_CONSULT", "AFTER_SALE_FAQ"} or decision.next_step == "clarify":
        return None
    return {"intent": decision.intent, "next_step": decision.next_step, "topic": payload["topic"]}


def continuation_decision(data: object, current: object) -> RequestDecision | None:
    if not _model_confident(data) or data.get("route") != "CONTINUE":
        return None
    focus = validated_focus(current)
    return RequestDecision(focus["intent"], focus["next_step"]) if focus else None


def next_focus(current: object, decision: RequestDecision, topic: str, *, continued: bool = False) -> dict | None:
    focus = validated_focus(current)
    if continued or (focus and focus["intent"] == "ORDER_QUERY" and decision.intent == "AFTER_SALE_FAQ" and decision.next_step == "retrieve"):
        return focus
    if decision.intent in {"SMALL_TALK", "ASSISTANT_META"} and decision.next_step == "assist":
        return focus
    if decision.intent in {"ORDER_QUERY", "PRODUCT_CONSULT", "AFTER_SALE_FAQ"} and decision.next_step != "clarify":
        return {"intent": decision.intent, "next_step": decision.next_step, "topic": topic}
    return None


@dataclass(frozen=True, slots=True)
class RouteExample:
    text: str
    intent: str
    next_step: str = "assist"
    missing: str | None = None


# Training examples describe intent/action pairs, never substring or regex triggers.
ROUTE_EXAMPLES = (
    RouteExample("收到商品后不太满意，不知道该怎么处理", "AFTER_SALE_FAQ", "clarify", "after_sale_goal"),
    RouteExample("买回来的东西不是我想要的，需要客服帮忙", "AFTER_SALE_FAQ", "clarify", "after_sale_goal"),
    RouteExample("这件东西不合心意，有什么解决办法", "AFTER_SALE_FAQ", "clarify", "after_sale_goal"),
    RouteExample("商品使用之后还能申请退货吗", "AFTER_SALE_FAQ", "retrieve"),
    RouteExample("请解释平台退货的适用条件和期限", "AFTER_SALE_FAQ", "retrieve"),
    RouteExample("退货寄回产生的邮费由谁承担", "AFTER_SALE_FAQ", "retrieve"),
    RouteExample("商品保修多久，如何享受保修服务", "AFTER_SALE_FAQ", "retrieve"),
    RouteExample("商品发票如何开具，有什么要求", "AFTER_SALE_FAQ", "retrieve"),
    RouteExample("平台配送通常需要多少天，采用什么方式", "AFTER_SALE_FAQ", "retrieve"),
    RouteExample("平台接受哪些付款方式", "AFTER_SALE_FAQ", "retrieve"),
    RouteExample("已经申请退款后，钱多久退到账户", "AFTER_SALE_FAQ", "retrieve"),
    RouteExample("我要办理退货退款，请协助处理订单", "ORDER_QUERY"),
    RouteExample("商品损坏了，帮我申请售后", "ORDER_QUERY"),
    RouteExample("收到的货少了配件，我想处理这笔订单", "ORDER_QUERY"),
    RouteExample("帮我查询订单现在到哪里了", "ORDER_QUERY"),
    RouteExample("我的包裹什么时候送到，查一下物流", "ORDER_QUERY"),
    RouteExample("我想取消尚未发货的订单", "ORDER_QUERY"),
    RouteExample("推荐一款适合拍照的手机", "PRODUCT_CONSULT"),
    RouteExample("我想买个轻便的电脑，帮我挑选", "PRODUCT_CONSULT"),
    RouteExample("预算三千左右，有哪些值得购买的商品", "PRODUCT_CONSULT"),
    RouteExample("对比一下这几件商品的区别和优缺点", "PRODUCT_CONSULT"),
    RouteExample("帮我选支持退换的商品，并解释相应条件", "PRODUCT_CONSULT", "retrieve"),
    RouteExample("我要购买刚才选好的那件商品，请生成订单", "ORDER_CREATE"),
    RouteExample("就要列表第二款，数量一个，帮我下单", "ORDER_CREATE"),
    RouteExample("我已经选定这个产品，可以结算了", "ORDER_CREATE"),
    RouteExample("请把对话转给人工客服", "HUMAN_REQUEST"),
    RouteExample("我要找真人处理投诉", "HUMAN_REQUEST"),
    RouteExample("我不想再和机器人说了，联系人工", "HUMAN_REQUEST"),
    RouteExample("你刚才答得不对，完全没理解我的问题", "SMALL_TALK"),
    RouteExample("你的回答太笨了，我对这次回复很失望", "SMALL_TALK"),
    RouteExample("帮我写一个排序算法", "SMALL_TALK"),
    RouteExample("介绍一下北京的天气情况", "SMALL_TALK"),
)


def _unit(vector: object, dimensions: int) -> tuple[float, ...]:
    if not isinstance(vector, (list, tuple)) or len(vector) != dimensions:
        raise ValueError("incompatible embedding dimension")
    if any(isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x) for x in vector):
        raise ValueError("nonfinite embedding")
    norm = math.hypot(*vector)
    if norm == 0 or not math.isfinite(norm):
        raise ValueError("zero embedding")
    return tuple(x / norm for x in vector)


class SemanticRouter:
    """Cache example embeddings once; accept only a high-score, distinct intent/action pair."""
    def __init__(self, embeddings_factory, *, dimensions: int, min_score: float,
                 min_margin: float, timeout_s: float, init_timeout_s: float = 90, enabled: bool = True):
        self.factory = embeddings_factory
        self.dimensions, self.min_score, self.min_margin = dimensions, min_score, min_margin
        self.timeout_s, self.init_timeout_s, self.enabled = timeout_s, init_timeout_s, enabled
        self._examples_task: asyncio.Task | None = None

    async def _load(self):
        async with asyncio.timeout(self.init_timeout_s):
            vectors = await self.factory().aembed_documents([e.text for e in ROUTE_EXAMPLES])
        if len(vectors) != len(ROUTE_EXAMPLES):
            raise ValueError("incomplete example embeddings")
        return [_unit(vector, self.dimensions) for vector in vectors]

    def _examples(self) -> asyncio.Task:
        task = self._examples_task
        if task is None or task.cancelled() or (task.done() and task.exception() is not None):
            task = asyncio.create_task(self._load(), context=contextvars.Context())
            # A timed-out caller leaves bounded initialization in flight for later requests.
            task.add_done_callback(lambda completed: completed.exception() if not completed.cancelled() else None,
                                   context=contextvars.Context())
            self._examples_task = task
        return task

    async def classify(self, text: str, *, contextual: bool = False) -> RequestDecision | None:
        if not self.enabled or contextual or len(text) > 512 or not text.strip():
            return None
        try:
            async with asyncio.timeout(self.timeout_s):
                vectors = await asyncio.shield(self._examples())
                query = _unit(await self.factory().aembed_query(text), self.dimensions)
            grouped = {}
            for example, vector in zip(ROUTE_EXAMPLES, vectors, strict=True):
                key = (example.intent, example.next_step, example.missing)
                score = math.fsum(a * b for a, b in zip(query, vector, strict=True))
                grouped[key] = max(score, grouped.get(key, -1.0))
            ranked = sorted(grouped.items(), key=lambda row: row[1], reverse=True)
            key, score = ranked[0]
            margin = score - ranked[1][1]
            if score < self.min_score or margin < self.min_margin:
                return None
            return RequestDecision(*key, source="embedding", score=score, margin=margin)
        except Exception as exc:
            logger.info("Semantic route abstained (%s)", type(exc).__name__)
            return None


@lru_cache(maxsize=1)
def get_semantic_router() -> SemanticRouter:
    return SemanticRouter(get_embeddings, dimensions=settings.embedding_dim,
        min_score=settings.semantic_route_min_score, min_margin=settings.semantic_route_min_margin,
        timeout_s=settings.semantic_route_timeout_s, enabled=settings.semantic_route_enabled)
