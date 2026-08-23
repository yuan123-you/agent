"""商品检索接口：手动触发同步 + 查询同步状态"""
import logging

from fastapi import APIRouter

from app.config import settings
from app.rag.ingest import sync_products
from app.rag.product_index import get_product_index

router = APIRouter()
logger = logging.getLogger("ai-service.products-api")


@router.post("/products/sync")
async def trigger_sync() -> dict:
    """手动触发商品向量化同步（幂等：内部互斥，重复调用不会并发重入）"""
    return await sync_products()


@router.get("/products/status")
async def sync_status() -> dict:
    """商品语料状态：Milvus collection 是否就绪、内存语料商品数、BM25 是否可用"""
    exists = False
    pidx = None
    try:
        pidx = get_product_index()
        exists = pidx.client.has_collection(settings.milvus_product_collection)
    except Exception as e:
        logger.warning("product collection check failed: %s", e)
    return {
        "collection_exists": exists,
        "corpus_ready": pidx.corpus.ready() if pidx else False,
        "product_count": len(pidx.corpus.products) if pidx else 0,
    }
