from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from app.agent import nodes
from app.agent.graph import build_graph
from app.tools.tools import set_tool_ctx

class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        # UTC is still Wednesday; in Shanghai it is already Thursday.
        instant = datetime(2026, 10, 28, 17, 0, tzinfo=timezone.utc)
        return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

@pytest.mark.parametrize('text, date, weekday', [
    ('今天星期几?', '2026年10月29日', '星期四'),
    ('明天星期几?', '2026年10月30日', '星期五'),
    ('昨天是周几？', '2026年10月28日', '星期三'),
    ('后天几号', '2026年10月31日', '星期六'),
    ('前天是几号？', '2026年10月27日', '星期二'),
])
async def test_relative_dates_are_local_answers_even_with_web_enabled(monkeypatch, text, date, weekday):
    set_tool_ctx({})
    monkeypatch.setattr(nodes, 'datetime', FixedDateTime)
    forbidden = MagicMock(side_effect=AssertionError('Date queries must not construct or call a remote model'))
    monkeypatch.setattr(nodes, 'get_chat_llm', forbidden)
    monkeypatch.setattr(nodes, 'get_intent_llm', forbidden)
    result = await build_graph(MemorySaver()).ainvoke(
        {'messages': [HumanMessage(content=text)], 'user_id': '1', 'conversation_id': '1', 'web_search_enabled': True},
        {'configurable': {'thread_id': 'relative-date'}})
    answer = result['messages'][-1].content
    assert date in answer and weekday in answer
    assert '商品' not in answer
    forbidden.assert_not_called()

@pytest.mark.parametrize('text', ['明天几点发货', '明天星期几，顺便推荐手机', '明天退货运费谁付'])
def test_mixed_requests_are_not_swallowed_by_date_shortcut(text):
    assert not nodes.TIME_QUERY_RE.fullmatch(text)
