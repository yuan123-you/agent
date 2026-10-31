"""Named current policy context is reserved before source approval, not an intent word rule."""
import asyncio
from unittest.mock import AsyncMock

import pytest
from app.rag.retrieval import RetrievalCandidate, RetrievalPipeline


def raw(chunk_id, *, score=.9, kind='POLICY', product=-1):
    return {'chunk_id':chunk_id,'doc_id':1,'product_id':product,'docType':kind,
            'content':f'完整证据{chunk_id}','source':'平台政策','score':score}


def context(chunk_id=99, *, product=-1):
    return RetrievalCandidate(chunk_id,1,product,'POLICY','完整的优先适用规则','平台政策')


def pipeline(priority, *, score=.9, kind='POLICY', ids=(1,2,3,4)):
    vector=AsyncMock(return_value={'hits':[raw(i,score=score,kind=kind) for i in ids]})
    return RetrievalPipeline(vector_search=vector,bm25_search=AsyncMock(return_value={'hits':[]}),
                             reranker=None,policy_context_search=priority)


async def test_current_priority_section_is_reserved_before_four_source_approval():
    lookup=AsyncMock(return_value=[context()])
    result=await pipeline(lookup).search('一般政策问题',product_id=-1)
    assert result.answerable
    assert [h.chunk_id for h in result.hits]==[99,1,2,3]
    assert [c.chunk_id for c in result.citations]==[99,1,2,3]
    assert result.hits[0].content=='完整的优先适用规则'
    assert 'policy_context' in result.hits[0].matched_by
    lookup.assert_awaited_once()


async def test_policy_context_cannot_turn_an_unrelated_query_into_an_answer():
    lookup=AsyncMock(return_value=[context()])
    result=await pipeline(lookup,score=.1).search('无相关依据的问题',product_id=-1)
    assert not result.answerable and not result.citations
    lookup.assert_not_awaited()


@pytest.mark.parametrize('failure',['missing','exception','wrong-scope'])
async def test_missing_current_policy_context_fails_closed(failure):
    lookup=AsyncMock(return_value=[] if failure=='missing' else [context(product=7)])
    if failure=='exception':lookup.side_effect=RuntimeError('lookup unavailable')
    result=await pipeline(lookup).search('政策问题',product_id=-1)
    assert not result.answerable and not result.citations
    assert result.reason=='retrieval_unavailable' and result.degraded
    assert 'policy_context_unavailable' in result.degraded_reasons


async def test_an_already_recalled_priority_chunk_is_not_duplicated():
    lookup=AsyncMock(return_value=[context(1)])
    result=await pipeline(lookup).search('政策问题',product_id=-1)
    assert result.answerable and [c.chunk_id for c in result.citations]==[1,2,3,4]


async def test_non_policy_retrieval_does_not_inherit_platform_policy_context():
    lookup=AsyncMock(return_value=[context()])
    result=await pipeline(lookup,kind='SPEC').search('商品规格',doc_type='SPEC',product_id=-1)
    assert result.answerable
    lookup.assert_not_awaited()


async def test_policy_context_request_cancellation_propagates():
    lookup=AsyncMock(side_effect=asyncio.CancelledError)
    with pytest.raises(asyncio.CancelledError):
        await pipeline(lookup).search('政策问题',product_id=-1)

async def test_named_context_lookup_uses_current_backend_scope_and_exact_heading(monkeypatch):
    from types import SimpleNamespace
    from app.rag import retrieval
    from app.clients.backend_client import backend_client
    monkeypatch.setattr(retrieval,'settings',SimpleNamespace(**{**retrieval.settings.model_dump(),
        'rag_policy_context_queries':['当前演示操作边界']}))
    exact={**raw(99),'content':'# 平台规则\n## 当前演示操作边界（优先适用）\n完整边界'}
    mention={**raw(100),'content':'# 其他章节\n本文提到当前演示操作边界，但不是该章节。'}
    search=AsyncMock(return_value={'hits':[exact,mention]})
    monkeypatch.setattr(backend_client,'kb_keyword_search',search)
    retrieval.get_retrieval_pipeline.cache_clear()
    try:
        result=await retrieval.get_retrieval_pipeline()._policy_context_search()
        assert [hit.chunk_id for hit in result]==[99]
        search.assert_awaited_once_with('当前演示操作边界',doc_type='POLICY',product_id=-1,top_k=4)
    finally:
        retrieval.get_retrieval_pipeline.cache_clear()


async def test_all_configured_current_sections_are_required(monkeypatch):
    from types import SimpleNamespace
    from app.rag import retrieval
    from app.clients.backend_client import backend_client
    titles=['当前演示操作边界','5.1 七天无理由退货的条件性说明']
    monkeypatch.setattr(retrieval,'settings',SimpleNamespace(**{**retrieval.settings.model_dump(),
        'rag_policy_context_queries':titles}))
    calls=[]
    async def lookup(query,**kwargs):
        calls.append(query)
        return {'hits':[{**raw(99),'content':'# 平台规则\n## 当前演示操作边界\n完整边界'}]}
    monkeypatch.setattr(backend_client,'kb_keyword_search',lookup)
    retrieval.get_retrieval_pipeline.cache_clear()
    try:
        pipe=retrieval.get_retrieval_pipeline()
        pipe._vector_search=AsyncMock(return_value={'hits':[raw(1)]})
        pipe._bm25_search=AsyncMock(return_value={'hits':[]})
        result=await pipe.search('政策问题',product_id=-1)
        assert not result.answerable and result.reason=='retrieval_unavailable'
        assert set(calls)==set(titles)
    finally:
        retrieval.get_retrieval_pipeline.cache_clear()


async def test_two_priority_sections_still_reserve_query_evidence_and_complete_blocks():
    result=await pipeline(AsyncMock(return_value=[context(99),context(98)])).search('政策问题',product_id=-1)
    assert result.answerable
    assert [hit.chunk_id for hit in result.hits]==[99,98,1,2]
    assert [citation.chunk_id for citation in result.citations]==[99,98,1,2]

@pytest.mark.parametrize('bad_kind',['prefix-heading','wrong-scope'])
async def test_each_required_section_is_exact_and_in_scope_before_combining(monkeypatch,bad_kind):
    from types import SimpleNamespace
    from app.rag import retrieval
    from app.clients.backend_client import backend_client
    names=['当前演示操作边界','5.1 七天无理由退货的条件性说明']
    monkeypatch.setattr(retrieval,'settings',SimpleNamespace(**{**retrieval.settings.model_dump(),
        'rag_policy_context_queries':names}))
    async def lookup(query,**kwargs):
        second=query==names[1]
        header=query+' 其他业务说明' if second and bad_kind=='prefix-heading' else query
        product=7 if second and bad_kind=='wrong-scope' else -1
        return {'hits':[{**raw(98 if second else 99,product=product),'content':'# 平台规则\n## '+header+'\n完整边界'}]}
    monkeypatch.setattr(backend_client,'kb_keyword_search',lookup)
    retrieval.get_retrieval_pipeline.cache_clear()
    try:
        pipe=retrieval.get_retrieval_pipeline()
        pipe._vector_search=AsyncMock(return_value={'hits':[raw(1)]})
        pipe._bm25_search=AsyncMock(return_value={'hits':[]})
        result=await pipe.search('政策问题',product_id=-1)
        assert not result.answerable and not result.citations and result.reason=='retrieval_unavailable'
    finally:
        retrieval.get_retrieval_pipeline.cache_clear()
