"""联网搜索工具：
1. Tavily 优先（商业高精度搜索，配置 TAVILY_API_KEY 时）
2. SearXNG（开源自建元搜索引擎，配置 SEARXNG_URL 时）
3. Bing 网页搜索（免 API Key，海外与国内直连极速稳定，无 Cloudflare 机房验证拦截）
4. Sogou 搜狗搜索（免 API Key，国内中文电商行情与时效资讯兜底）
"""
import asyncio
import html
import logging
import os
import re
import urllib.parse
import urllib.request

from langchain_core.tools import tool
from opencc import OpenCC

from app.config import settings

logger = logging.getLogger("ai-service.websearch")
_to_simplified = OpenCC("t2s").convert


def _clean_text(value: str | None) -> str:
    """Decode entities, strip HTML tags, normalize whitespace, and convert to Simplified Chinese."""
    if not value:
        return ""
    no_html = re.sub(r"<[^>]+>", "", value)
    normalized = _to_simplified(html.unescape(no_html))
    return re.sub(r"\s+", " ", normalized).strip()


def _search_tavily(query: str, max_results: int) -> list[dict]:
    """Tavily 搜索（官方 REST API，配置了 TAVILY_API_KEY 时可用）"""
    import json

    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        raise ValueError("TAVILY_API_KEY not configured")
    payload = json.dumps({
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
    }).encode()
    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    results = []
    for item in data.get("results", []):
        results.append({
            "title": _clean_text(item.get("title")),
            "snippet": _clean_text(item.get("content"))[:500],
            "url": item.get("url", ""),
        })
    return results


def _search_searxng(query: str, max_results: int) -> list[dict]:
    """SearXNG 元搜索（配置了 SEARXNG_URL 时可用，支持私有化部署聚合搜索）"""
    import json

    base_url = os.environ.get("SEARXNG_URL", "").rstrip("/")
    if not base_url:
        raise ValueError("SEARXNG_URL not configured")

    params = {
        "q": query,
        "format": "json",
        "language": "zh-CN",
    }
    url = f"{base_url}/search?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="ignore"))

    results = []
    for item in data.get("results", []):
        title = _clean_text(item.get("title"))
        snippet = _clean_text(item.get("content") or item.get("snippet"))[:500]
        href = item.get("url", "").strip()
        if title and href:
            results.append({
                "title": title,
                "snippet": snippet,
                "url": href,
            })
            if len(results) >= max_results:
                break
    return results


def _search_bing(query: str, max_results: int) -> list[dict]:
    """Bing 网页搜索（免 API Key，同步，线程池执行）"""
    url = "https://cn.bing.com/search?q=" + urllib.parse.quote(query)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        html_text = resp.read().decode("utf-8", errors="ignore")

    items = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html_text, re.DOTALL)
    results = []
    for item in items:
        title_match = re.search(r'<h2[^>]*><a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>', item, re.DOTALL)
        if not title_match:
            continue
        href = title_match.group(1).strip()
        raw_title = title_match.group(2)
        title = _clean_text(re.sub(r"<[^>]+>", "", raw_title))

        snippet_match = re.search(r"<p[^>]*>(.*?)</p>", item, re.DOTALL)
        snippet = ""
        if snippet_match:
            snippet = _clean_text(re.sub(r"<[^>]+>", "", snippet_match.group(1)))[:500]

        if title and href:
            results.append({
                "title": title,
                "snippet": snippet,
                "url": href,
            })
            if len(results) >= max_results:
                break
    return results


def _search_sogou(query: str, max_results: int) -> list[dict]:
    """Sogou 搜狗搜索（免 API Key，同步，线程池执行）"""
    url = "https://www.sogou.com/web?query=" + urllib.parse.quote(query)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        content = resp.read().decode("utf-8", errors="ignore")

    results = []
    h3_blocks = re.findall(
        r'<h3[^>]*>.*?<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?</h3>(.*?)(?=<h3|$)',
        content, re.DOTALL,
    )
    for href, raw_title, rest in h3_blocks:
        title = _clean_text(re.sub(r"<[^>]+>", "", raw_title))
        if not title or ("sogou.com" in href and "query=" in href):
            continue
        if href.startswith("/"):
            href = "https://www.sogou.com" + href
        snippet_match = re.search(r'<p class="(?:txt-info|star-wiki|str-info)"[^>]*>(.*?)</p>', rest, re.DOTALL)
        if not snippet_match:
            snippet_match = re.search(r'<div class="space-txt"[^>]*>(.*?)</div>', rest, re.DOTALL)
        snippet = ""
        if snippet_match:
            snippet = _clean_text(re.sub(r"<[^>]+>", "", snippet_match.group(1)))[:500]
        else:
            snippet = _clean_text(re.sub(r"<[^>]+>", " ", rest))[:200]

        results.append({"title": title, "snippet": snippet, "url": href})
        if len(results) >= max_results:
            break
    return results


def _search(query: str, max_results: int) -> tuple[list[dict], str]:
    """多级搜索策略：
    1. Tavily 优先（商业 API，配置 TAVILY_API_KEY 时）
    2. SearXNG（开源自建元搜索引擎，配置 SEARXNG_URL 时）
    3. Bing 网页搜索（免 Key，海外与国内直连极速稳定，无 Cloudflare 机房验证拦截）
    4. Sogou 搜狗搜索（免 Key，国内中文电商与时效资讯兜底）
    """
    try:
        return _search_tavily(query, max_results), "tavily"
    except Exception as e:
        logger.info("tavily unavailable (%s), trying searxng...", e)

    try:
        results = _search_searxng(query, max_results)
        if results:
            return results, "searxng"
    except Exception as e:
        logger.info("searxng unavailable (%s), trying bing...", e)

    try:
        results = _search_bing(query, max_results)
        if results:
            return results, "bing"
    except Exception as e:
        logger.info("bing search unavailable (%s), trying sogou...", e)

    return _search_sogou(query, max_results), "sogou"


@tool
async def web_search(query: str, max_results: int = 5) -> dict:
    """联网搜索最新网络信息。适用于：最新产品/新闻/价格/时效性问题，
    或商品库与知识库都无法回答的问题。返回网络搜索结果（标题+摘要+链接），
    回答时必须基于这些结果，并在回答开头标注"【联网搜索】"。"""
    try:
        results, engine = await asyncio.to_thread(_search, query, max_results)
        return {
            "results": results,
            "total": len(results),
            "engine": engine,
            "note": "以下内容来自互联网搜索，回答开头需标注【联网搜索】",
        }
    except Exception as e:
        logger.warning("web_search failed: %s", e)
        return {"results": [], "total": 0, "error": "联网搜索暂时不可用，请告知用户稍后再试"}
