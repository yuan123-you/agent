"""Milvus 向量库封装：kb_chunks collection（主键=kb_chunk.id，标量过滤检索）
惰性初始化：实例仅在被 getter 调用或应用 lifespan 显式初始化时才创建，避免 import 阶段因 Milvus 不可用而失败。"""
import asyncio
import logging

from pymilvus import DataType, MilvusClient

from app.clients.backend_client import backend_client
from app.clients.llm import get_embeddings
from app.config import settings

logger = logging.getLogger("ai-service.vectorstore")


class MilvusUnavailableError(RuntimeError):
    """Milvus 连接/初始化失败：可控异常，供健康检查与降级逻辑统一识别。"""


class VectorStore:
    def __init__(self):
        try:
            self.client = MilvusClient(uri=settings.milvus_uri)
            self.client.list_collections()  # 首次触达：构造与连接校验，失败抛可控异常
        except Exception as e:
            raise MilvusUnavailableError(
                f"Milvus unavailable at {settings.milvus_uri}: {e}") from e
        self.embeddings = get_embeddings()

    def ensure_collection(self) -> None:
        """启动时确保 collection 存在（含 HNSW 索引）"""
        name = settings.milvus_collection
        if self.client.has_collection(name):
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
        self.client.create_collection(name, schema=schema, index_params=index_params)
        logger.info("created milvus collection %s (dim=%s)", name, settings.embedding_dim)

    async def search(self, query: str, doc_type: str = "ALL",
                     product_id: int | None = None, top_k: int = 4) -> dict:
        """Recall ACTIVE vector candidates; request metadata filters run in the pipeline."""
        emb = await self.embeddings.aembed_query(query)
        filter_expr = "doc_id >= 0"
        res = await asyncio.to_thread(
            self.client.search,
            collection_name=settings.milvus_collection,
            data=[emb],
            limit=top_k,
            filter=filter_expr,
            output_fields=["content", "doc_id", "product_id", "doc_type"],
            search_params={"ef": 128},
        )
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
        # 来源标注：内部编号 → 文档标题（如《退换货条款》），后端批量查询
        if hits:
            try:
                titles = await backend_client.kb_titles(list(doc_ids))
            except Exception as e:
                logger.warning("kb titles lookup failed: %s", e)
                titles = {}
            for hit in hits:
                hit["source"] = titles.get(hit.get("doc_id"), f"知识库文档#{hit.get('doc_id')}")
        return {"hits": hits, "total": len(hits)}

    async def existing_ids(self, ids: list[int], include_legacy: bool = True) -> set[int]:
        """Return IDs already vectorized in this or configured legacy collections."""
        if not ids:
            return set()
        names = [settings.milvus_collection]
        if include_legacy:
            names.extend(settings.milvus_legacy_collection_names)
        found: set[int] = set()
        for name in names:
            if not self.client.has_collection(name):
                continue
            for start in range(0, len(ids), 500):
                batch = ids[start:start + 500]
                rows = await asyncio.to_thread(
                    self.client.query,
                    collection_name=name,
                    filter=f"id in [{','.join(str(value) for value in batch)}]",
                    output_fields=["id"],
                    limit=len(batch),
                )
                found.update(int(row["id"]) for row in rows)
        return found
    async def insert(self, rows: list[dict]) -> None:
        await asyncio.to_thread(
            self.client.insert, collection_name=settings.milvus_collection, data=rows,
        )

    async def delete_by_doc(self, doc_id: int, exclude_version: int | None = None) -> dict:
        """删除文档向量（可排除指定版本，用于重建索引时保留新版本）"""
        expr = f"doc_id == {doc_id}"
        if exclude_version:
            expr += f" and doc_version != {exclude_version}"
        return await asyncio.to_thread(
            self.client.delete, collection_name=settings.milvus_collection, filter=expr,
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

