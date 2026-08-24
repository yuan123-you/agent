"""文档摄取链路：下载 → 解析 → 分割 → 后端分配 chunk id → 向量化 → Milvus 入库 → 回写状态
商品语料向量化：sync_products() 复用同一 embedding/Milvus 链路（版本化重建、停用自动清除）"""
import asyncio
import io
import json
import logging
import time

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from pypdf import PdfReader
from pydantic import BaseModel

from app.clients.backend_client import backend_client
from app.config import settings
from app.clients.llm import get_embeddings
from app.rag.product_index import get_product_corpus, get_product_index
from app.rag.vectorstore import get_vectorstore

logger = logging.getLogger("ai-service.ingest")


class IngestTask(BaseModel):
    doc_id: int
    product_id: int | None = None
    doc_type: str
    doc_version: int
    file_url: str
    file_format: str


def parse_file(file_format: str, data: bytes) -> str:
    if file_format.upper() == "PDF":
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return data.decode("utf-8", errors="ignore")


# 标题分块器：先提取标题元数据，随后把完整标题路径重复到每个子块。
_header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "H1"), ("##", "H2"), ("###", "H3")],
    strip_headers=True,
)
_CHINESE_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", "、", " ", ""]


def _heading_prefix(metadata: dict) -> str:
    lines = []
    for level, key in enumerate(("H1", "H2", "H3"), start=1):
        value = metadata.get(key)
        if value:
            lines.append(f"{'#' * level} {value}")
    return "\n".join(lines)


def _body_splitter(chunk_size: int, chunk_overlap: int) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=_CHINESE_SEPARATORS,
        keep_separator="end",
    )


def split_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[str]:
    """标题感知的中文分块；每个 Markdown 子块重复完整标题路径。"""
    if not text or not text.strip():
        return []
    size = chunk_size if chunk_size is not None else settings.rag_chunk_size
    overlap = chunk_overlap if chunk_overlap is not None else settings.rag_chunk_overlap
    if size < 200 or overlap < 0 or overlap >= size:
        raise ValueError("chunk_size must be >= 200 and 0 <= chunk_overlap < chunk_size")

    chunks: list[str] = []
    sections = _header_splitter.split_text(text)
    for doc in sections:
        body = doc.page_content.strip()
        prefix = _heading_prefix(doc.metadata)
        if not body and not prefix:
            continue
        combined = f"{prefix}\n\n{body}".strip()
        if len(combined) <= size:
            chunks.append(combined)
            continue

        # 为重复标题预留空间，使最终块始终不超过配置上限。
        prefix_cost = len(prefix) + 2 if prefix else 0
        body_size = size - prefix_cost
        if body_size < 80:
            raise ValueError("chunk_size is too small for the Markdown heading path")
        body_overlap = min(overlap, body_size - 1)
        for part in _body_splitter(body_size, body_overlap).split_text(body):
            chunks.append(f"{prefix}\n\n{part}".strip() if prefix else part)

    return [chunk for chunk in chunks if chunk.strip()]

