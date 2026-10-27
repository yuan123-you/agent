"""Regression coverage for the retrieval/product audit (offline boundaries)."""
from types import SimpleNamespace
from unittest.mock import AsyncMock


import pytest
from app.rag import ingest, product_index, retrieval, vectorstore
from app.tools import tools
from app.rag.citations import validate_citations


@pytest.fixture(autouse=True)
def isolated_tool_context(monkeypatch):
    tools.set_tool_ctx({"user_id": 1, "active_entities": {}})
    monkeypatch.setattr(product_index, "_get_product_reranker", lambda: None)
    yield
    tools.set_tool_ctx({})


@pytest.mark.asyncio
async def test_empty_successful_catalog_sync_must_clear_old_products(monkeypatch):
    corpus = product_index.ProductCorpus()
    corpus.products = {1: {"productId": 1, "name": "now off shelf", "price": 99}}
    monkeypatch.setattr(ingest, "get_product_corpus", lambda: corpus)
    monkeypatch.setattr(product_index, "get_product_corpus", lambda: corpus)
    monkeypatch.setattr(ingest.backend_client, "products_all", AsyncMock(return_value=[]))
    await ingest.sync_products()
    result = await product_index.hybrid_product_search(None, None, None, None)
    assert result is None or result["products"] == [], result


@pytest.mark.asyncio
async def test_explicit_category_must_not_be_silently_relaxed(monkeypatch):
    corpus = product_index.ProductCorpus()
    products = [
        {"productId": 1, "name": "拍照手机", "category": "PHONE", "price": 999},
        {"productId": 2, "name": "办公笔记本", "category": "LAPTOP", "price": 1999},
        {"productId": 3, "name": "运动鞋", "category": "SHOES", "price": 99},
    ]
    corpus.rebuild(products, [p["name"] for p in products])
    monkeypatch.setattr(product_index, "get_product_corpus", lambda: corpus)
    monkeypatch.setattr(product_index, "get_product_index", lambda: SimpleNamespace(vector_recall=AsyncMock(return_value=[])))
    result = await product_index.hybrid_product_search("拍照", "LAPTOP", None, None)
    assert all(p["category"] == "LAPTOP" for p in result["products"]), result


@pytest.mark.asyncio
async def test_stale_vector_scalars_must_not_bypass_current_budget(monkeypatch):
    # Current corpus was refreshed, but vector update failed: old vector price is 100.
    corpus = product_index.ProductCorpus()
    corpus.products = {1: {"productId": 1, "name": "phone", "category": "PHONE", "price": 1000}}
    monkeypatch.setattr(product_index, "get_product_corpus", lambda: corpus)
    monkeypatch.setattr(product_index, "get_product_index", lambda: SimpleNamespace(vector_recall=AsyncMock(return_value=[(1, 0.9)])))
    result = await product_index.hybrid_product_search("phone", "PHONE", None, 500)
    assert all(float(p["price"]) <= 500 for p in result["products"]), result


@pytest.mark.asyncio
async def test_fourth_product_reference_must_not_resolve_to_first(monkeypatch):
    tools.set_tool_ctx({"user_id": 1, "latest_user_text": "第四款的参数是什么", "active_entities": {
        "last_products": [{"id": 101 + i, "name": str(i)} for i in range(5)]}})
    detail = AsyncMock(return_value={})
    monkeypatch.setattr(tools.backend_client, "product_detail", detail)
    await tools.product_detail.ainvoke({})
    assert detail.await_args.kwargs["product_id"] == 104, detail.await_args


def kb_result(chunk_id, title):
    return retrieval.RetrievalResult(
        True, "high_confidence", (), f'<source id="S1" chunk_id="{chunk_id}" title="{title}">正文</source>',
        (retrieval.Citation("S1", chunk_id, title),), False, ())


