"""Keep evidence facts in local-model prompts; leave UI/URL transport work to the application."""
from __future__ import annotations

import html
import json
import re
from urllib.parse import quote, urlsplit

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

SOURCE_HEADING = "\n\n参考来源：\n"
_IMAGE_FIELDS = {"imageUrl", "imageUrls", "imageSha256", "originalImageUrl", "imageGallery", "thumbnail", "thumbnailUrl", "coverUrl", "gallery"}


def _source_url(value: object) -> str | None:
    if not isinstance(value, str) or any(ord(char) < 32 or ord(char) == 127 for char in value):
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            return None
    except ValueError:
        return None
    # Parentheses/whitespace cannot terminate a Markdown destination; existing escapes stay intact.
    return quote(value, safe=":/?=&%#@+;,$!-_.~[]")


def _needs_link_details(text: str) -> bool:
    return bool(re.search(r"图片|图源|原图|主图|图集|照片|链接|网址|网站|来源|出处|域名|仓库|sha.?256|哈希|https?://|url|image", text, re.IGNORECASE))


def web_prompt_evidence(payloads: list[dict], *, question: str = "") -> tuple[str, str]:
    facts, links = [], []
    source_numbers = {}
    next_number = 1
    for payload in payloads:
        rows = payload.get("results")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            url = _source_url(row.get("url"))
            if url and url in source_numbers:
                number = source_numbers[url]
            else:
                number = next_number
                next_number += 1
            title = str(row.get("title") or f"来源{number}")
            snippet = str(row.get("snippet") or "")
            text = f"[{number}] {title}\n{snippet}"
            if url:
                text += "\n来源域名：" + str(urlsplit(url).hostname)
                if _needs_link_details(question):
                    text += "\n来源地址：" + url
            # Preserve future semantic fields, not just the current provider's title/snippet schema.
            extra = {key: value for key, value in row.items() if key not in {"title", "snippet", "url"}}
            if extra:
                text += "\n" + json.dumps(extra, ensure_ascii=False, separators=(",", ":"))
            facts.append(text)
            if url and url not in source_numbers:
                source_numbers[url] = number
                label = html.escape(re.sub(r"([\\\[\]])", r"\\\1", title), quote=False)
                links.append(f"[{number}. {label}]({url})")
    return "\n\n".join(facts), SOURCE_HEADING + "\n".join(links) if links else ""


def _without_source_destinations(content: str) -> str:
    body, marker, footer = content.partition(SOURCE_HEADING)
    if not marker:
        return content
    # Only the canonical program-owned footer is compacted; titles and the answer remain available.
    def title_and_domain(match):
        try:
            domain = urlsplit(match[2]).hostname
        except ValueError:
            domain = None
        return match[1] + (f"（{domain}）" if domain else "")
    footer = re.sub(r"\[([^\n]*?)\]\((https?://[^)\s]+)\)", title_and_domain, footer)
    return body + marker + footer


def compact_prompt_messages(messages: list, *, question: str = "") -> list:
    """Return inference-only copies. Explicit media/link questions retain requested transport facts."""
    questions = [str(m.content) for m in messages if isinstance(m, HumanMessage)][-3:]
    preserve_transport = any(_needs_link_details(text) for text in [*questions, question])
    compact = []
    for message in messages:
        if isinstance(message, ToolMessage) and message.name == "kb_search":
            try:
                payload = json.loads(message.content)
                if (isinstance(payload, dict) and type(payload.get("answerable")) is bool
                        and isinstance(payload.get("context"), str)
                        and isinstance(payload.get("hits"), list)):
                    # context already carries complete source text; hits duplicates it with scores.
                    projected = {key: payload[key] for key in
                                 ("answerable", "reason", "context", "citations", "degraded") if key in payload}
                    message = message.model_copy(update={
                        "content": json.dumps(projected, ensure_ascii=False, separators=(",", ":"))})
            except (TypeError, ValueError):
                pass
            compact.append(message)
            continue
        if preserve_transport:
            compact.append(message)
            continue
        if isinstance(message, AIMessage) and isinstance(message.content, str):
            content = _without_source_destinations(str(message.content))
            compact.append(message.model_copy(update={"content": content}) if content != message.content else message)
            continue
        if not isinstance(message, ToolMessage) or message.name not in {"product_search", "product_detail"}:
            compact.append(message)
            continue
        try:
            payload = json.loads(message.content)
            if not isinstance(payload, dict):
                compact.append(message)
                continue
            def facts(row):
                return {key: value for key, value in row.items() if key not in _IMAGE_FIELDS} if isinstance(row, dict) else row
            projected = facts(payload)
            if isinstance(payload.get("products"), list):
                projected["products"] = [facts(row) for row in payload["products"]]
            if isinstance(payload.get("product"), dict):
                projected["product"] = facts(payload["product"])
            compact.append(message.model_copy(update={"content": json.dumps(projected, ensure_ascii=False, separators=(",", ":"))}))
        except (TypeError, ValueError):
            compact.append(message)
    return compact
