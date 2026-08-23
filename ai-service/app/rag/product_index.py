"""商品向量索引：Milvus product_index collection（主键=商品ID，区别于政策/FAQ 知识库）
+ 内存 BM25 商品语料缓存 + 混合检索（向量召回 + BM25 关键词 → RRF 混排 → 轻量重排）。

检索链路：
  1. 向量召回（Milvus，带类目/价格标量过滤）
  2. BM25 关键词召回（同步 job 构建的内存语料，同样过滤）
  3. 两者 RRF（Reciprocal Rank Fusion）混排
  4. 轻量重排：相关度优先，同相关度按价格升序（"便宜点"）、再按销量降序（质量信号）
语料未就绪（同步 job 未完成/Milvus 不可用）时返回 None，由调用方降级为后端 SQL 检索。
"""
import asyncio
import logging
import re
from collections import defaultdict

from pymilvus import DataType, MilvusClient

from app.clients.llm import get_embeddings
from app.config import settings
from app.rag.vectorstore import MilvusUnavailableError
from app.rag.reranker import get_reranker

logger = logging.getLogger("ai-service.product-index")

try:
    from rank_bm25 import BM25Okapi
except ImportError:  # rank_bm25 未安装时禁用 BM25 路（向量召回仍可用）
    BM25Okapi = None

# 中文切词：CJK 双字滑窗（2 字词直接命中，多字短语拆 bigram）+ ASCII 词
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
_ASCII_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._\-]+")


def tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    tokens: list[str] = []
    for seg in _CJK_RE.findall(text):
        if len(seg) >= 2:
            tokens.extend(seg[i:i + 2] for i in range(len(seg) - 1))
    tokens.extend(_ASCII_RE.findall(text))
    return tokens


def _match(p: dict, category: str | None, min_price: float | None, max_price: float | None) -> bool:
    if category and p.get("category") != category:
        return False
    price = float(p.get("price") or 0)
    if min_price is not None and price < min_price:
        return False
    if max_price is not None and price > max_price:
        return False
    return True


def _to_vo(p: dict) -> dict:
    return {
        "productId": int(p["productId"]),
        "name": p.get("name", ""),
        "brand": p.get("brand", ""),
        "category": p.get("category", ""),
        "price": p.get("price"),
        "stock": p.get("stock", 0),
        "sellingPoints": p.get("sellingPoints", ""),
        "sales": p.get("sales", 0),
        "link": f"mall://product/{int(p['productId'])}",
    }


class ProductCorpus:
    """内存商品语料：由同步 job 重建；检索时提供 BM25 关键词召回与纯结构化兜底"""

    def __init__(self):
        self.products: dict[int, dict] = {}  # product_id -> 完整商品 VO
        self._bm25 = None
        self._ids: list[int] = []

    def ready(self) -> bool:
        return self._bm25 is not None

    def rebuild(self, products: list[dict], texts: list[str]) -> None:
        if not products:
            return
        self.products = {int(p["productId"]): dict(p) for p in products}
        self._ids = list(self.products.keys())
        self._bm25 = BM25Okapi([tokenize(t) for t in texts]) if BM25Okapi is not None else None
        logger.info("product corpus rebuilt: %s products, bm25=%s",
                    len(self.products), self._bm25 is not None)

    def clear(self) -> None:
        self.products = {}
        self._ids = []
        self._bm25 = None

    def structured(self, category, min_price, max_price, top_k: int) -> list[dict]:
        """无关键词时按价格升序（销量降序）返回过滤后的商品"""
        cands = [p for p in self.products.values() if _match(p, category, min_price, max_price)]
        cands.sort(key=lambda p: (float(p.get("price") or 0), -(int(p.get("sales") or 0))))
        return cands[:top_k]

    def bm25_recall(self, query: str, category, min_price, max_price, k: int) -> list[tuple[int, float]]:
        if self._bm25 is None:
            return []
        terms = tokenize(query)
        if not terms:
            return []
        scores = self._bm25.get_scores(terms)
        cands = []
        for i, pid in enumerate(self._ids):
            if scores[i] > 0 and _match(self.products[pid], category, min_price, max_price):
                cands.append((pid, float(scores[i])))
        cands.sort(key=lambda x: -x[1])
        return cands[:k]


