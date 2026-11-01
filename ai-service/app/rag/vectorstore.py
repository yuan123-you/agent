"""Milvus 向量库封装：kb_chunks collection（主键=kb_chunk.id，标量过滤检索）
惰性初始化：实例仅在被 getter 调用或应用 lifespan 显式初始化时才创建，避免 import 阶段因 Milvus 不可用而失败。"""
import asyncio
import json
import inspect
import logging
from pathlib import Path
from urllib.parse import urlparse

import grpc

from pymilvus import DataType, MilvusClient
from pymilvus.client.utils import check_status
from pymilvus.exceptions import MilvusException

from app.clients.backend_client import backend_client
from app.clients.llm import get_embeddings
from app.config import settings
from app.observability.execution_trace import trace_span
from app.resilience import budget_scope, remaining_timeout, run

logger = logging.getLogger("ai-service.vectorstore")


class MilvusUnavailableError(RuntimeError):
    """Milvus 连接/初始化失败：可控异常，供健康检查与降级逻辑统一识别。"""


# No new settings: a finite fallback also bounds standalone ingest/health calls.
_MILVUS_TIMEOUT_S = 10.0


class _ConnectRpc:
    """Only synchronous SDK bootstrap Connect: bounded and never SDK-retryable."""
    def __init__(self, rpc):
        self._rpc = rpc

    def _call(self, call, args, kwargs, *, with_call=False):
        timeout = kwargs.get("timeout")
        kwargs["timeout"] = remaining_timeout(
            min(timeout, _MILVUS_TIMEOUT_S) if timeout is not None else _MILVUS_TIMEOUT_S
        )
        try:
            result = call(*args, **kwargs)
            check_status((result[0] if with_call else result).status)
            return result
        except (grpc.RpcError, MilvusException) as error:
            # 2.4 bootstrap has its own retry decorator, before _get_connection.
            raise MilvusUnavailableError("Milvus bootstrap Connect failed (single-shot)") from error

    def __call__(self, *args, **kwargs):
        return self._call(self._rpc, args, kwargs)

    def with_call(self, *args, **kwargs):
        # SDK authorization/database interceptors use this public gRPC interface.
        return self._call(self._rpc.with_call, args, kwargs, with_call=True)


class _OwnedChannel:
    """gRPC channel facade; SDK kwargs copies retain one owned channel, not locks.

    Only public channel methods are delegated. SDK auth/database interceptors are
    still applied normally, including bootstrap. No SDK/global factory patching.
    """
    def __init__(self, channel):
        self._channel, self._closed = channel, False

    def __deepcopy__(self, memo):
        return self

    def __getattr__(self, name):
        return getattr(self._channel, name)

    def unary_unary(self, method, *args, **kwargs):
        rpc = self._channel.unary_unary(method, *args, **kwargs)
        return _ConnectRpc(rpc) if method.endswith("/Connect") else rpc

    def close(self):
        if not self._closed:
            self._closed = True
            self._channel.close()