@pytest.mark.asyncio
async def test_multiple_kb_calls_must_keep_unique_correct_citations(monkeypatch):
    pipeline = SimpleNamespace(search=AsyncMock(side_effect=[kb_result(101, "退货政策"), kb_result(202, "保修政策")]))
    monkeypatch.setattr(retrieval, "get_retrieval_pipeline", lambda: pipeline)
    first = await tools.kb_search.ainvoke({"query": "退货"})
    second = await tools.kb_search.ainvoke({"query": "保修"})
    ctx = tools.get_tool_ctx()
    validation = validate_citations("退货期限为七天[S1]", allowed=ctx["rag_allowed_citations"], answerable=ctx["rag_answerable"])
    # Existing code accepts S1, but maps the first answer's citation to the second document.
    assert validation.citations[0]["chunk_id"] == first["citations"][0]["chunk_id"], {
        "first": first["citations"], "second": second["citations"], "validated": validation.citations}


@pytest.mark.asyncio
async def test_current_chunk_validation_outage_must_be_reported_unavailable(monkeypatch):
    store = vectorstore.VectorStore.__new__(vectorstore.VectorStore)
    store.embeddings = SimpleNamespace(aembed_query=AsyncMock(return_value=[0.1, 0.2]))
    store.client = SimpleNamespace(search=lambda **kwargs: [[{
        "id": 11, "distance": 0.95,
        "entity": {"content": "政策", "doc_id": 1, "product_id": -1, "doc_type": "POLICY"}}]])
    monkeypatch.setattr(vectorstore.backend_client, "_post", AsyncMock(return_value={"error": "backend offline"}))
    pipeline = retrieval.RetrievalPipeline(vector_search=store.search,
        bm25_search=AsyncMock(side_effect=RuntimeError("backend offline")), reranker=None)
    result = await pipeline.search("退货")
    assert result.reason == "retrieval_unavailable", result


@pytest.mark.asyncio
async def test_post_topk_filter_can_starve_an_existing_product_answer(monkeypatch):
    # Ranked #21 is the first candidate valid for the requested product.
    records = [{"chunk_id": i, "doc_id": i, "product_id": 999 if i <= 20 else 7,
        "docType": "FAQ", "content": "七天退货", "source": "policy", "score": 100.0}
        for i in range(1, 22)]
    async def recall(query, *, top_k, doc_type="ALL", product_id=None):
        scoped = [r for r in records if product_id is None or r["product_id"] in (product_id, -1, None)]
        return {"hits": scoped[:top_k]}
    monkeypatch.setattr(retrieval.settings, "rag_vector_recall_k", 20)
    monkeypatch.setattr(retrieval.settings, "rag_bm25_recall_k", 20)
    pipeline = retrieval.RetrievalPipeline(vector_search=recall, bm25_search=recall, reranker=None)
    result = await pipeline.search("退货", product_id=7)
    assert result.answerable, result


@pytest.mark.asyncio
async def test_legacy_only_vector_must_be_searchable_after_ingest(monkeypatch):
    active_rows = []
    store = vectorstore.VectorStore.__new__(vectorstore.VectorStore)
    store.embeddings = SimpleNamespace(aembed_query=AsyncMock(return_value=[0.1, 0.2]))
    def insert(**kwargs):
        active_rows.extend(kwargs["data"])
    store.client = SimpleNamespace(
        has_collection=lambda name: True,
        query=lambda **kwargs: [{"id": 101}] if kwargs["collection_name"] == "audit_legacy" else [],
        insert=insert,
        search=lambda **kwargs: [[{"id": row["id"], "distance": 0.95, "entity": row} for row in active_rows]],
    )
    monkeypatch.setattr(vectorstore.settings, "milvus_collection", "audit_current")
    monkeypatch.setattr(vectorstore.settings, "milvus_legacy_collections", "audit_legacy")
    monkeypatch.setattr(ingest, "get_vectorstore", lambda: store)
    monkeypatch.setattr(ingest, "get_embeddings", lambda: SimpleNamespace(aembed_documents=AsyncMock(return_value=[[0.1, 0.2]])))
    monkeypatch.setattr(ingest, "split_text", lambda text: ["退货政策"])
    monkeypatch.setattr(ingest.backend_client, "download_file", AsyncMock(return_value=b"policy"))
    monkeypatch.setattr(ingest.backend_client, "kb_chunks_batch", AsyncMock(return_value={"ids": [101]}))
    callback = AsyncMock()
    monkeypatch.setattr(ingest.backend_client, "kb_result", callback)
    monkeypatch.setattr(vectorstore.backend_client, "kb_current_chunks", AsyncMock(return_value={101: "policy"}))
    await ingest.run_ingest(ingest.IngestTask(doc_id=1, doc_type="POLICY", doc_version=1,
        file_url="/unused", file_format="TXT"))
    result = await store.search("退货")
    assert [h["chunk_id"] for h in result["hits"]] == [101], {
        "result": result, "active_rows": active_rows, "callback": str(callback.await_args)}