async def run_ingest(task: IngestTask) -> None:
    """后台摄取任务：分块落库失败置 FAILED；
    向量 Embedding/Milvus 不可用时降级为关键词检索模式（仍置 ACTIVE，保证知识库可用）"""
    try:
        data = await backend_client.download_file(task.file_url)
        text = parse_file(task.file_format, data)
        if not text.strip():
            raise ValueError("文档内容为空或无法解析")

        texts = split_text(text)
        chunks = [{"chunkIndex": i, "content": t, "tokenCount": len(t) // 2} for i, t in enumerate(texts)]

        # ① 网关预分配 chunk id（MySQL kb_chunk 落库）——关键词检索的数据基础
        resp = await backend_client.kb_chunks_batch(task.doc_id, chunks)
        if "ids" not in resp:
            raise RuntimeError(str(resp.get("error", "chunks batch failed")))
        ids = resp["ids"]

        # ② 向量化并写入 Milvus（Embedding 不可用时跳过：检索自动降级关键词模式）
        try:
            store = get_vectorstore()
            existing = await store.existing_ids(ids)
            pending = [(chunk_id, text) for chunk_id, text in zip(ids, texts) if chunk_id not in existing]
            if pending:
                embeddings = get_embeddings()
                vectors = await embeddings.aembed_documents([text for _, text in pending])
                rows = [{
                    "id": chunk_id,
                    "embedding": vectors[i],
                    "doc_id": task.doc_id,
                    "product_id": task.product_id if task.product_id else -1,
                    "doc_type": task.doc_type,
                    "doc_version": task.doc_version,
                    "content": text[:4000],
                } for i, (chunk_id, text) in enumerate(pending)]
                await store.insert(rows)
            logger.info(
                "ingest vectors doc=%s embedded=%s skipped_existing=%s",
                task.doc_id, len(pending), len(existing),
            )
            # 重建索引场景：清理旧版本向量
            if task.doc_version > 1:
                await get_vectorstore().delete_by_doc(task.doc_id, exclude_version=task.doc_version)
        except Exception as e:
            logger.warning(
                "embedding/milvus unavailable (doc=%s), KB falls back to keyword mode: %s",
                task.doc_id, e)

        await backend_client.kb_result(task.doc_id, "ACTIVE", len(chunks))
        logger.info("ingest done doc=%s chunks=%s", task.doc_id, len(chunks))
    except Exception as e:
        logger.error("ingest failed doc=%s: %s", task.doc_id, e)
        await backend_client.kb_result(task.doc_id, "FAILED", 0, str(e)[:200])


# ========== 商品语料向量化 ==========

CATEGORY_LABELS = {
    "PHONE": "手机 智能手机 数码",
    "LAPTOP": "笔记本电脑 电脑 笔记本 办公本",
    "APPLIANCE": "家用电器 家电 电器",
    "CLOTHING": "服饰 衣服 服装 内衣",
    "BEAUTY": "美妆 护肤 个护 化妆品",
    "FOOD": "食品 零食 生鲜 饮料",
    "MATERNAL": "母婴 玩具 儿童",
    "SPORTS": "运动 户外 健身",
    "BOOK": "图书 书籍 文娱",
    "HOME": "家居 家具 家纺",
    "JEWELRY": "珠宝 饰品 首饰",
    "BAGS": "箱包 包包 背包",
    "SHOES": "鞋 鞋靴 运动鞋",
    "PET": "宠物 宠物用品",
    "HEALTH": "医疗 保健 健康",
    "CAR": "汽车 车品 车载",
}


def _specs_text(specs) -> str:
    """参数 JSON → 可检索文本（如 {"屏幕":"6.7英寸"} → "屏幕 6.7英寸"）"""
    if not specs:
        return ""
    try:
        data = json.loads(specs) if isinstance(specs, str) else specs
        if isinstance(data, dict):
            return " ".join(f"{k} {v}" for k, v in data.items())
        return str(data)
    except Exception:
        return str(specs)


def build_product_text(p: dict) -> str:
    """单商品语料：名称 + 品牌 + 类目同义词 + 卖点 + 参数 + 介绍（语义混合检索的正文）"""
    cat = p.get("category") or ""
    label = CATEGORY_LABELS.get(cat, cat)
    return " ".join(x for x in [
        p.get("name") or "",
        f"品牌 {p.get('brand')}" if p.get("brand") else "",
        label,
        f"卖点 {p.get('sellingPoints')}" if p.get("sellingPoints") else "",
        _specs_text(p.get("specs")),
        f"介绍 {p.get('description')}" if p.get("description") else "",
    ] if x)


_product_sync_lock = asyncio.Lock()


async def sync_products() -> dict:
    """Refresh keyword corpus immediately, then best-effort vector index."""
    async with _product_sync_lock:
        try:
            products = await backend_client.products_all()
            if not products:
                logger.warning("product sync: backend returned no on-sale products")
                return {"indexed": 0, "vectorIndexed": 0, "reason": "no products"}
            texts = [build_product_text(product) for product in products]
            get_product_corpus().rebuild(products, texts)
        except Exception as exc:
            logger.warning("product source sync failed; preserving previous corpus: %s", exc)
            return {"indexed": 0, "vectorIndexed": 0, "error": str(exc)[:200]}

        try:
            vectors = await get_embeddings().aembed_documents(texts)
            version = int(time.time() * 1000)
            rows = [{
                "product_id": int(product["productId"]), "embedding": vector,
                "name": (product.get("name") or "")[:200],
                "category": (product.get("category") or "")[:32],
                "brand": (product.get("brand") or "")[:64],
                "price": float(product.get("price") or 0),
                "stock": int(product.get("stock") or 0),
                "sales": int(product.get("sales") or 0),
                "build_version": version,
            } for product, vector in zip(products, vectors)]
            index = get_product_index()
            await index.upsert(rows)
            await index.delete_old_versions(version)
            logger.info("product sync done: indexed=%s version=%s", len(rows), version)
            return {"indexed": len(products), "vectorIndexed": len(rows), "version": version}
        except Exception as exc:
            logger.warning("product vector sync failed; keyword corpus remains available: %s", exc)
            return {"indexed": len(products), "vectorIndexed": 0,
                    "degraded": True, "error": str(exc)[:200]}