def _no_retry_channel(uri, **kwargs):
    """Match pinned SDK address/TLS settings, but inject retries=0 at creation.

    2.4.15 ignores grpc_options and hard-codes retries=1 when it builds a channel.
    Its supported channel kwarg bypasses that branch, but Connections.connect
    deep-copies kwargs. _OwnedChannel makes that path safe without copying a
    native channel. Never fall back to an SDK-created retries-on channel.
    """
    parsed = urlparse(uri)
    if uri.startswith("unix:"):
        address = uri
    elif parsed.scheme in {"http", "https", "tcp", "grpc"} and parsed.hostname:
        if ":" in parsed.hostname:
            raise MilvusUnavailableError("IPv6 Milvus URIs are unsupported by the pinned connection parser")
        port = parsed.port or (443 if parsed.scheme == "https" else 19530)
        address = f"{parsed.hostname}:{port}"
    else:
        raise MilvusUnavailableError("No-retry Milvus requires a server URI or unix socket")
    options = {
        "grpc.max_send_message_length": -1, "grpc.max_receive_message_length": -1,
        "grpc.keepalive_time_ms": 55000, **kwargs.get("grpc_options", {}),
        "grpc.enable_retries": 0,
    }
    secure = parsed.scheme == "https" or kwargs.get("secure", False)
    if not secure:
        return _OwnedChannel(grpc.insecure_channel(address, options=list(options.items())))
    if kwargs.get("server_name"):
        options["grpc.ssl_target_name_override"] = kwargs["server_name"]
    root_cert = private_key = cert_chain = None
    if kwargs.get("server_pem_path"):
        root_cert = Path(kwargs["server_pem_path"]).read_bytes()
    elif all(kwargs.get(name) for name in ("ca_pem_path", "client_key_path", "client_pem_path")):
        root_cert = Path(kwargs["ca_pem_path"]).read_bytes()
        private_key = Path(kwargs["client_key_path"]).read_bytes()
        cert_chain = Path(kwargs["client_pem_path"]).read_bytes()
    credentials = grpc.ssl_channel_credentials(
        root_certificates=root_cert, private_key=private_key, certificate_chain=cert_chain,
    )
    return _OwnedChannel(grpc.secure_channel(address, credentials, options=list(options.items())))