@pytest.mark.asyncio
async def test_control_single_kb_call_keeps_correct_citation(monkeypatch):
    pipeline = SimpleNamespace(search=AsyncMock(return_value=kb_result(101, "退货政策")))
    monkeypatch.setattr(retrieval, "get_retrieval_pipeline", lambda: pipeline)
    await tools.kb_search.ainvoke({"query": "退货"})
    ctx = tools.get_tool_ctx()
    result = validate_citations("七天退货[S1]", allowed=ctx["rag_allowed_citations"], answerable=True)
    assert result.valid and result.citations[0]["chunk_id"] == 101


@pytest.mark.asyncio
async def test_control_second_product_reference_is_correct(monkeypatch):
    tools.set_tool_ctx({"user_id": 1, "latest_user_text": "第二款的参数", "active_entities": {
        "last_products": [{"id": 101 + i, "name": str(i)} for i in range(5)]}})
    detail = AsyncMock(return_value={})
    monkeypatch.setattr(tools.backend_client, "product_detail", detail)
    await tools.product_detail.ainvoke({})
    assert detail.await_args.kwargs["product_id"] == 102


@pytest.mark.asyncio
async def test_control_metadata_in_recall_window_is_found(monkeypatch):
    hit = {"chunk_id": 21, "doc_id": 21, "product_id": 7, "docType": "FAQ",
        "content": "七天退货", "source": "policy", "score": 100.0}
    recall = AsyncMock(return_value={"hits": [hit]})
    result = await retrieval.RetrievalPipeline(vector_search=recall, bm25_search=recall, reranker=None).search("退货", product_id=7)
    assert result.answerable and result.hits[0].chunk_id == 21


@pytest.mark.asyncio
async def test_control_explicit_dual_failure_reports_unavailable():
    pipeline = retrieval.RetrievalPipeline(
        vector_search=AsyncMock(side_effect=RuntimeError("vector offline")),
        bm25_search=AsyncMock(side_effect=RuntimeError("backend offline")), reranker=None)
    result = await pipeline.search("退货")
    assert result.reason == "retrieval_unavailable" and result.degraded

@pytest.mark.asyncio
async def test_kb_citations_are_unique_even_when_queries_complete_concurrently(monkeypatch):
    import asyncio
    async def search(query, **kwargs):
        await asyncio.sleep(0)
        return kb_result(101 if query == "退货" else 202, query)
    monkeypatch.setattr(retrieval, "get_retrieval_pipeline", lambda: SimpleNamespace(search=search))
    first, second = await asyncio.gather(tools.kb_search.ainvoke({"query": "退货"}), tools.kb_search.ainvoke({"query": "保修"}))
    assert first["citations"][0]["id"] != second["citations"][0]["id"]
    assert f'id="{second["citations"][0]["id"]}"' in second["context"]
    assert {v["chunk_id"] for v in tools.get_tool_ctx()["rag_allowed_citations"].values()} == {101, 202}


