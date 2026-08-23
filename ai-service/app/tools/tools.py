"""工具定义：身份上下文由服务端 ContextVar 注入（不信任模型生成的身份）"""
import contextvars
import logging

from langchain_core.tools import tool

from app import rag as _rag
from app.clients.backend_client import backend_client
from app.observability.telemetry import observe_retrieval
from app.rag.product_index import hybrid_product_search
from app.tools.web_search import web_search

logger = logging.getLogger("ai-service.tools")

# 工具执行上下文（网关请求注入 userId/conversation_id）
_tool_ctx: contextvars.ContextVar[dict] = contextvars.ContextVar("tool_ctx", default={})


def set_tool_ctx(ctx: dict) -> None:
    _tool_ctx.set(ctx)


def get_tool_ctx() -> dict:
    return _tool_ctx.get()


async def _kb_search(query: str, doc_type: str = "ALL", product_id: int | None = None, top_k: int = 4) -> dict:
    """经惰性 getter 解析向量库（运行期取到缓存实例），便于测试 monkeypatch 替换。"""
    return await _rag.vectorstore.get_vectorstore().search(
        query, doc_type=doc_type, product_id=product_id, top_k=top_k)


# RAG 检索节点打点（可观测：命中数与来源）
_observe_kb = observe_retrieval("rag::kb_search")(_kb_search)
_observe_product = observe_retrieval("rag::product_search")(hybrid_product_search)


@tool
async def product_search(keyword: str | None = None, category: str | None = None,
                         min_price: float | None = None, max_price: float | None = None,
                         top_k: int = 5) -> dict:
    """检索在售商品。当用户表达购物需求（品类/预算/偏好关键词）时调用。
    采用语义混合检索：语义召回（拍照/夜拍/vlog/游戏本 等特性词效果更好）+ 类目/价格过滤，返回商品列表（含价格、库存、卖点与站内跳转链接 link 字段）。
    keyword 填商品特性词或短语，如"拍照""夜拍""游戏本""轻薄"。"""
    ctx = get_tool_ctx()
    try:
        result = await _observe_product(
            keyword=keyword, category=category, min_price=min_price, max_price=max_price, top_k=top_k)
        if result is not None:
            return result
    except Exception as e:
        logger.warning("hybrid product search failed, fallback to SQL: %s", e)
    return await backend_client.product_search(
        user_id=int(ctx.get("user_id", 0)), keyword=keyword, category=category,
        min_price=min_price, max_price=max_price, top_k=top_k,
    )


@tool
async def product_detail(product_id: int) -> dict:
    """查询指定商品的详细信息（参数、介绍、价格、库存）。用于商品比较或深度介绍。
    product_id 必须来自 product_search 结果。"""
    ctx = get_tool_ctx()
    return await backend_client.product_detail(
        user_id=int(ctx.get("user_id", 0)), product_id=product_id,
    )


@tool
async def order_query(status: str = "ALL") -> dict:
    """查询当前买家的订单列表与物流状态。用户询问"我的订单""到哪了""发货没"时调用。"""
    ctx = get_tool_ctx()
    return await backend_client.order_query(
        user_id=int(ctx.get("user_id", 0)), status=status,
    )


@tool
async def order_create(product_id: int, quantity: int = 1,
                       receiver_name: str = "", receiver_phone: str = "",
                       receiver_address: str = "") -> dict:
    """生成待用户确认的下单动作，不创建订单。
    默认复用买家保存的默认收货地址；只有买家明确提供新信息时才传入覆盖值。
    返回确认卡片所需的商品、数量、金额、收货信息和 actionId。"""
    ctx = get_tool_ctx()
    result = await backend_client.order_prepare(
        user_id=int(ctx.get("user_id", 0)),
        conversation_id=int(ctx.get("conversation_id", 0)),
        product_id=product_id, quantity=quantity,
        receiver_name=receiver_name, receiver_phone=receiver_phone,
        receiver_address=receiver_address,
    )
    if "error" not in result:
        ctx.setdefault("actions", []).append({"type": "ORDER_CREATE", **result})
        result = {**result, "status": "PENDING_CONFIRMATION"}
    return result


@tool
async def kb_search(query: str, doc_type: str = "ALL", product_id: int | None = None, top_k: int = 4) -> dict:
    """检索知识库（商品介绍/售后政策/常见问题）。回答退换货政策、保修规则、商品介绍细节时调用。
    返回检索到的内容片段与来源，回答时必须基于这些内容并注明来源。
    未命中时 hits 为空且 empty=true，此时应明确告知用户知识库暂无相关资料，禁止编造。"""
    # 双路检索 RRF 混排：向量（Milvus）+ 关键词（后端 MySQL），按 chunk_id 融合。
    # 任一腿命中即返回；向量腿单独命中也要保留，避免"关键词零命中否定向量召回"的误判。
    # 关键词链路异常（kw_err）时退化为纯向量。
    vector_hits, kw_hits = [], []
    kw_err: Exception | None = None
    try:
        vector_result = await _observe_kb(query, doc_type=doc_type, product_id=product_id, top_k=top_k)
        vector_hits = (vector_result or {}).get("hits") or []
    except Exception as e:
        logger.warning("vector search failed: %s", e)
    try:
        kw_result = await backend_client.kb_keyword_search(
            query, doc_type=doc_type, product_id=product_id, top_k=top_k)
        kw_hits = (kw_result or {}).get("hits") or []
    except Exception as e:
        kw_err = e
        logger.warning("keyword search failed: %s", e)

    # 双路 RRF 融合：任一路命中即返回（含仅向量命中），避免关键词零命中误判为空
    if vector_hits or kw_hits:
        merged = _rrf_content([vector_hits, kw_hits], top_k)
        return {"hits": merged, "total": len(merged)}
    return {"hits": [], "total": 0, "empty": True}


def _rrf_content(ranked: list[list[dict]], top_k: int, k: int = 60) -> list[dict]:
    """RRF 混排（k=60 常用）：score = Σ 1/(k + rank)，按 chunk_id 融合。
    向量与关键词命中同一 chunk 时排名叠加；chunk_id 缺失（如单测/旧数据）回退按正文识别。取 top_k。"""
    scores: dict[str, float] = {}
    by_chunk: dict[str, dict] = {}
    for lst in ranked:
        for rank, hit in enumerate(lst):
            key = hit.get("chunk_id") or hit.get("content", "")
            if not key:
                continue
            key = str(key)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            by_chunk.setdefault(key, hit)
    ordered = sorted(scores, key=scores.get, reverse=True)
    return [by_chunk[key] for key in ordered[:top_k]]


@tool
async def escalate_to_human(reason: str = "") -> dict:
    """转接人工客服。用户明确要求转人工/投诉，或你无法解决用户问题时调用。"""
    ctx = get_tool_ctx()
    ctx["escalated"] = True
    return await backend_client.escalate(
        user_id=int(ctx.get("user_id", 0)),
        conversation_id=int(ctx.get("conversation_id", 0)),
        reason=reason[:200],
    )


ALL_TOOLS = [product_search, product_detail, order_query, order_create, kb_search, escalate_to_human, web_search]



