"""Read-only web search with preferred-provider hedging and cancellable HTTP I/O."""
import asyncio
import html
import logging
import os
import re

import httpx
from langchain_core.tools import tool
from opencc import OpenCC

from app.config import settings

logger = logging.getLogger("ai-service.websearch")
_to_simplified = OpenCC("t2s").convert
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    no_html = re.sub(r"<[^>]+>", "", value)
    return re.sub(r"\s+", " ", _to_simplified(html.unescape(no_html))).strip()


async def _request(client, method, url, **kwargs):
    if client is None:
        async with httpx.AsyncClient(timeout=settings.web_search_timeout_s, follow_redirects=True) as owned:
            return await _request(owned, method, url, **kwargs)
    response = await client.request(method, url, **kwargs)
    response.raise_for_status()
    return response


async def _search_tavily(query: str, max_results: int, *, client=None) -> list[dict]:
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        raise ValueError("TAVILY_API_KEY not configured")
    response = await _request(client, "POST", "https://api.tavily.com/search", follow_redirects=False, json={
        "api_key": api_key, "query": query, "max_results": max_results, "search_depth": "basic",
    })
    return [{"title": _clean_text(item.get("title")), "snippet": _clean_text(item.get("content"))[:500],
             "url": item.get("url", "")} for item in response.json().get("results", [])]


async def _search_searxng(query: str, max_results: int, *, client=None) -> list[dict]:
    base = os.environ.get("SEARXNG_URL", "").rstrip("/")
    if not base:
        raise ValueError("SEARXNG_URL not configured")
    response = await _request(client, "GET", base + "/search", params={"q": query, "format": "json", "language": "zh-CN"},
                              headers={**_HEADERS, "Accept": "application/json"})
    results = []
    for item in response.json().get("results", []):
        title = _clean_text(item.get("title"))
        href = item.get("url", "").strip()
        if title and href:
            results.append({"title": title, "snippet": _clean_text(item.get("content") or item.get("snippet"))[:500], "url": href})
            if len(results) >= max_results:
                break
    return results


async def _search_bing(query: str, max_results: int, *, client=None) -> list[dict]:
    response = await _request(client, "GET", "https://cn.bing.com/search", params={"q": query}, headers=_HEADERS)
    content = response.content.decode("utf-8", errors="ignore")
    results = []
    for item in re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', content, re.DOTALL):
        title_match = re.search(r'<h2[^>]*><a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>', item, re.DOTALL)
        if not title_match:
            continue
        href, title = title_match.group(1).strip(), _clean_text(title_match.group(2))
        snippet = re.search(r"<p[^>]*>(.*?)</p>", item, re.DOTALL)
        if title and href:
            results.append({"title": title, "snippet": _clean_text(snippet.group(1))[:500] if snippet else "", "url": href})
            if len(results) >= max_results:
                break
    return results


async def _search_sogou(query: str, max_results: int, *, client=None) -> list[dict]:
    response = await _request(client, "GET", "https://www.sogou.com/web", params={"query": query}, headers=_HEADERS)
    content = response.content.decode("utf-8", errors="ignore")
    results = []
    blocks = re.findall(r'<h3[^>]*>.*?<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?</h3>(.*?)(?=<h3|$)', content, re.DOTALL)
    for href, raw_title, rest in blocks:
        title = _clean_text(raw_title)
        if not title or ("sogou.com" in href and "query=" in href):
            continue
        if href.startswith("/"):
            href = "https://www.sogou.com" + href
        snippet = re.search(r'<p class="(?:txt-info|star-wiki|str-info)"[^>]*>(.*?)</p>', rest, re.DOTALL)
        if not snippet:
            snippet = re.search(r'<div class="space-txt"[^>]*>(.*?)</div>', rest, re.DOTALL)
        text = _clean_text(snippet.group(1))[:500] if snippet else _clean_text(re.sub(r"<[^>]+>", " ", rest))[:200]
        results.append({"title": title, "snippet": text, "url": href})
        if len(results) >= max_results:
            break
    return results


async def _search(query: str, max_results: int) -> tuple[list[dict], str]:
    providers = []
    if os.environ.get("TAVILY_API_KEY"):
        providers.append(("tavily", _search_tavily))
    if os.environ.get("SEARXNG_URL"):
        providers.append(("searxng", _search_searxng))
    providers.extend([("bing", _search_bing), ("sogou", _search_sogou)])
    loop = asyncio.get_running_loop()
    deadline = loop.time() + settings.web_search_total_timeout_s
    all_tasks = []
    completed_ok = False

    def result(task, name):
        nonlocal completed_ok
        try:
            rows = task.result()
            completed_ok = True
            return rows
        except Exception as e:
            logger.info("web search provider %s unavailable: %s", name, type(e).__name__)
            return []

    async with httpx.AsyncClient(timeout=settings.web_search_timeout_s, follow_redirects=True) as client:
        pending = {}
        try:
            name, provider = providers[0]
            first = asyncio.create_task(provider(query, max_results, client=client))
            all_tasks.append(first)
            pending[first] = name
            grace = min(settings.web_search_hedge_delay_s, max(0, deadline - loop.time()))
            done, _ = await asyncio.wait([first], timeout=grace)
            if done:
                rows = result(first, name)
                pending.pop(first)
                if rows:
                    return rows, name
            for name, provider in providers[1:]:
                task = asyncio.create_task(provider(query, max_results, client=client))
                all_tasks.append(task)
                pending[task] = name
            priority = {name: index for index, (name, _) in enumerate(providers)}
            while pending:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise TimeoutError("web search exceeded its total deadline")
                done, _ = await asyncio.wait(pending, timeout=remaining, return_when=asyncio.FIRST_COMPLETED)
                if not done:
                    raise TimeoutError("web search exceeded its total deadline")
                for task in sorted(done, key=lambda t: priority[pending[t]]):
                    name = pending.pop(task)
                    rows = result(task, name)
                    if rows:
                        return rows, name
            if completed_ok:
                return [], providers[-1][0]
            raise RuntimeError("all configured search providers unavailable")
        finally:
            for task in all_tasks:
                if not task.done():
                    task.cancel()
            # Cancellation closes in-flight HTTP responses, not merely the caller's wait.
            await asyncio.gather(*all_tasks, return_exceptions=True)


@tool
async def web_search(query: str, max_results: int = 5) -> dict:
    """联网检索真实网络信息，返回标题、摘要与链接。适用于新闻、最新产品、价格等外部资讯。
    回答须基于真实搜索结果并标注【联网搜索】，不得把外站信息当作平台承诺。"""
    try:
        results, engine = await asyncio.wait_for(_search(query, max_results), timeout=settings.web_search_total_timeout_s)
        return {"results": results, "total": len(results), "engine": engine,
                "note": "以下内容来自互联网搜索，回答开头需标注【联网搜索】"}
    except Exception as e:
        logger.warning("web_search unavailable: %s", type(e).__name__)
        return {"results": [], "total": 0, "error": "联网搜索暂时不可用，请告知用户稍后再试"}