@pytest.mark.asyncio
async def test_failed_followup_kb_query_does_not_erase_previous_evidence(monkeypatch):
    pipeline = SimpleNamespace(search=AsyncMock(side_effect=[kb_result(101, "退货"),
        retrieval.RetrievalResult(False, "retrieval_unavailable", (), "", (), True, ("vector_unavailable", "bm25_unavailable"))]))
    monkeypatch.setattr(retrieval, "get_retrieval_pipeline", lambda: pipeline)
    await tools.kb_search.ainvoke({"query": "退货"})
    result = await tools.kb_search.ainvoke({"query": "保修"})
    assert not result["answerable"]
    assert tools.get_tool_ctx()["rag_answerable"] is True
    assert tools.get_tool_ctx()["rag_allowed_citations"]["S1"]["chunk_id"] == 101
    assert tools.get_tool_ctx()["degraded"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("text,expected", [("第五款的参数", 105), ("第4个", 104), ("最后一款", 105)])
async def test_product_reference_positions(monkeypatch, text, expected):
    tools.set_tool_ctx({"user_id": 1, "latest_user_text": text, "active_entities": {
        "last_products": [{"id": 101+i} for i in range(5)]}})
    monkeypatch.setattr(tools.backend_client, "product_detail", AsyncMock(side_effect=lambda **kwargs: {"productId": kwargs["product_id"]}))
    result = await tools.product_detail.ainvoke({})
    assert result["productId"] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["第六款", "这两款的参数", "介绍这款"])
async def test_ambiguous_or_out_of_range_product_must_not_default_to_first(monkeypatch, text):
    tools.set_tool_ctx({"latest_user_text": text, "active_entities": {"last_products": [{"id": 1}, {"id": 2}]}})
    detail = AsyncMock(return_value={"productId": 1})
    monkeypatch.setattr(tools.backend_client, "product_detail", detail)
    assert "error" in await tools.product_detail.ainvoke({})
    detail.assert_not_awaited()


@pytest.mark.asyncio
async def test_order_reference_uses_the_same_fourth_product_resolution(monkeypatch):
    tools.set_tool_ctx({"user_id": 1, "conversation_id": 1, "latest_user_text": "买第四款", "active_entities": {
        "last_products": [{"id": 101+i} for i in range(5)]}})
    monkeypatch.setattr(tools.backend_client, "order_prepare", AsyncMock(side_effect=lambda **kwargs: {"productId": kwargs["product_id"]}))
    result = await tools.order_create.ainvoke({})
    assert result["productId"] == 104


@pytest.mark.asyncio
async def test_empty_catalog_clears_vectors_without_embedding(monkeypatch):
    corpus = product_index.ProductCorpus()
    corpus.products = {1: {"productId": 1}}
    index = SimpleNamespace(delete_old_versions=AsyncMock())
    embed = AsyncMock()
    monkeypatch.setattr(ingest, "get_product_corpus", lambda: corpus)
    monkeypatch.setattr(ingest, "get_product_index", lambda: index)
    monkeypatch.setattr(ingest, "get_embeddings", embed)
    monkeypatch.setattr(ingest.backend_client, "products_all", AsyncMock(return_value=[]))
    result = await ingest.sync_products()
    assert result["indexed"] == 0 and corpus.products == {}
    index.delete_old_versions.assert_awaited_once()
    embed.assert_not_called()


def test_empty_rebuild_replaces_old_corpus():
    corpus = product_index.ProductCorpus()
    corpus.products = {1: {"productId": 1}}
    corpus.rebuild([], [])
    assert corpus.products == {} and corpus.bm25_recall("手机", None, None, None, 5) == []


@pytest.mark.asyncio
async def test_hybrid_tool_rechecks_live_price_stock_and_availability(monkeypatch):
    cached = [{"productId": i, "price": 100, "category": "PHONE"} for i in range(1, 5)]
    monkeypatch.setattr(tools, "_observe_product", AsyncMock(return_value={"products": cached, "total": 4}))
    live = {1: {"productId": 1, "price": 300, "stock": 2, "category": "PHONE", "name": "fresh"},
        2: {"error": "商品不存在或已下架"}, 3: {"productId": 3, "price": 100, "stock": 0, "category": "PHONE"},
        4: {"productId": 4, "price": 100, "stock": 1, "category": "PHONE", "name": "valid"}}
    monkeypatch.setattr(tools.backend_client, "product_detail", AsyncMock(side_effect=lambda **kwargs: live[kwargs["product_id"]]))
    result = await tools.product_search.ainvoke({"category": "PHONE", "max_price": 200})
    assert [p["productId"] for p in result["products"]] == [4]
    assert result["products"][0]["name"] == "valid"
    assert tools.get_tool_ctx()["active_entities"]["last_products"][0]["id"] == 4


