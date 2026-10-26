"""链接输出后验校验（link_guard）：
正则提取回答中的 mall:// 链接，比对 id 是否来自本轮工具真实结果；
未命中的链接降级为纯文本（防模型编造 id）。"""
import logging
import re

logger = logging.getLogger("ai-service.link_guard")

LINK_RE = re.compile(r"\[([^\]]+)\]\((mall://[^)\s]+)\)")
ID_RE = re.compile(r"mall://(?:product|order)/(\d+)")


def collect_known_ids(*texts: str) -> set[str]:
    """从工具结果文本中收集合法的链接 id"""
    ids: set[str] = set()
    for t in texts:
        if t:
            ids.update(ID_RE.findall(t))
    return ids


def guard_links(text: str, known_ids: set[str]) -> str:
    """校验回答中的链接；id 不在已知集合中的链接降级为纯文本"""
    if not text or "[" not in text:
        return text

    def repl(m: re.Match) -> str:
        href = m.group(2)
        ids = ID_RE.findall(href)
        if ids and all(i in known_ids for i in ids):
            return m.group(0)
        logger.warning("link_guard: strip invalid link %s", href)
        return m.group(1)  # 降级为纯文本

    return LINK_RE.sub(repl, text)


def ensure_product_links(text: str, result: dict | None) -> str:
    """Fallback for unlinked recommendations using only actual product-search links."""
    if result is None:
        return text
    if result.get("error"):
        return "商品检索暂时不可用，请稍后重试。"
    products = result.get("products")
    if not isinstance(products, list):
        return text
    if not products:
        return "暂未找到符合条件的在售商品，您可以调整预算或筛选条件后再试。"
    valid = [p for p in products if isinstance(p, dict) and p.get("name")
             and re.fullmatch(r"mall://product/\d+", str(p.get("link", "")))]
    urls = {p["link"] for p in valid}
    has_placeholder = re.search(r"\[(?:产品|商品)链接\]", text)
    if not has_placeholder and any(m.group(2) in urls for m in LINK_RE.finditer(text)):
        return text
    if not valid:
        return "已检索到商品，但商品链接暂时不可用，请稍后重试。"
    rows = []
    for p in valid[:5]:
        name = re.sub(r"([\\\[\]])", r"\\\1", str(p["name"]))
        price = f"，¥{p['price']}" if p.get("price") is not None else ""
        rows.append(f"{len(rows) + 1}. [{name}]({p['link']}){price}")
    return "为您找到以下在售商品：\n" + "\n".join(rows) + "\n点击商品名可查看详情。"


class GuardedLinkBuffer:
    """Hold incomplete Markdown links so unknown IDs never escape in early tokens."""

    def __init__(self, known_ids: set[str], enabled: bool = True):
        self.known_ids = known_ids
        self.enabled = enabled
        self.pending = ""

    def push(self, text: str) -> str:
        if not self.enabled:
            return text
        self.pending += text
        ready: list[str] = []
        while self.pending:
            start = self.pending.find("[")
            if start < 0:
                ready.append(self.pending)
                self.pending = ""
                break
            ready.append(self.pending[:start])
            self.pending = self.pending[start:]
            close = self.pending.find("]")
            newline = self.pending.find("\n")
            if close < 0 or (newline >= 0 and newline < close):
                if newline < 0:
                    break
                ready.append(self.pending[:newline + 1])
                self.pending = self.pending[newline + 1:]
                continue
            if close + 1 == len(self.pending):
                break
            if self.pending[close + 1] != "(":
                ready.append(self.pending[:close + 1])
                self.pending = self.pending[close + 1:]
                continue
            end = self.pending.find(")", close + 2)
            if end < 0:
                break
            ready.append(guard_links(self.pending[:end + 1], self.known_ids))
            self.pending = self.pending[end + 1:]
        return "".join(ready)
