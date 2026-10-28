"""Bounded async fallback and cancellation of slow/infinite provider response bodies."""
import asyncio,time
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx,pytest
from app.tools import web_search as search

RESULT=[{'title':'真实检索','snippet':'真实返回','url':'https://example.com/source'}]

def config(monkeypatch,*,deadline=0.15,grace=0.02):
    monkeypatch.setattr(search,'settings',SimpleNamespace(web_search_hedge_delay_s=grace,web_search_total_timeout_s=deadline,web_search_timeout_s=4))
    monkeypatch.delenv('TAVILY_API_KEY',raising=False)

async def test_a_slow_preferred_provider_does_not_block_a_fast_fallback(monkeypatch):
    config(monkeypatch);monkeypatch.setenv('SEARXNG_URL','http://search.local')
    canceled=asyncio.Event()
    async def slow(*args,**kwargs):
        try: await asyncio.sleep(1)
        finally: canceled.set()
    monkeypatch.setattr(search,'_search_searxng',slow)
    monkeypatch.setattr(search,'_search_bing',AsyncMock(return_value=RESULT))
    monkeypatch.setattr(search,'_search_sogou',AsyncMock(return_value=[]))
    started=time.perf_counter()
    result,engine=await search._search('真实问题',3)
    assert time.perf_counter()-started < 0.3
    assert result==RESULT and engine=='bing'
    assert canceled.is_set()

async def test_no_evidence_arriving_before_the_total_deadline_is_reported_as_a_timeout(monkeypatch):
    config(monkeypatch,deadline=0.04,grace=0.01);monkeypatch.delenv('SEARXNG_URL',raising=False)
    async def slow(*args,**kwargs): await asyncio.sleep(1); return RESULT
    monkeypatch.setattr(search,'_search_bing',slow);monkeypatch.setattr(search,'_search_sogou',slow)
    with pytest.raises(TimeoutError): await search._search('真实问题',3)

async def test_tool_deadline_includes_the_orchestration_call(monkeypatch):
    config(monkeypatch,deadline=0.04)
    canceled=asyncio.Event()
    async def delayed(*args):
        try: await asyncio.sleep(1); return RESULT,'bing'
        finally: canceled.set()
    monkeypatch.setattr(search,'_search',delayed)
    started=time.perf_counter()
    result=await search.web_search.ainvoke({'query':'真实问题','max_results':3})
    assert time.perf_counter()-started < 0.2
    assert result.get('error') and not result['results']
    assert canceled.is_set()

async def test_trickling_losers_are_closed_and_cannot_starve_later_fast_searches(monkeypatch):
    config(monkeypatch,deadline=0.1,grace=0.001);monkeypatch.delenv('SEARXNG_URL',raising=False)
    streams=[];fast=False
    class Trickle(httpx.AsyncByteStream):
        closed=False
        async def __aiter__(self):
            while True:
                yield b'x'
                await asyncio.sleep(0.002)
        async def aclose(self): self.closed=True
    def handle(request):
        if fast:
            return httpx.Response(200,text='<li class="b_algo"><h2><a href="https://example.com/source">真实检索</a></h2><p>真实返回</p></li>')
        stream=Trickle();streams.append(stream)
        return httpx.Response(200,stream=stream)
    original=httpx.AsyncClient
    monkeypatch.setattr(search.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handle),**kw))
    results=await asyncio.gather(*(search.web_search.ainvoke({'query':f'问题{i}'}) for i in range(4)))
    assert all(item.get('error') for item in results)
    assert streams and all(stream.closed for stream in streams)
    fast=True
    result=await search.web_search.ainvoke({'query':'后续请求'})
    assert result['results']==RESULT and result['engine']=='bing'
