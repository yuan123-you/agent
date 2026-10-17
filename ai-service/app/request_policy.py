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
