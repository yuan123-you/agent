import json

from app.tools import web_search


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return json.dumps({
            "results": [{
                "title": "電競手機推薦與什麼手機最適合打遊戲與 &#x20;",
                "content": "效能比較 &amp; 選購建議",
                "url": "https://example.com",
            }]
        }).encode()


def test_tavily_results_decode_entities_and_use_simplified_chinese(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: _Response())

    result = web_search._search_tavily("電競手機", 1)

    assert result == [{
        "title": "电竞手机推荐与什么手机最适合打游戏与",
        "snippet": "效能比较 & 选购建议",
        "url": "https://example.com",
    }]
