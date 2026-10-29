"""Pure conversational identity rules; no model, database or graph dependency.

Account nickname is a fallback, not an explicit conversational user_name.
Only USER messages may supply naming commands. Callers pass history in order.
"""
from collections.abc import Iterable, Mapping
import re
from typing import Any

IDENTITY_KEYS = frozenset({"assistant_name", "user_name"})


def _clean_name(name: str) -> str:
    if not name:
        return ""
    n = name.strip()
    return re.sub(r"(?:了|啦|吧|呗|就好|就行|即可)+$", "", n).strip()


def _is_valid_name(name: str) -> bool:
    if not name:
        return False
    n = name.strip()
    return not any(w in n for w in ["什么", "谁", "名字", "哪", "啥"])


def parse_naming_command(text: str) -> dict[str, str]:
    """快速规则提取用户明确发出的称呼/人设指令，保证本轮对话毫秒级实时生效"""
    if not text:
        return {}
    t = re.sub(r"[，, ]*(?:记住了?吗|知道了吗|好吗|可以吗|行吗|ok吗)[？?！!。\s]*$", "", text.strip(), flags=re.IGNORECASE)
    res: dict[str, str] = {}

    # 1. 双方互定: "你叫大肥鱼，我叫派蒙" 或 "我叫派蒙，你叫大肥鱼"
    m1 = re.search(
        r"(?:你叫|叫你|称呼你为)\s*([A-Za-z0-9_一-龥]{1,16})"
        r"[，, ；;和且]+(?:我叫|叫我|我是|称呼我为)\s*([A-Za-z0-9_一-龥]{1,16})",
        t,
    )
    if m1 and _is_valid_name(m1.group(1)) and _is_valid_name(m1.group(2)):
        res["assistant_name"] = _clean_name(m1.group(1))
        res["user_name"] = _clean_name(m1.group(2))
        return res

    m2 = re.search(
        r"(?:我叫|叫我|我是|称呼我为)\s*([A-Za-z0-9_一-龥]{1,16})"
        r"[，, ；;和且]+(?:你叫|叫你|称呼你为)\s*([A-Za-z0-9_一-龥]{1,16})",
        t,
    )
    if m2 and _is_valid_name(m2.group(1)) and _is_valid_name(m2.group(2)):
        res["user_name"] = _clean_name(m2.group(1))
        res["assistant_name"] = _clean_name(m2.group(2))
        return res

    # 2. 单独为助手起名: "从现在开始你叫大肥鱼" / "你叫大肥鱼，记住了吗"
    m3 = re.search(
        r"(?:从现在开始|以后|起)?\s*(?:你叫|叫你|称呼你为)\s*([A-Za-z0-9_一-龥]{1,16})",
        t,
    )
    if m3 and _is_valid_name(m3.group(1)) and not re.search(r"(?:你叫|叫你|称呼你为)\s*[^，, ]+?[吗么呢？?]", t):
        res["assistant_name"] = _clean_name(m3.group(1))

    # 3. 单独自我介绍: "我叫派蒙" / "叫我派蒙"
    m4 = re.search(
        r"(?:从现在开始|以后)?\s*(?:我叫|叫我|称呼我为)\s*([A-Za-z0-9_一-龥]{1,16})",
        t,
    )
    if m4 and _is_valid_name(m4.group(1)) and not any(w in t for w in ["什么", "谁", "名字", "买", "要"]) and not re.search(r"(?:我叫|叫我|称呼我为)\s*[^，, ]+?[吗么呢？?]", t):
        res["user_name"] = _clean_name(m4.group(1))

    return res


def normalize_profile(profile: Mapping[str, Any] | None) -> dict[str, Any]:
    """Copy a profile and remove blank identity fields, without name blacklists."""
    result = dict(profile or {})
    for key in (*IDENTITY_KEYS, "nickname"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            result[key] = value.strip()
        else:
            result.pop(key, None)
    return result


def resolve_profile(
    base: Mapping[str, Any] | None,
    checkpoint: Mapping[str, Any] | None = None,
    *,
    user_history: Iterable[str] = (),
    current_text: str = "",
) -> dict[str, Any]:
    """Backend fields < checkpoint identity < USER history < current naming.

    Other profile fields stay backend-owned. For regeneration, pass no checkpoint
    profile: the gateway's validated history is the reconstruction source.
    """
    saved = normalize_profile(checkpoint)
    result = {**saved, **normalize_profile(base)}
    result.update({key: saved[key] for key in IDENTITY_KEYS if key in saved})
    for text in user_history:
        result.update(parse_naming_command(text))
    result.update(parse_naming_command(current_text))
    return result
