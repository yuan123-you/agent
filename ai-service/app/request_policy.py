"""Deterministic constraints grounded in the buyer's words, not model guesses."""
import re


def requests_human(text: str) -> bool:
    for clause in re.split(r'[，。！？,!?；;\n]', text):
        if re.search(r'不(?:要|用|需要|想|是)|别|无需|取消|怎么|如何', clause):
            continue
        if re.search(r'(?:转(?:接)?|找|联系|接(?:入|通|一下)?|呼叫|我要|我需要|让).{0,4}(?:人工|真人)|(?:我要|要求)投诉', clause):
            return True
        if clause.strip() in {'人工', '人工客服', '人工服务', '真人客服', '投诉'}:
            return True
    return False


def asks_assistant_identity(text: str) -> bool:
    return any(word in text for word in ('你是谁', '你能做什么', '你能帮我做什么', '介绍你自己',
        '你有什么功能', '你叫什么', '介绍下你自己', '你是真人', '你是机器人', '你是人工'))


def asks_user_identity(text: str) -> bool:
    t = (text or "").strip().lower()
    return any(w in t for w in ('我叫什么', '我是谁', '我的名字', '记得我叫什么', '知道我是谁', '我的称呼', '我叫啥'))


def asks_mutual_identity(text: str) -> bool:
    t = (text or "").strip().lower()
    return (('你叫什么' in t or '你是谁' in t or '你的名字' in t) and
            ('我叫什么' in t or '我是谁' in t or '我的名字' in t))


def asks_conversation_context(text: str) -> bool:
    t = (text or "").strip().lower()
    return any(re.search(p, t) for p in [
        r'我刚才(?:问|说|提)了?(?:你|什么)',
        r'我上一句(?:话)?(?:问|说)了?',
        r'(?:刚才(?:我们)?|(?:我们)?刚才)聊了?(?:什么|哪|到哪|的)',
        r'记得我刚才说',
        r'聊到哪了',
        r'刚才聊的内容',
    ])


def budget_from_text(text: str) -> dict:
    """Extract explicit yuan budgets only; never treat model numbers as budget."""
    number = r'(\d+(?:\.\d+)?)'
    range_pattern = number + r"\s*(?:元|块)?\s*(?:到|至|[-~～])\s*" + number + r"\s*(?:元|块)?"
    match = re.search(range_pattern, text)
    if match and (re.search(r"预算|价格|元|块", text) or re.fullmatch(range_pattern, text.strip())):
        low, high = map(float, match.groups())
        return {"min_price": low, "max_price": high} if low <= high else {}
    match = re.search(number + r"\s*(?:元|块)?\s*(以内|以下|左右|上下|以上|起)", text)
    if match:
        amount = float(match.group(1))
        lower_bound = match.group(2) in {"以上", "起"}
        return {"min_price": amount if lower_bound else None,
                "max_price": None if lower_bound else amount}
    match = re.search(r"(?:预算|不超过|最多|上限)\s*" + number, text)
    if not match:
        match = re.search(number + r"\s*(?:元|块)", text)
    if not match:
        match = re.fullmatch(r"\s*" + number + r"\s*", text)
    return {"min_price": None, "max_price": float(match.group(1))} if match else {}


def requires_kb(text: str) -> bool:
    """Explicit service-policy questions need evidence even if a model ignores tools."""
    t = (text or "").strip()
    if requests_human(t) or asks_assistant_identity(t):
        return False
    topic = re.search(r"退货|退换|退款|保修|售后|运费|三包|发票|开票|配送|送货|人工客服", t)
    if not topic:
        return False
    if re.search(r"规则|政策|条件|标准|期限|规定|流程|要求", t):
        return True
    if re.search(r"(?:帮我|我要|请)(?:申请|发起|提交)(?:退款|退货|售后)", t):
        return False
    return bool(re.search(r"几天|多久|谁|怎么|如何|能否|是否|支持|几点|上班|[?？吗]", t))
