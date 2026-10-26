import json
import pytest

from app.tools import web_search


class _JsonResponse:
    def __init__(self, data: dict):
        self._payload = json.dumps(data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return self._payload


class _HtmlResponse:
    def __init__(self, html_content: str):
        self._html = html_content.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return self._html


def test_tavily_results_decode_entities_and_use_simplified_chinese(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: _JsonResponse({
            "results": [{
                "title": "電競手機推薦與什麼手機最適合打遊戲與 &#x20;",
                "content": "效能比較 &amp; 選購建議",
                "url": "https://example.com",
            }]
        })
    )

    result = web_search._search_tavily("電競手機", 1)

    assert result == [{
        "title": "电竞手机推荐与什么手机最适合打游戏与",
        "snippet": "效能比较 & 选购建议",
        "url": "https://example.com",
    }]


def test_searxng_results_extract_and_normalize_clean_text(monkeypatch):
    monkeypatch.setenv("SEARXNG_URL", "http://searxng.local:8080")
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: _JsonResponse({
            "query": "折叠屏手机",
            "results": [
                {
                    "title": "2026 最新<b>折疊屏</b>旗艦評測",
                    "content": "全面解析鉸鏈耐用度與<b>相機</b>表現 &amp; 續航情況。",
                    "url": "https://example.com/foldable",
                },
                {
                    "title": "折叠屏手机选购指南",
                    "snippet": "各大品牌折叠屏综合对比。",
                    "url": "https://example.com/guide",
                }
            ]
        })
    )

    results = web_search._search_searxng("折叠屏手机", max_results=2)

    assert len(results) == 2
    assert results[0] == {
        "title": "2026 最新折叠屏旗舰评测",
        "snippet": "全面解析铰链耐用度与相机表现 & 续航情况。",
        "url": "https://example.com/foldable",
    }
    assert results[1] == {
        "title": "折叠屏手机选购指南",
        "snippet": "各大品牌折叠屏综合对比。",
        "url": "https://example.com/guide",
    }


def test_bing_results_extract_and_normalize_clean_text(monkeypatch):
    sample_html = """
    <html><body>
    <li class="b_algo">
        <h2><a href="https://example.com/item1"><strong>電競</strong>旗艦手機&#x20;評測</a></h2>
        <p>這款手機<strong>效能</strong>強大，續航表現出色 &amp; 散熱優秀。</p>
    </li>
    <li class="b_algo">
        <h2><a href="https://example.com/item2">最新款遊戲手機排行榜</a></h2>
        <p>提供多維度性能對比。</p>
    </li>
    </body></html>
    """
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: _HtmlResponse(sample_html))

    results = web_search._search_bing("电竞手机", max_results=2)

    assert len(results) == 2
    assert results[0] == {
        "title": "电竞旗舰手机 评测",
        "snippet": "这款手机效能强大，续航表现出色 & 散热优秀。",
        "url": "https://example.com/item1",
    }
    assert results[1] == {
        "title": "最新款游戏手机排行榜",
        "snippet": "提供多维度性能对比。",
        "url": "https://example.com/item2",
    }


def test_sogou_results_extract_and_normalize_clean_text(monkeypatch):
    sample_html = """
    <html><body>
    <h3><a href="https://example.com/sogou1">搜狗<strong>熱門</strong>手機資訊</a></h3>
    <p class="txt-info">這是一篇關於<strong>手機</strong>性價比評測的文章。</p>
    </body></html>
    """
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: _HtmlResponse(sample_html))

    results = web_search._search_sogou("手机资讯", max_results=1)

    assert len(results) == 1
    assert results[0]["title"] == "搜狗热门手机资讯"
    assert "性价比评测" in results[0]["snippet"]
    assert results[0]["url"] == "https://example.com/sogou1"


def test_search_falls_back_to_searxng_when_configured(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setenv("SEARXNG_URL", "http://searxng.local:8080")
    monkeypatch.setattr(
        web_search,
        "_search_searxng",
        lambda query, max_results: [{"title": "SearXNG手机", "snippet": "自建元搜索结果", "url": "https://searx.example.com"}]
    )

    results, engine = web_search._search("手机", 1)

    assert engine == "searxng"
    assert len(results) == 1
    assert results[0]["title"] == "SearXNG手机"


def test_search_falls_back_to_bing_when_searxng_not_set(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    monkeypatch.setattr(
        web_search,
        "_search_bing",
        lambda query, max_results: [{"title": "Bing手机", "snippet": "国内直连结果", "url": "https://bing.example.com"}]
    )

    results, engine = web_search._search("手机", 1)

    assert engine == "bing"
    assert len(results) == 1
    assert results[0]["title"] == "Bing手机"


def test_search_falls_back_to_sogou_when_bing_fails(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    monkeypatch.setattr(web_search, "_search_bing", lambda query, max_results: [])
    monkeypatch.setattr(
        web_search,
        "_search_sogou",
        lambda query, max_results: [{"title": "搜狗手机", "snippet": "备用结果", "url": "https://sogou.com"}]
    )

    results, engine = web_search._search("手机", 1)

    assert engine == "sogou"
    assert len(results) == 1
    assert results[0]["title"] == "搜狗手机"


@pytest.mark.asyncio
async def test_web_search_tool_handles_searxng_results(monkeypatch):
    monkeypatch.setattr(
        web_search,
        "_search",
        lambda query, max_results: ([{"title": "SearXNG测试", "snippet": "内容摘要", "url": "https://test.com"}], "searxng")
    )

    result = await web_search.web_search.ainvoke({"query": "手机推荐", "max_results": 1})

    assert result["total"] == 1
    assert result["engine"] == "searxng"
    assert result["results"][0]["title"] == "SearXNG测试"
    assert "以下内容来自互联网搜索" in result["note"]