class ProductIndex:
    """Milvus product_index collection：商品向量（主键=商品ID，含类目/价格/销量标量字段）"""

    def __init__(self):
        try:
            self.client = MilvusClient(uri=settings.milvus_uri)
            self.client.list_collections()  # 首次触达：构造与连接校验，失败抛可控异常
        except Exception as e:
            raise MilvusUnavailableError(
                f"Milvus unavailable at {settings.milvus_uri}: {e}") from e
        self.embeddings = get_embeddings()
        self.corpus = ProductCorpus()
        self._sync_lock = asyncio.Lock()

    # ---------- collection ----------
    def ensure_collection(self) -> None:
        name = settings.milvus_product_collection
        if self.client.has_collection(name):
            return
        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("product_id", DataType.INT64, is_primary=True)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=settings.embedding_dim)
        schema.add_field("name", DataType.VARCHAR, max_length=256)
        schema.add_field("category", DataType.VARCHAR, max_length=32)
        schema.add_field("brand", DataType.VARCHAR, max_length=64)
        schema.add_field("price", DataType.FLOAT)
        schema.add_field("stock", DataType.INT64)
        schema.add_field("sales", DataType.INT64)
        schema.add_field("build_version", DataType.INT64)
        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="embedding", index_type="HNSW", metric_type="IP",
            params={"M": 16, "efConstruction": 200},
        )
        self.client.create_collection(name, schema=schema, index_params=index_params)
        logger.info("created milvus product collection %s (dim=%s)", name, settings.embedding_dim)

    async def upsert(self, rows: list[dict]) -> None:
        await asyncio.to_thread(
            self.client.upsert, collection_name=settings.milvus_product_collection, data=rows,
        )

    async def delete_old_versions(self, version: int) -> None:
        """重建/停用：清理旧版本向量（新版本已含当前在售全量，旧版本即停用商品）"""
        await asyncio.to_thread(
            self.client.delete,
            collection_name=settings.milvus_product_collection,
            filter=f"build_version < {version}",
        )

    # ---------- 向量召回 ----------
    def _filter_expr(self, category, min_price, max_price) -> str:
        parts: list[str] = []
        if category:
            parts.append(f'category == "{category}"')
        if min_price is not None:
            parts.append(f"price >= {min_price}")
        if max_price is not None:
            parts.append(f"price <= {max_price}")
        return " and ".join(parts) if parts else "product_id >= 0"

    async def vector_recall(self, query: str, category, min_price, max_price, k: int) -> list[tuple[int, float]]:
        emb = await self.embeddings.aembed_query(query)
        res = await asyncio.to_thread(
            self.client.search,
            collection_name=settings.milvus_product_collection,
            data=[emb],
            limit=k,
            filter=self._filter_expr(category, min_price, max_price),
            output_fields=["product_id"],
            search_params={"ef": 128},
        )
        hits: list[tuple[int, float]] = []
        for h in (res[0] if res else []):
            entity = h.get("entity", {}) or {}
            pid = int(entity.get("product_id") or h.get("id", 0))
            hits.append((pid, float(h.get("distance", 0))))
        return hits


_index: "ProductIndex | None" = None


def get_product_index() -> ProductIndex:
    """惰性 + 缓存单例：首次调用才创建客户端（含连接校验）；
    连接失败抛 MilvusUnavailableError（可控异常，由调用方决定降级/标记 degraded）。"""
    global _index
    if _index is None:
        _index = ProductIndex()
    return _index


def _reset_product_index() -> None:
    """测试/重建用：清空缓存，下次 getter 调用时重新创建。"""
    global _index
    _index = None


def _rrf(ranked_lists: list[list[tuple[int, float]]], k: int = 60) -> dict[int, float]:
    """Reciprocal Rank Fusion：score = Σ 1/(k + rank)，k=60 常用"""
    scores: dict[int, float] = defaultdict(float)
    for lst in ranked_lists:
        for rank, (pid, _) in enumerate(lst):
            scores[pid] += 1.0 / (k + rank + 1)
    return scores


async def hybrid_product_search(keyword: str | None, category: str | None,
                                min_price: float | None, max_price: float | None,
                                top_k: int = 5) -> dict | None:
    """混合检索：向量召回 + BM25 关键词 → RRF 混排 → 轻量重排。
    语料未就绪返回 None，由调用方降级后端 SQL 检索。"""
    pidx = get_product_index()
    if not pidx.corpus.ready() and not pidx.corpus.products:
        return None
    kw = (keyword or "").strip()
    if not kw:
        # 纯结构化检索（无关键词）：按价格升序，保持原有"便宜优先"语义
        top = pidx.corpus.structured(category, min_price, max_price, top_k)
        return {"products": [_to_vo(p) for p in top], "total": len(top)}

    vec = await pidx.vector_recall(kw, category, min_price, max_price, top_k * 4)
    bm = pidx.corpus.bm25_recall(kw, category, min_price, max_price, top_k * 4)
    rrf = _rrf([vec, bm])
    if not rrf:
        return {"products": [], "total": 0}

    def _sort_key(item):
        pid, score = item
        p = pidx.corpus.products.get(pid) or {}
        return (-score, float(p.get("price") or 0), -(int(p.get("sales") or 0)))

    merged = sorted(rrf.items(), key=_sort_key)
    candidate_ids = [
        pid for pid, _ in merged[:max(top_k, settings.reranker_candidates)]
        if pid in pidx.corpus.products
    ]
    candidates = []
    for pid in candidate_ids:
        product = pidx.corpus.products[pid]
        content = " ".join(str(product.get(key) or "") for key in (
            "name", "brand", "category", "sellingPoints", "specs", "description"
        ))
        candidates.append({"product_id": pid, "content": content})
    ranked = await get_reranker().rerank(kw, candidates, top_n=top_k)
    top = [
        pidx.corpus.products[item["product_id"]]
        for item in ranked if item.get("product_id") in pidx.corpus.products
    ]
    return {"products": [_to_vo(p) for p in top], "total": len(top)}
