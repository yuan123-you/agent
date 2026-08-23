"""AI Mall AI 推理服务入口：仅后端可访问（X-Internal-Token 校验）"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import chat, health, kb, products
from app.config import settings
from app.rag.ingest import sync_products
from app.rag.product_index import get_product_index
from app.rag.vectorstore import get_vectorstore

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("ai-service")


async def _product_sync_loop() -> None:
    """商品同步后台 job：确保 collection → 立即同步一次 → 按 interval 周期刷新（失败下一轮自动重试）"""
    try:
        await asyncio.to_thread(get_product_index().ensure_collection)
    except Exception as e:
        logger.error("product collection init failed (product RAG will degrade): %s", e)
    while True:
        await sync_products()
        await asyncio.sleep(settings.product_sync_interval_s)


@asynccontextmanager
async def lifespan(app: FastAPI):
    sync_task = None
    # lifespan 显式初始化并缓存向量库实例；Milvus 宕机时抛可控异常 → 记录降级依赖，服务照常启动。
    try:
        await asyncio.to_thread(get_vectorstore().ensure_collection)
        logger.info("Milvus collection ready: %s", settings.milvus_collection)
        health.set_dependency("milvus", True)
    except Exception as e:
        health.set_dependency("milvus", False, str(e)[:200])
        logger.error("Milvus init failed (RAG will degrade): %s", e)
    # 其余依赖（LLM / 后端）仅在健康检查时实时探测，此处不阻塞启动
    if settings.product_sync_enabled:
        sync_task = asyncio.create_task(_product_sync_loop())
        logger.info("product sync job started (interval=%ss)", settings.product_sync_interval_s)
    yield
    if sync_task:
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="AI Mall AI Service", version="1.0.0", lifespan=lifespan)
app.include_router(chat.router, prefix="/v1")
app.include_router(kb.router, prefix="/v1")
app.include_router(products.router, prefix="/v1")
app.include_router(health.router)


@app.middleware("http")
async def internal_token_guard(request: Request, call_next):
    """服务间鉴权：/v1/** 必须携带正确的 X-Internal-Token"""
    if request.url.path.startswith("/v1"):
        token = request.headers.get("X-Internal-Token")
        if token != settings.internal_token:
            return JSONResponse(status_code=401, content={"code": 1003, "message": "invalid internal token"})
    return await call_next(request)