class _DeadlineRpc:
    def __init__(self, rpc, name, mutations):
        self._rpc, self._name, self._mutations = rpc, name, mutations

    def _call(self, call, *args, **kwargs):
        # Reclip at dispatch: thread queueing and metadata RPCs consume time too.
        timeout = kwargs.get("timeout")
        kwargs["timeout"] = remaining_timeout(
            min(float(timeout), _MILVUS_TIMEOUT_S) if timeout is not None else _MILVUS_TIMEOUT_S
        )
        if self._name in {"Insert", "Upsert", "Delete"}:
            if self._name in self._mutations:
                raise MilvusUnavailableError("Milvus SDK mutation replay refused: " + self._name)
            self._mutations.add(self._name)
        return call(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        return self._call(self._rpc, *args, **kwargs)

    def future(self, *args, **kwargs):
        return self._call(self._rpc.future, *args, **kwargs)


class _DeadlineStub:
    def __init__(self, stub):
        self._stub, self._mutations = stub, set()

    def __getattr__(self, name):
        return _DeadlineRpc(getattr(self._stub, name), name, self._mutations)


class _SingleShotConnection:
    """Client-local SDK adapter; never patch shared handlers or decorators.

    Audited against pinned pymilvus 2.4.15 and installed 2.6.17. In 2.6 the
    numeric timeout overrides retry_times; 2.4 insert drops that kwarg and can
    replay internally after SchemaMismatch. Public kwargs alone are insufficient.
    Bind undecorated SDK methods to this proxy so nested metadata calls also
    bypass SDK retry/schema-refresh decorators. Keep SDK request building and
    result validation. The stub additionally refuses internal mutation replay.
    This uses private SDK interfaces: re-audit on SDK upgrades. The injected
    owned channel disables gRPC retries (grpc.enable_retries=0), and bootstrap
    Connect is single-shot with a clipped RPC deadline. The SDK still owns
    auth/database interceptors and wire data; no lower-transport retry gap remains
    in the audited channel setup.
    """
    def __init__(self, connection):
        object.__setattr__(self, "_connection", connection)
        object.__setattr__(self, "_deadline_stub", _DeadlineStub(connection._stub))

    def __getattr__(self, name):
        if name == "_stub":
            return self._deadline_stub
        value = getattr(self._connection, name)
        if inspect.ismethod(value):
            raw = inspect.unwrap(value.__func__)

            def single_shot(*args, **kwargs):
                # Some pinned SDK methods have no **kwargs after unwrapping.
                kwargs.pop("retry_times", None)
                kwargs.pop("retry_on_rate_limit", None)
                return raw(self, *args, **kwargs)

            return single_shot
        return value

    def __setattr__(self, name, value):
        setattr(self._connection, name, value)


class _SingleShotMilvusClient(MilvusClient):
    def __init__(self, uri="http://localhost:19530", **kwargs):
        if "channel" in kwargs:
            raise ValueError("Milvus no-retry client owns its channel")
        timeout = kwargs.pop("timeout", None)
        limit = min(timeout, _MILVUS_TIMEOUT_S) if timeout is not None else _MILVUS_TIMEOUT_S
        with budget_scope(limit):
            remaining_timeout(limit)
            channel = _no_retry_channel(uri, **kwargs)
            try:
                super().__init__(uri=uri, channel=channel, timeout=remaining_timeout(limit), **kwargs)
            except BaseException:
                channel.close()
                raise

    def _get_connection(self):
        return _SingleShotConnection(super()._get_connection())


def _milvus_sync(client, method, *args, timeout_s=_MILVUS_TIMEOUT_S, **kwargs):
    return getattr(client, method)(
        *args, timeout=remaining_timeout(timeout_s), retry_times=0,
        retry_on_rate_limit=False, **kwargs,
    )


async def _milvus_call(client, method, *args, replay_safe, **kwargs):
    async def call(timeout):
        # Cancelling to_thread does NOT stop its worker; the SDK RPC timeout does.
        return await asyncio.to_thread(_milvus_sync, client, method, *args,
                                       timeout_s=timeout, **kwargs)

    # Single-shot owner for reads AND writes: no replay of ambiguous mutations,
    # and no overlap with a synchronous RPC whose caller has stopped waiting.
    return await run("milvus." + method, call, replay_safe=replay_safe,
                     max_attempts=1, attempt_timeout_s=_MILVUS_TIMEOUT_S)


class VectorStore:
    def __init__(self):
        try:
            with budget_scope(_MILVUS_TIMEOUT_S):
                self.client = _SingleShotMilvusClient(
                    uri=settings.milvus_uri, timeout=remaining_timeout(_MILVUS_TIMEOUT_S),
                    grpc_options={"grpc.enable_retries": 0}, dedicated=True,
                )
                _milvus_sync(self.client, "list_collections")
        except Exception as e:
            raise MilvusUnavailableError(
                f"Milvus unavailable at {settings.milvus_uri}: {e}") from e
        self.embeddings = get_embeddings()

    def ensure_collection(self) -> None:
        """启动时确保 collection 存在（含 HNSW 索引）"""
        with budget_scope(_MILVUS_TIMEOUT_S):
            name = settings.milvus_collection
            if _milvus_sync(self.client, "has_collection", name):
                return
            schema = self.client.create_schema(auto_id=False, enable_dynamic_field=False)
            schema.add_field("id", DataType.INT64, is_primary=True)
            schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=settings.embedding_dim)
            schema.add_field("doc_id", DataType.INT64)
            schema.add_field("product_id", DataType.INT64)   # -1 表示平台通用文档
            schema.add_field("doc_type", DataType.VARCHAR, max_length=16)
            schema.add_field("doc_version", DataType.INT64)
            schema.add_field("content", DataType.VARCHAR, max_length=4096)
            index_params = self.client.prepare_index_params()
            index_params.add_index(
                field_name="embedding", index_type="HNSW", metric_type="IP",
                params={"M": 16, "efConstruction": 200},
            )
            _milvus_sync(self.client, "create_collection", name, schema=schema, index_params=index_params)
            logger.info("created milvus collection %s (dim=%s)", name, settings.embedding_dim)

    async def search(self, query: str, doc_type: str = "ALL",
                     product_id: int | None = None, top_k: int = 4) -> dict:
        """Recall within request scope before LIMIT; backend validates current versions."""
        with trace_span("rag.embedding", kind="embedding", model=settings.embedding_model, input={"query":query}) as span:
            emb = await self.embeddings.aembed_query(query)
            span.complete({"dimensions":len(emb)})
        filters = ["doc_id >= 0"]
        if doc_type and doc_type != "ALL":
            filters.append(f"doc_type == {json.dumps(doc_type, ensure_ascii=False)}")
        if product_id is not None:
            filters.append(f"(product_id == {int(product_id)} or product_id == -1)")
        filter_expr = " and ".join(filters)
        with trace_span("rag.milvus", kind="retrieval", input={"collection":settings.milvus_collection, "filter":filter_expr, "topK":top_k}) as span:
            res = await _milvus_call(
                self.client, "search", replay_safe=True,
                collection_name=settings.milvus_collection,
                data=[emb],
                limit=top_k,
                filter=filter_expr,
                output_fields=["content", "doc_id", "product_id", "doc_type"],
                search_params={"ef": 128},
            )
            span.complete(res)
        # 不设绝对分数阈值：IP 距离在不同 embedding 模型间不可迁移，相关性判定交给
        # kb_search 的双路 RRF 混排（关键词无命中即判无答案）。此处返回全部候选供融合。
        hits = []
        doc_ids: set[int] = set()
        for h in (res[0] if res else []):
            entity = h.get("entity", {}) or {}
            doc_id = int(entity.get("doc_id", 0))
            doc_ids.add(doc_id)
            hits.append({
                "content": entity.get("content", ""),
                "chunk_id": int(h.get("id", 0)),  # Milvus 主键 = kb_chunk.id，作双路 RRF 融合身份
                "doc_id": doc_id,
                "product_id": entity.get("product_id"),
                "docType": entity.get("doc_type", ""),
                "score": round(float(h.get("distance", 0)), 4),
            })
        # 后端是版本真相源：过滤停用/旧版本向量并补充可信文档标题。
        if hits:
            with trace_span("rag.current_version", kind="retrieval", input={"chunkIds":[hit["chunk_id"] for hit in hits]}) as span:
                current = await backend_client.kb_current_chunks([hit["chunk_id"] for hit in hits])
                span.complete({"currentChunks":current})
            hits = [hit for hit in hits if hit["chunk_id"] in current]
            for hit in hits:
                hit["source"] = current[hit["chunk_id"]]
        return {"hits": hits, "total": len(hits)}

    async def existing_ids(self, ids: list[int], include_legacy: bool = True) -> set[int]:
        """Return IDs already vectorized in this or configured legacy collections."""
        with budget_scope(_MILVUS_TIMEOUT_S):
            if not ids:
                return set()
            names = [settings.milvus_collection]
            if include_legacy:
                names.extend(settings.milvus_legacy_collection_names)
            found: set[int] = set()
            for name in names:
                if not await _milvus_call(self.client, "has_collection", name, replay_safe=True):
                    continue
                for start in range(0, len(ids), 500):
                    batch = ids[start:start + 500]
                    rows = await _milvus_call(
                        self.client, "query", replay_safe=True,
                        collection_name=name,
                        filter=f"id in [{','.join(str(value) for value in batch)}]",
                        output_fields=["id"],
                        limit=len(batch),
                    )
                    found.update(int(row["id"]) for row in rows)
            return found

    async def insert(self, rows: list[dict]) -> None:
        await _milvus_call(
            self.client, "insert", replay_safe=False, collection_name=settings.milvus_collection, data=rows,
        )

    async def delete_by_doc(self, doc_id: int, exclude_version: int | None = None) -> dict:
        """仅清理严格早于 exclude_version 的版本，保留当前及未来版本。
        参数名兼容现有调用者；未指定或为 0 时仍删除该文档的所有版本。
        """
        expr = f"doc_id == {doc_id}"
        if exclude_version:
            expr += f" and doc_version < {exclude_version}"
        return await _milvus_call(
            self.client, "delete", replay_safe=False, collection_name=settings.milvus_collection, filter=expr,
        )


_store: "VectorStore | None" = None


def get_vectorstore() -> VectorStore:
    """惰性 + 缓存单例：首次调用才创建客户端；
    连接失败抛 MilvusUnavailableError（可控异常，由调用方决定降级/标记 degraded）。"""
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


def _reset_vectorstore() -> None:
    """测试/重建用：清空缓存，下次 getter 调用时重新创建。"""
    global _store
    _store = None
