"""One request policy for fast routing, classifier constraints and graph dispatch.

Rules handle explicit invariants; ambiguous turns still use the intent model.
There is no model or graph execution in this module.
"""
import re

from app.agent.state import ReplyRoute
from app.agent.identity import parse_naming_command
from app.request_policy import (
    asks_assistant_identity, asks_conversation_context, asks_mutual_identity,
    asks_user_identity, budget_from_text, is_negative_sentiment, is_out_of_scope,
    requests_human, requires_kb,
)
from app.tools.tools import category_from_user_text

KNOWN_INTENTS = frozenset({
    "PRODUCT_CONSULT", "ORDER_QUERY", "ORDER_CREATE", "AFTER_SALE_FAQ",
    "SMALL_TALK", "ASSISTANT_META", "HUMAN_REQUEST",
})

TIME_QUERY_RE = re.compile(
    r"(?:(?P<day>今天|明天|后天|昨天|前天)(?:是)?(?:星期几|周几|礼拜几|几号|多少号|什么日子)|现在(?:是)?(?:几点|什么时间))[？?！!。\s]*"
)


def fallback_intent_by_rules(user_text: str) -> str:
    """当模型未能输出标准 JSON 时，基于规则启发式兜底，避免全部误判为 PRODUCT_CONSULT"""
    t = (user_text or "").strip().lower()
    if requests_human(t):
        return "HUMAN_REQUEST"
    if parse_naming_command(t):
        return "SMALL_TALK"
    if asks_mutual_identity(t) or asks_user_identity(t) or asks_conversation_context(t):
        return "SMALL_TALK"
    if asks_assistant_identity(t):
        return "ASSISTANT_META"
    if is_negative_sentiment(t) or is_out_of_scope(t):
        return "SMALL_TALK"
    if TIME_QUERY_RE.search(t):
        return "SMALL_TALK"
    if "人工客服" in t and any(w in t for w in ["几点", "上班", "时间"]):
        return "AFTER_SALE_FAQ"
    if re.search(r"(?:帮我|我要|我想|请)(?:申请|发起|提交|办|办理)?(?:退款|退货|售后)", t):
        return "ORDER_QUERY"
    if any(w in t for w in ["订单", "物流", "发货", "快递", "到哪了", "待支付"]):
        return "ORDER_QUERY"
    if any(w in t for w in ["退货", "退换", "退款", "保修", "售后", "运费", "三包", "坏了", "换货", "发票", "送货", "自提", "七天"]):
        return "AFTER_SALE_FAQ"
    # Buying an unspecified category is selection, not authorization to order.
    if category_from_user_text(t) and not any(w in t for w in ["下单", "确认购买", "买这个", "买它", "买第"]):
        return "PRODUCT_CONSULT"
    if any(w in t for w in ["帮我买", "下单", "拍下", "立刻购买", "我要买", "买第", "买这个", "买它", "帮我下单", "确认购买"]):
        return "ORDER_CREATE"
    if any(w in t for w in ["你好", "您好", "早上好", "晚上好", "嗨", "hello", "谢谢", "多谢", "再见", "在吗"]):
        return "SMALL_TALK"
    if re.search(r"不(?:要|用|需要|想).*(?:人工|真人)|取消.*(?:人工|转接)", t):
        return "SMALL_TALK"
    return "PRODUCT_CONSULT"



class RequestPolicy:
    """Inspect once at the router; persist only intent + destination in graph state."""

    def __init__(self, text: str):
        self.text = text
        self.human = requests_human(text)
        self.naming = bool(parse_naming_command(text))
        self.identity = asks_assistant_identity(text)
        self.local_conversation = bool(
            self.naming or self.identity or asks_user_identity(text)
            or asks_mutual_identity(text) or asks_conversation_context(text)
            or bool(TIME_QUERY_RE.search(text.strip()))
            or re.fullmatch(r"(?:你好(?:呀|啊)?|您好|嗨|hello|hi|谢谢(?:你|啦)?|感谢|再见|拜拜)[！!。.?？\s]*", text.strip(), re.IGNORECASE)
            or is_negative_sentiment(text) or is_out_of_scope(text)
        )
        self.category = category_from_user_text(text)
        self.policy_required = requires_kb(text)
        self.fallback_intent = fallback_intent_by_rules(text)

    def fast_intent(self) -> str | None:
        if self.human:
            return "HUMAN_REQUEST"
        mixed_shopping = bool(self.category and re.search(r"推荐|挑选|选购|想买|购买|找|看看", self.text))
        if (self.policy_required and not mixed_shopping
                and not is_negative_sentiment(self.text) and not is_out_of_scope(self.text)):
            return "AFTER_SALE_FAQ"
        if self.local_conversation:
            return self.fallback_intent
        standalone_shopping = (
            re.fullmatch(r"(?:请(?:帮我)?|帮我|给我|我想|想)?(?:推荐|找|挑选|选购|看看|最新|最火)[^，,。！？!?；;\n]{0,80}[。！？!?]?", self.text.strip())
            and self.category and self.fallback_intent == "PRODUCT_CONSULT"
            and not re.search(r"退|换货|售后|保修|发货|配送|运费|发票|下单|订单|物流|取消|人工|七天|7天", self.text)
        )
        return "PRODUCT_CONSULT" if standalone_shopping else None

    def constrain(self, model_intent: str | None) -> str:
        """A classifier cannot invent authorization or bypass policy evidence."""
        explicit = self.fast_intent()
        if explicit:
            return explicit
        intent = model_intent if model_intent in KNOWN_INTENTS else self.fallback_intent
        if intent == "HUMAN_REQUEST":
            return self.fallback_intent
        if self.policy_required and intent in {"SMALL_TALK", "ASSISTANT_META"}:
            return "AFTER_SALE_FAQ"
        if self.fallback_intent == "ORDER_QUERY" and not self.category:
            return "ORDER_QUERY"
        if (intent == "ORDER_CREATE" and self.fallback_intent == "PRODUCT_CONSULT"
                and (self.category or budget_from_text(self.text))):
            return "PRODUCT_CONSULT"
        return intent

    def destination(self, intent: str | None, web_enabled: bool) -> ReplyRoute:
        if intent == "HUMAN_REQUEST":
            return "escalate_node"
        if intent == "ASSISTANT_META":
            return "small_talk"
        if intent == "SMALL_TALK":
            return "agent" if web_enabled and not self.local_conversation else "small_talk"
        return "agent"
