"""Local identity/time responses and authorization boundaries, not business-word routing."""
import re

from app.agent.state import ReplyRoute
from app.agent.identity import parse_naming_command
from app.request_policy import (
    asks_assistant_identity, asks_conversation_context, asks_mutual_identity,
    asks_user_identity, is_negative_sentiment, is_out_of_scope,
    requests_human,
)

TIME_QUERY_RE = re.compile(
    r"(?:(?P<day>今天|明天|后天|昨天|前天)(?:是)?(?:星期几|周几|礼拜几|几号|多少号|什么日子)|现在(?:是)?(?:几点|什么时间))[？?！!。\s]*"
)




class RequestPolicy:
    """Keep local shortcuts and dispatch separate from semantic business decisions."""

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

    def fast_intent(self) -> str | None:
        """Only explicit authorization and local identity/time commands bypass semantics."""
        if self.text.strip().rstrip("。！？!?.") in {"人工", "人工客服", "转人工", "转人工客服", "请转人工", "请转人工客服"}:
            return "HUMAN_REQUEST"
        if self.naming or asks_user_identity(self.text) or asks_mutual_identity(self.text) or asks_conversation_context(self.text):
            return "SMALL_TALK"
        if self.identity:
            return "ASSISTANT_META"
        if TIME_QUERY_RE.search(self.text.strip()) or re.fullmatch(
                r"(?:你好(?:呀|啊)?|您好|嗨|hello|hi|谢谢(?:你|啦)?|感谢|再见|拜拜)[！!。.?？\s]*",
                self.text.strip(), re.IGNORECASE):
            return "SMALL_TALK"
        return None

    def destination(self, intent: str | None, web_enabled: bool) -> ReplyRoute:
        if intent == "HUMAN_REQUEST":
            return "escalate_node"
        if intent == "ASSISTANT_META":
            return "small_talk"
        if intent == "SMALL_TALK":
            return "agent" if web_enabled and not self.local_conversation else "small_talk"
        return "agent"
