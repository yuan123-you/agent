"""联网搜索工具：Tavily 优先（配置了 TAVILY_API_KEY 时），否则 DuckDuckGo 兜底（均免费起步）"""
import asyncio
import logging

from langchain_core.tools import tool

logger = logging.getLogger("ai-service.websearch")


def _search_tavily(query: str, max_results: int) -> list[dict]:
    """Tavily 搜索（同步，线程池执行）；官方 REST API，无需 SDK"""
    import os
    import json
    import urllib.request

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
            "title": item.get("title", ""),
            "snippet": (item.get("content") or "")[:500],
            "url": item.get("url", ""),
        })
    return results


def _search_ddg(query: str, max_results: int) -> list[dict]:
    """DuckDuckGo 搜索兜底（同步，线程池执行）"""
    from duckduckgo_search import DDGS
    results = []
    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=max_results):
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("body", ""),
                "url": item.get("href", ""),
            })
    return results


def _search(query: str, max_results: int) -> tuple[list[dict], str]:
    """Tavily 优先，失败/未配置降级 DuckDuckGo；返回 (结果, 引擎名)"""
    try:
        return _search_tavily(query, max_results), "tavily"
    except Exception as e:
        logger.info("tavily unavailable, fallback to ddg: %s", e)
    return _search_ddg(query, max_results), "duckduckgo"


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
