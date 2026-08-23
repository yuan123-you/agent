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