@pytest.mark.asyncio
async def test_live_lookup_outage_does_not_expose_cached_price_as_fresh(monkeypatch):
    monkeypatch.setattr(tools, "_observe_product", AsyncMock(return_value={"products": [{"productId": 1, "price": 100}]}))
    monkeypatch.setattr(tools.backend_client, "product_detail", AsyncMock(return_value={"error": "后端服务暂时不可用"}))
    result = await tools.product_search.ainvoke({})
    assert result.get("error") and result.get("products") == []
    assert tools.get_tool_ctx()["degraded"] is True


def test_product_text_includes_available_factual_fields():
    text = ingest.build_product_text({"productId": 1, "origin": "法国", "shipFrom": "上海", "material": "纯棉", "productionDate": "2026-10-01"})
    for fact in ("法国", "上海", "纯棉", "2026-10-01"):
        assert fact in text

@pytest.mark.asyncio
async def test_product_status_still_reports_keyword_corpus_when_milvus_is_down(monkeypatch):
    from app.api import products as api
    corpus = product_index.ProductCorpus()
    corpus.products = {1: {"productId": 1}}
    monkeypatch.setattr(api, "get_product_corpus", lambda: corpus, raising=False)
    def offline():
        raise RuntimeError("milvus offline")
    monkeypatch.setattr(api, "get_product_index", offline)
    result = await api.sync_status()
    assert result["product_count"] == 1
    assert result["collection_exists"] is False


@pytest.mark.asyncio
async def test_empty_catalog_publishes_empty_even_when_vector_cleanup_fails(monkeypatch):
    corpus = product_index.ProductCorpus()
    corpus.products = {1: {"productId": 1}}
    monkeypatch.setattr(ingest, "get_product_corpus", lambda: corpus)
    monkeypatch.setattr(ingest.backend_client, "products_all", AsyncMock(return_value=[]))
    monkeypatch.setattr(ingest, "get_product_index", lambda: SimpleNamespace(delete_old_versions=AsyncMock(side_effect=RuntimeError("milvus down"))))
    result = await ingest.sync_products()
    assert corpus.products == {} and result["degraded"] is True

@pytest.mark.asyncio
@pytest.mark.parametrize("text,products,expected", [
    ("这款支持第三方充电器吗？", [{"id": 101}], 101),
    ("这款是第二代吗？", [{"id": 101}], 101),
    ("第二款支持第三方充电器吗？", [{"id": 101}, {"id": 102}], 102),
])
async def test_non_product_ordinals_do_not_override_product_reference(monkeypatch, text, products, expected):
    tools.set_tool_ctx({"latest_user_text": text, "active_entities": {"last_products": products}})
    monkeypatch.setattr(tools.backend_client, "product_detail", AsyncMock(side_effect=lambda **kwargs: {"productId": kwargs["product_id"]}))
    result = await tools.product_detail.ainvoke({})
    assert result.get("productId") == expected


@pytest.mark.asyncio
async def test_agent_prompt_does_not_instruct_guessing_first_or_hide_remembered_positions(monkeypatch):
    from langchain_core.messages import AIMessage, HumanMessage
    from app.agent import nodes
    class Model:
        def bind_tools(self, *args, **kwargs):
            return self
        async def ainvoke(self, messages):
            self.prompt = messages[0].content
            return AIMessage(content="请明确商品")
    model = Model()
    monkeypatch.setattr(nodes, "get_chat_llm", lambda: model)
    await nodes.agent_node({"intent": "PRODUCT_CONSULT", "messages": [HumanMessage(content="介绍这款")],
        "active_entities": {"last_category": "PHONE", "last_products": [
            {"id": i, "name": f"商品{i}"} for i in range(1, 11)]}})
    assert "或序号 1" not in model.prompt
    assert "商品10" in model.prompt
