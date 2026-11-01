"""Offline retrieval deadlines, SDK controls and bounded provider fanout."""
import asyncio
import importlib
import threading
from time import monotonic
from types import SimpleNamespace
from unittest.mock import AsyncMock

import grpc
import httpx
import pytest
from pymilvus.client.grpc_handler import GrpcHandler
from pymilvus.decorators import retry_on_rpc_failure
from pymilvus.exceptions import ErrorCode, MilvusException
from pymilvus.grpc_gen import common_pb2, milvus_pb2

from app import resilience
from app.rag import product_index, vectorstore

web = importlib.import_module("app.tools.web_search")
pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def no_live_transports(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("offline retrieval test attempted a live transport")

    monkeypatch.setattr("socket.getaddrinfo", forbidden)
    monkeypatch.setattr("socket.create_connection", forbidden)
    monkeypatch.setattr(grpc, "insecure_channel", forbidden)
    monkeypatch.setattr(grpc, "secure_channel", forbidden)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)


class Unavailable(grpc.RpcError):
    def code(self):
        return grpc.StatusCode.UNAVAILABLE

    def details(self):
        return "offline injected failure"


class Rpc:
    def __init__(self, *, response=None, error=None):
        self.calls, self.response, self.error = [], response, error

    def __call__(self, *args, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response

    def future(self, *args, **kwargs):
        return SimpleNamespace(result=lambda: self(*args, **kwargs))


def sdk_client(handler, monkeypatch):
    # Neither the SDK constructor nor a channel is needed for boundary tests.
    monkeypatch.setattr(vectorstore.MilvusClient, "_get_connection", lambda self: handler)
    return vectorstore._SingleShotMilvusClient.__new__(vectorstore._SingleShotMilvusClient)


@pytest.mark.parametrize("failure", [Unavailable(), MilvusException(code=ErrorCode.RATE_LIMIT, message="rate limited")])
async def test_installed_sdk_decorator_cannot_retry_numeric_timeout(monkeypatch, failure):
    rpc = Rpc(error=failure)

    class Handler:
        @retry_on_rpc_failure()
        def search(self, *, timeout=None, **kwargs):
            return self._stub.Search(timeout=timeout)

    handler = Handler()
    handler._stub = SimpleNamespace(Search=rpc)
    client = sdk_client(handler, monkeypatch)
    monkeypatch.setattr("pymilvus.decorators.time.sleep", lambda _: pytest.fail("hidden SDK retry sleep"))
    with resilience.budget_scope(0.2):
        with pytest.raises(type(failure)):
            client._get_connection().search(timeout=0.1, retry_times=0, retry_on_rate_limit=False)
    assert len(rpc.calls) == 1
    assert 0 < rpc.calls[0]["timeout"] <= 0.1
    assert handler._stub.Search is rpc  # No global/shared connection mutation.
    assert hasattr(handler.search, "__wrapped__")


async def test_actual_installed_grpc_delete_handler_is_single_shot(monkeypatch):
    rpc = Rpc(error=Unavailable())
    handler = GrpcHandler.__new__(GrpcHandler)
    handler._address = "offline:19530"
    handler._stub = SimpleNamespace(Delete=rpc)
    client = sdk_client(handler, monkeypatch)
    monkeypatch.setattr("pymilvus.decorators.time.sleep", lambda _: pytest.fail("SDK replay"))
    with resilience.budget_scope(0.2):
        with pytest.raises(grpc.RpcError):
            client._get_connection().delete("kb_chunks", "doc_id == 7", timeout=0.1,
                                            retry_times=0, retry_on_rate_limit=False)
    assert len(rpc.calls) == 1
    assert rpc.calls[0]["timeout"] <= 0.1


async def test_sdk_internal_schema_refresh_cannot_replay_an_insert(monkeypatch):
    rpc = Rpc(response={})

    class Handler:
        @retry_on_rpc_failure()
        def insert_rows(self, *, timeout=None, **kwargs):
            # Pinned 2.4 has an internal schema-mismatch replay, not a decorator.
            self._stub.Insert(timeout=timeout)
            return self._stub.Insert(timeout=timeout)

    handler = Handler()
    handler._stub = SimpleNamespace(Insert=rpc)
    client = sdk_client(handler, monkeypatch)
    with pytest.raises(vectorstore.MilvusUnavailableError, match="replay"):
        client._get_connection().insert_rows(timeout=0.1, retry_times=0)
    assert len(rpc.calls) == 1


async def test_rpc_deadline_reclipped_after_metadata_before_mutation(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(resilience, "monotonic", lambda: clock[0])
    describe, insert = Rpc(response={}), Rpc(response={})

    class Handler:
        def insert_rows(self, *, timeout=None, **kwargs):
            self._stub.DescribeCollection(timeout=timeout)
            clock[0] += 0.07
            return self._stub.Insert(timeout=timeout)

    handler = Handler()
    handler._stub = SimpleNamespace(DescribeCollection=describe, Insert=insert)
    client = sdk_client(handler, monkeypatch)
    with resilience.budget_scope(0.1):
        client._get_connection().insert_rows(timeout=10.0, retry_times=0)
    assert describe.calls[0]["timeout"] == pytest.approx(0.1)
    assert insert.calls[0]["timeout"] == pytest.approx(0.03)


@pytest.mark.parametrize("kind,operation", [("vector", "insert"), ("vector", "delete_by_doc"),
                                            ("product", "upsert"), ("product", "delete_old_versions")])
async def test_ambiguous_mutations_single_shot_with_rpc_deadlines(kind, operation):
    calls = []

    def fail(**kwargs):
        calls.append(kwargs)
        raise TimeoutError("acknowledgement lost after commit")

    cls = vectorstore.VectorStore if kind == "vector" else product_index.ProductIndex
    store = cls.__new__(cls)
    method = {"delete_by_doc": "delete", "delete_old_versions": "delete"}.get(operation, operation)
    store.client = SimpleNamespace(**{method: fail})
    arg = [{"id": 1}] if operation in {"insert", "upsert"} else 7
    with resilience.budget_scope(0.2) as budget:
        with pytest.raises(TimeoutError):
            await getattr(store, operation)(arg)
    assert len(calls) == 1
    assert 0 < calls[0]["timeout"] <= 0.2
    assert calls[0]["retry_times"] == 0 and calls[0]["retry_on_rate_limit"] is False
    assert budget.retry_tokens_remaining == 6
    assert [e["outcome"] for e in budget.events] == ["attempt", "failure"]


@pytest.mark.parametrize("kind", ["vector", "product"])
async def test_vector_read_parent_timeout_and_preserved_evidence(monkeypatch, kind):
    calls = []

    def search(**kwargs):
        calls.append(kwargs)
        return [[{"id": 11, "distance": 0.9, "entity": {
            "product_id": 7, "doc_id": 3, "content": "trusted evidence", "doc_type": "POLICY"}}]]

    cls = vectorstore.VectorStore if kind == "vector" else product_index.ProductIndex
    store = cls.__new__(cls)
    store.client = SimpleNamespace(search=search)
    store.embeddings = SimpleNamespace(aembed_query=AsyncMock(return_value=[0.1]))
    monkeypatch.setattr(vectorstore.backend_client, "kb_current_chunks", AsyncMock(return_value={11: "Current policy"}))
    with resilience.budget_scope(0.2):
        if kind == "vector":
            result = await store.search("query", doc_type="POLICY", product_id=7, top_k=2)
            assert result["hits"][0]["source"] == "Current policy"
            assert result["hits"][0]["content"] == "trusted evidence"
            assert result["hits"][0]["chunk_id"] == 11
        else:
            assert await store.vector_recall("query", "PHONE", 1, 10, 2) == [(7, 0.9)]
    assert len(calls) == 1
    assert 0 < calls[0]["timeout"] <= 0.2
    assert calls[0]["retry_times"] == 0 and calls[0]["limit"] == 2


async def test_expired_parent_prevents_mutation_and_existence_lookup(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr(resilience, "monotonic", lambda: clock[0])
    calls = []
    store = vectorstore.VectorStore.__new__(vectorstore.VectorStore)
    store.client = SimpleNamespace(insert=lambda **kw: calls.append(kw), has_collection=lambda *a, **kw: calls.append(kw))
    with resilience.budget_scope(0.1):
        clock[0] += 0.2
        with pytest.raises(resilience.DeadlineExceeded):
            await store.insert([{"id": 1}])
        with pytest.raises(resilience.DeadlineExceeded):
            await store.existing_ids([1])
    assert calls == []


async def test_existing_ids_off_loop_with_deadlines_for_each_batch():
    loop_thread, calls = threading.get_ident(), []

    def exists(name, **kwargs):
        assert threading.get_ident() != loop_thread
        calls.append(("has", kwargs))
        return True

    def query(**kwargs):
        assert threading.get_ident() != loop_thread
        calls.append(("query", kwargs))
        return [{"id": 1}]

    store = vectorstore.VectorStore.__new__(vectorstore.VectorStore)
    store.client = SimpleNamespace(has_collection=exists, query=query)
    with resilience.budget_scope(0.2):
        assert await store.existing_ids(list(range(501)), include_legacy=False) == {1}
    assert [method for method, _ in calls] == ["has", "query", "query"]
    assert all(0 < kw["timeout"] <= 0.2 and kw["retry_times"] == 0 for _, kw in calls)


async def test_provider_http_single_shot_with_clipped_timeout():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(503, json={"error": "busy"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with resilience.budget_scope(0.2) as budget:
            with pytest.raises(httpx.HTTPStatusError):
                await web._request(client, "POST", "https://provider.test/search", json={"query": "evidence"})
    assert len(requests) == 1
    assert all(0 < t <= 0.2 for t in requests[0].extensions["timeout"].values())
    assert budget.retry_tokens_remaining == 6
    assert [e["outcome"] for e in budget.events] == ["attempt", "failure"]


async def test_web_fanout_does_not_multiply_failures_or_extend_parent(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    monkeypatch.setattr(web.settings, "web_search_hedge_delay_s", 0.001)
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(503, text="busy")

    original = httpx.AsyncClient
    monkeypatch.setattr(web.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    with resilience.budget_scope(0.2) as budget:
        result = await web.web_search.ainvoke({"query": "evidence"})
    assert result["results"] == [] and result["error"]
    assert sorted(req.url.host for req in requests) == ["cn.bing.com", "www.sogou.com"]
    assert all(0 < value <= 0.2 for req in requests for value in req.extensions["timeout"].values())
    assert budget.retry_tokens_remaining == 6
    assert len([e for e in budget.events if e["outcome"] == "attempt"]) == 2


async def test_web_orchestration_inherits_deadline_and_cancels_body(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    monkeypatch.setattr(web.settings, "web_search_hedge_delay_s", 0.001)
    streams = []

    class Body(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self):
            while True:
                yield b"x"
                await asyncio.sleep(0.002)

        async def aclose(self):
            self.closed = True

    def handle(request):
        stream = Body()
        streams.append(stream)
        return httpx.Response(200, stream=stream)

    original = httpx.AsyncClient
    monkeypatch.setattr(web.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    started = monotonic()
    with resilience.budget_scope(0.03):
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(web._search("evidence", 2), timeout=0.15)
    assert monotonic() - started < 0.12
    assert streams and all(stream.closed for stream in streams)


async def test_expired_web_budget_never_opens_provider(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr(resilience, "monotonic", lambda: clock[0])
    calls = []

    def forbidden(**kw):
        calls.append(kw)
        pytest.fail("provider opened after deadline")

    monkeypatch.setattr(web.httpx, "AsyncClient", forbidden)
    with resilience.budget_scope(0.1):
        clock[0] += 0.2
        result = await web.web_search.ainvoke({"query": "evidence"})
    assert result.get("error") and calls == []

async def test_existing_ids_has_one_local_deadline_across_rpcs_without_parent(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(resilience, "monotonic", lambda: clock[0])
    monkeypatch.setattr(vectorstore, "_MILVUS_TIMEOUT_S", 0.1)
    calls = []

    def exists(name, **kwargs):
        calls.append(("has", kwargs))
        clock[0] += 0.06
        return True

    def query(**kwargs):
        calls.append(("query", kwargs))
        clock[0] += 0.06
        return [{"id": 1}]

    store = vectorstore.VectorStore.__new__(vectorstore.VectorStore)
    store.client = SimpleNamespace(has_collection=exists, query=query)
    with pytest.raises(resilience.DeadlineExceeded):
        await store.existing_ids([1], include_legacy=False)
    assert len(calls) == 2
    assert calls[1][1]["timeout"] == pytest.approx(0.04)


@pytest.mark.parametrize("kind", ["vector", "product"])
async def test_collection_setup_shares_deadline_across_existence_and_create(monkeypatch, kind):
    clock = [100.0]
    monkeypatch.setattr(resilience, "monotonic", lambda: clock[0])
    monkeypatch.setattr(vectorstore, "_MILVUS_TIMEOUT_S", 0.1)
    monkeypatch.setattr(product_index, "_MILVUS_TIMEOUT_S", 0.1)
    calls = []

    def exists(name, **kwargs):
        clock[0] += 0.06
        return False

    cls = vectorstore.VectorStore if kind == "vector" else product_index.ProductIndex
    store = cls.__new__(cls)
    store.client = SimpleNamespace(
        has_collection=exists,
        create_schema=lambda **kw: SimpleNamespace(add_field=lambda *a, **k: None),
        prepare_index_params=lambda: SimpleNamespace(add_index=lambda **kw: None),
        create_collection=lambda name, **kw: calls.append(kw),
    )
    store.ensure_collection()
    assert len(calls) == 1
    assert calls[0]["timeout"] == pytest.approx(0.04)


async def test_milvus_worker_is_not_claimed_killed_when_waiter_deadline_expires():
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    calls = []

    def write(**kwargs):
        calls.append(kwargs)
        started.set()
        try:
            release.wait(1)
            raise TimeoutError("late RPC termination")
        finally:
            finished.set()

    store = vectorstore.VectorStore.__new__(vectorstore.VectorStore)
    store.client = SimpleNamespace(insert=write)
    try:
        with resilience.budget_scope(0.03):
            with pytest.raises(resilience.DeadlineExceeded):
                await store.insert([{"id": 1}])
        assert started.is_set() and not finished.is_set()
        assert len(calls) == 1
        assert 0 < calls[0]["timeout"] <= 0.03
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 1)


async def test_expired_budget_in_thread_queue_prevents_rpc_dispatch(monkeypatch):
    clock, calls = [100.0], []
    monkeypatch.setattr(resilience, "monotonic", lambda: clock[0])

    async def queued(func, *args, **kwargs):
        clock[0] += 0.2
        return func(*args, **kwargs)

    monkeypatch.setattr(vectorstore.asyncio, "to_thread", queued)
    store = vectorstore.VectorStore.__new__(vectorstore.VectorStore)
    store.client = SimpleNamespace(insert=lambda **kw: calls.append(kw))
    with resilience.budget_scope(0.1):
        with pytest.raises(resilience.DeadlineExceeded):
            await store.insert([{"id": 1}])
    assert calls == []

@pytest.mark.parametrize("method,rpc_name,kwargs", [
    ("search", "Search", {"data": [[0.1, 0.2]], "limit": 2}),
    ("query", "Query", {"filter": "id >= 0", "output_fields": ["id"]}),
    ("insert", "Insert", {"data": [{"id": 1}]}),
    ("upsert", "Upsert", {"data": [{"id": 1}]}),
    ("delete", "Delete", {"filter": "doc_id == 7"}),
    ("has_collection", "DescribeCollection", {}),
    ("list_collections", "ShowCollections", {}),
])
async def test_actual_sdk_high_level_to_grpc_boundary_is_single_shot(monkeypatch, method, rpc_name, kwargs):
    rpc = Rpc(error=Unavailable())
    handler = GrpcHandler.__new__(GrpcHandler)
    handler._address = "offline:19530"
    handler._stub = SimpleNamespace(**{rpc_name: rpc})
    handler._prepare_row_insert_request = lambda *a, **kw: object()
    handler._prepare_row_upsert_request = lambda *a, **kw: object()
    client = sdk_client(handler, monkeypatch)
    client._config = SimpleNamespace(db_name="default")
    monkeypatch.setattr("pymilvus.decorators.time.sleep", lambda _: pytest.fail("hidden SDK replay"))
    options = {} if method == "list_collections" else {"collection_name": "kb_chunks"}
    with resilience.budget_scope(0.2) as budget:
        with pytest.raises(grpc.RpcError):
            await vectorstore._milvus_call(client, method, replay_safe=method not in {"insert", "upsert", "delete"},
                                          **options, **kwargs)
    assert len(rpc.calls) == 1
    assert 0 < rpc.calls[0]["timeout"] <= 0.2
    assert budget.retry_tokens_remaining == 6


async def test_expired_standalone_http_budget_never_constructs_client(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(resilience, "monotonic", lambda: clock[0])
    calls = []

    def forbidden(**kwargs):
        calls.append(kwargs)
        pytest.fail("client constructed after deadline")

    monkeypatch.setattr(web.httpx, "AsyncClient", forbidden)
    with resilience.budget_scope(0.1):
        clock[0] += 0.2
        with pytest.raises(resilience.DeadlineExceeded):
            await web._request(None, "GET", "https://provider.test/search")
    assert calls == []


@pytest.mark.parametrize("method,rpc_name,count_key", [
    ("insert", "Insert", "insert_count"),
    ("upsert", "Upsert", "upsert_count"),
    ("delete", "Delete", "delete_count"),
])
async def test_actual_sdk_mutation_success_preserves_result(monkeypatch, method, rpc_name, count_key):
    response = milvus_pb2.MutationResult(status=common_pb2.Status(), insert_cnt=1, upsert_cnt=1, delete_cnt=1)
    rpc = Rpc(response=response)
    handler = GrpcHandler.__new__(GrpcHandler)
    handler._address = "offline:19530"
    handler._stub = SimpleNamespace(**{rpc_name: rpc})
    handler._prepare_row_insert_request = lambda *a, **kw: object()
    handler._prepare_row_upsert_request = lambda *a, **kw: object()
    client = sdk_client(handler, monkeypatch)
    client._config = SimpleNamespace(db_name="default")
    kwargs = {"filter": "doc_id == 7"} if method == "delete" else {"data": [{"id": 1}]}
    with resilience.budget_scope(0.2):
        result = await vectorstore._milvus_call(client, method, replay_safe=False,
                                               collection_name="kb_chunks", **kwargs)
    assert result[count_key] == 1
    assert len(rpc.calls) == 1


@pytest.mark.parametrize("method,rpc_name", [("insert", "Insert"), ("upsert", "Upsert")])
async def test_actual_sdk_schema_mismatch_does_not_replay_mutation(monkeypatch, method, rpc_name):
    response = milvus_pb2.MutationResult(
        status=common_pb2.Status(error_code=common_pb2.SchemaMismatch, reason="schema changed"))
    rpc = Rpc(response=response)
    handler = GrpcHandler.__new__(GrpcHandler)
    handler._address = "offline:19530"
    handler._stub = SimpleNamespace(**{rpc_name: rpc})
    handler._prepare_row_insert_request = lambda *a, **kw: object()
    handler._prepare_row_upsert_request = lambda *a, **kw: object()
    handler.update_schema = lambda *a, **kw: {}
    client = sdk_client(handler, monkeypatch)
    client._config = SimpleNamespace(db_name="default")
    with resilience.budget_scope(0.2) as budget:
        with pytest.raises((MilvusException, vectorstore.MilvusUnavailableError)):
            await vectorstore._milvus_call(client, method, replay_safe=False,
                                           collection_name="kb_chunks", data=[{"id": 1}])
    assert len(rpc.calls) == 1
    assert budget.retry_tokens_remaining == 6


async def test_all_configured_providers_keep_original_four_call_fanout(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "offline-placeholder")
    monkeypatch.setenv("SEARXNG_URL", "https://searxng.test")
    monkeypatch.setattr(web.settings, "web_search_hedge_delay_s", 0.001)
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(429, headers={"Retry-After": "1"}, json={"error": "busy"})

    original = httpx.AsyncClient
    monkeypatch.setattr(web.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    with resilience.budget_scope(0.2) as budget:
        result = await web.web_search.ainvoke({"query": "evidence"})
    assert result["results"] == [] and result["error"]
    assert sorted(req.url.host for req in requests) == [
        "api.tavily.com", "cn.bing.com", "searxng.test", "www.sogou.com"]
    assert budget.retry_tokens_remaining == 6
    assert len([e for e in budget.events if e["outcome"] == "attempt"]) == 4

async def test_actual_sdk_nested_schema_rpc_clips_remaining_mutation_timeout(monkeypatch):
    from pymilvus import DataType
    from pymilvus.grpc_gen import schema_pb2

    clock = [100.0]
    monkeypatch.setattr(resilience, "monotonic", lambda: clock[0])
    schema = schema_pb2.CollectionSchema(name="offline_deadline_insert", fields=[
        schema_pb2.FieldSchema(fieldID=100, name="id", is_primary_key=True, data_type=DataType.INT64),
        schema_pb2.FieldSchema(fieldID=101, name="embedding", data_type=DataType.FLOAT_VECTOR,
                              type_params=[common_pb2.KeyValuePair(key="dim", value="2")]),
    ])
    schema_reply = milvus_pb2.DescribeCollectionResponse(status=common_pb2.Status(), schema=schema, collectionID=1)
    class SchemaRpc(Rpc):
        def __call__(self, *args, **kwargs):
            clock[0] += 0.05
            return super().__call__(*args, **kwargs)

    describe = SchemaRpc(response=schema_reply)
    reads = describe.calls
    insert = Rpc(error=Unavailable())
    handler = GrpcHandler.__new__(GrpcHandler)
    handler._address = "offline-deadline-schema:19530"
    handler.schema_cache = {}
    handler._stub = SimpleNamespace(DescribeCollection=describe, Insert=insert)
    client = sdk_client(handler, monkeypatch)
    client._config = SimpleNamespace(db_name="default")
    monkeypatch.setattr("pymilvus.decorators.time.sleep", lambda _: pytest.fail("nested SDK retry"))
    with resilience.budget_scope(0.2):
        with pytest.raises(grpc.RpcError):
            await vectorstore._milvus_call(client, "insert", replay_safe=False,
                                           collection_name="offline_deadline_insert",
                                           data=[{"id": 1, "embedding": [0.1, 0.2]}])
    assert len(reads) == len(insert.calls) == 1
    assert reads[0]["timeout"] == pytest.approx(0.2)
    assert insert.calls[0]["timeout"] == pytest.approx(0.15)

@pytest.mark.parametrize("kind", ["vector", "product"])
async def test_constructor_requests_dedicated_channel_and_disables_supported_transport_retries(monkeypatch, kind):
    module = vectorstore if kind == "vector" else product_index
    cls = vectorstore.VectorStore if kind == "vector" else product_index.ProductIndex
    options, probes = [], []

    def construct(**kwargs):
        options.append(kwargs)
        return SimpleNamespace(list_collections=lambda **kw: probes.append(kw))

    monkeypatch.setattr(module, "_SingleShotMilvusClient", construct)
    monkeypatch.setattr(module, "get_embeddings", lambda: object())
    with resilience.budget_scope(0.2):
        cls()
    assert len(options) == len(probes) == 1
    assert options[0]["dedicated"] is True
    assert options[0]["grpc_options"] == {"grpc.enable_retries": 0}
    assert 0 < options[0]["timeout"] <= 0.2
    assert 0 < probes[0]["timeout"] <= options[0]["timeout"]
    assert probes[0]["retry_times"] == 0

class OfflineChannel:
    """A gRPC-shaped wire, including pinned Connections.connect's copy barrier."""
    def __init__(self, *, error=None, status=None):
        self.calls = []
        self.closes = 0
        self.error, self.status = error, status

    def __deepcopy__(self, memo):
        raise TypeError("native gRPC channels cannot be deep-copied")

    def subscribe(self, callback, try_to_connect=False):
        callback(grpc.ChannelConnectivity.READY)

    def unsubscribe(self, callback):
        pass

    def close(self):
        self.closes += 1

    def unary_unary(self, method, *args, **kwargs):
        owner = self

        class Call:
            def __call__(self, *args, **kwargs):
                owner.calls.append((method, kwargs))
                if owner.error:
                    raise owner.error
                return milvus_pb2.ConnectResponse(
                    status=owner.status or common_pb2.Status(), identifier=42)

            def with_call(self, *args, **kwargs):
                return self(*args, **kwargs), SimpleNamespace()

        return Call()

    unary_stream = unary_unary
    stream_unary = unary_unary
    stream_stream = unary_unary


@pytest.mark.parametrize("uri,target,tls", [
    ("http://reader:offline@milvus.invalid:19530/tenant", "milvus.invalid:19530", False),
    ("https://reader:offline@milvus.invalid/tenant", "milvus.invalid:443", True),
])
async def test_actual_sdk_constructor_injects_copyable_no_retry_channel_preserving_auth(monkeypatch, uri, target, tls):
    import base64
    import copy
    created = []
    wire = OfflineChannel()
    credentials = object()

    def insecure(address, **kwargs):
        created.append((False, address, None, kwargs))
        return wire

    def secure(address, creds, **kwargs):
        created.append((True, address, creds, kwargs))
        return wire

    monkeypatch.setattr(grpc, "insecure_channel", insecure)
    monkeypatch.setattr(grpc, "secure_channel", secure)
    monkeypatch.setattr(grpc, "ssl_channel_credentials", lambda **kw: credentials)
    with resilience.budget_scope(0.2):
        client = vectorstore._SingleShotMilvusClient(uri=uri, timeout=0.2, dedicated=True)
        try:
            channel = vectorstore.MilvusClient._get_connection(client)._channel
            assert copy.deepcopy({"channel": channel})["channel"] is channel
        finally:
            client.close()
    assert len(created) == 1
    assert created[0][:2] == (tls, target)
    assert created[0][2] is (credentials if tls else None)
    assert dict(created[0][3]["options"])["grpc.enable_retries"] == 0
    assert len(wire.calls) == 1 and wire.calls[0][0].endswith("/Connect")
    metadata = dict(wire.calls[0][1]["metadata"])
    authorization = metadata["authorization"]
    if isinstance(authorization, bytes):
        authorization = authorization.decode("ascii")
    assert authorization == base64.b64encode(b"reader:offline").decode()
    # Pinned 2.4 forwards database metadata at the channel layer.
    import pymilvus
    if pymilvus.__version__.startswith("2.4."):
        assert metadata["dbname"] == "tenant"
    assert 0 < wire.calls[0][1]["timeout"] <= 0.2
    assert wire.closes == 1


@pytest.mark.parametrize("failure", [Unavailable(), "rate_limit"])
async def test_actual_sdk_bootstrap_connect_never_retries_or_omits_rpc_deadline(monkeypatch, failure):
    wire = OfflineChannel(
        error=failure if isinstance(failure, Exception) else None,
        status=common_pb2.Status(error_code=common_pb2.RateLimit, reason="busy") if failure == "rate_limit" else None,
    )
    monkeypatch.setattr(grpc, "insecure_channel", lambda *a, **kw: wire)
    monkeypatch.setattr("pymilvus.decorators.time.sleep", lambda _: pytest.fail("hidden bootstrap SDK retry"))
    with resilience.budget_scope(0.2):
        # Pinned error_handler wraps the permanent RuntimeError in MilvusException.
        with pytest.raises((vectorstore.MilvusUnavailableError, MilvusException)):
            vectorstore._SingleShotMilvusClient(uri="http://milvus.invalid:19530", timeout=0.2, dedicated=True)
    assert len(wire.calls) == 1
    assert 0 < wire.calls[0][1]["timeout"] <= 0.2
    assert wire.closes == 1


@pytest.mark.parametrize("mtls", [False, True])
async def test_injected_secure_channel_preserves_sdk_certificate_and_authority_settings(monkeypatch, tmp_path, mtls):
    paths = {}
    for name in ["server_pem_path", "ca_pem_path", "client_key_path", "client_pem_path"]:
        path = tmp_path / name
        path.write_bytes(name.encode())
        paths[name] = str(path)
    kwargs = {name: value for name, value in paths.items() if name != "server_pem_path"} if mtls else {
        "server_pem_path": paths["server_pem_path"]}
    creds, created = [], []
    wire = OfflineChannel()

    def credentials(**kwargs):
        creds.append(kwargs)
        return "offline-tls-credentials"

    def secure(address, credentials, **kwargs):
        created.append((address, credentials, kwargs))
        return wire

    monkeypatch.setattr(grpc, "ssl_channel_credentials", credentials)
    monkeypatch.setattr(grpc, "secure_channel", secure)
    client = vectorstore._SingleShotMilvusClient(uri="https://milvus.invalid:19530", timeout=0.2,
                                                dedicated=True, server_name="milvus.internal", **kwargs)
    client.close()
    assert creds == [{
        "root_certificates": b"ca_pem_path" if mtls else b"server_pem_path",
        "private_key": b"client_key_path" if mtls else None,
        "certificate_chain": b"client_pem_path" if mtls else None,
    }]
    options = dict(created[0][2]["options"])
    assert options["grpc.ssl_target_name_override"] == "milvus.internal"
    assert options["grpc.enable_retries"] == 0
    assert created[0][:2] == ("milvus.invalid:19530", "offline-tls-credentials")


async def test_sdk_public_grpc_options_override_constraint_is_source_verified(monkeypatch):
    import pymilvus
    options = []
    wire = OfflineChannel()

    def create(*args, **kwargs):
        options.append(dict(kwargs["options"]))
        return wire

    monkeypatch.setattr(grpc, "insecure_channel", create)
    handler = GrpcHandler(address="milvus.invalid:19530", grpc_options={"grpc.enable_retries": 0})
    handler.close()
    expected = 1 if pymilvus.__version__.startswith("2.4.") else 0
    assert options[0]["grpc.enable_retries"] == expected


async def test_constructor_bootstrap_clips_deadline_after_channel_setup(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(resilience, "monotonic", lambda: clock[0])

    class SetupDelay(OfflineChannel):
        delayed = False

        def unary_unary(self, method, *args, **kwargs):
            if method.endswith("/Connect") and not self.delayed:
                self.delayed = True
                clock[0] += 0.15
            return super().unary_unary(method, *args, **kwargs)

    wire = SetupDelay()
    monkeypatch.setattr(grpc, "insecure_channel", lambda *a, **kw: wire)
    with resilience.budget_scope(0.2):
        client = vectorstore._SingleShotMilvusClient(uri="http://milvus.invalid:19530", timeout=0.2, dedicated=True)
        client.close()
    assert len(wire.calls) == 1
    assert wire.calls[0][1]["timeout"] == pytest.approx(0.05)


async def test_no_retry_channel_cannot_be_reenabled_by_caller_options(monkeypatch):
    created = []
    wire = OfflineChannel()

    def create(*args, **kwargs):
        created.append(kwargs)
        return wire

    monkeypatch.setattr(grpc, "insecure_channel", create)
    client = vectorstore._SingleShotMilvusClient(uri="http://milvus.invalid:19530", timeout=0.2,
                                                dedicated=True, grpc_options={"grpc.enable_retries": 1})
    client.close()
    assert len(created) == 1
    assert dict(created[0]["options"])["grpc.enable_retries"] == 0

async def test_expired_constructor_budget_never_creates_a_channel(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(resilience, "monotonic", lambda: clock[0])
    with resilience.budget_scope(0.1):
        clock[0] += 0.2
        with pytest.raises(resilience.DeadlineExceeded):
            vectorstore._SingleShotMilvusClient(uri="http://milvus.invalid:19530", timeout=0.2)

@pytest.mark.parametrize("uri", [
    "http://[::1]:19530",
    "https://reader:offline@[2001:db8::1]:19530/tenant",
])
async def test_ipv6_uri_is_explicitly_rejected_before_channel_creation(uri):
    # Pinned Connections.connect also formats hostname:port without brackets.
    # Do not silently construct a malformed target or broaden URI support here.
    with pytest.raises(vectorstore.MilvusUnavailableError, match="IPv6"):
        vectorstore._SingleShotMilvusClient(uri=uri, timeout=0.2, dedicated=True)
