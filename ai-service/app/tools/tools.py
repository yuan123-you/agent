"""工具定义：身份上下文由服务端 ContextVar 注入（不信任模型生成的身份），支持会话级实体记忆"""
import contextvars
import logging
import re
from dataclasses import asdict

from langchain_core.tools import tool

from app.rag import retrieval
from app.clients.backend_client import backend_client
from app.observability.telemetry import observe_retrieval
from app.rag.product_index import hybrid_product_search
from app.tools.web_search import web_search

logger = logging.getLogger("ai-service.tools")

# 工具执行上下文（网关请求注入 userId/conversation_id/active_entities）
_tool_ctx: contextvars.ContextVar[dict] = contextvars.ContextVar("tool_ctx", default={})


def set_tool_ctx(ctx: dict) -> None:
    _tool_ctx.set(ctx)


def get_tool_ctx() -> dict:
    return _tool_ctx.get()


CATEGORY_MAP = {
    "phone": "PHONE",
    "手机": "PHONE",
    "手机数码": "PHONE",
    "computer": "COMPUTER",
    "laptop": "COMPUTER",
    "电脑": "COMPUTER",
    "电脑办公": "COMPUTER",
    "笔记本": "COMPUTER",
    "笔记本电脑": "COMPUTER",
    "台式机": "COMPUTER",
    "pc": "COMPUTER",
    "digital": "DIGITAL",
    "数码": "DIGITAL",
    "数码配件": "DIGITAL",
    "配件": "DIGITAL",
    "充电器": "DIGITAL",
    "耳机": "DIGITAL",
    "clothing": "CLOTHING",
    "服饰": "CLOTHING",
    "服饰内衣": "CLOTHING",
    "服装": "CLOTHING",
    "衣服": "CLOTHING",
    "内衣": "CLOTHING",
    "裤子": "CLOTHING",
    "shoes": "SHOES",
    "鞋": "SHOES",
    "鞋靴": "SHOES",
    "鞋子": "SHOES",
    "凉鞋": "SHOES",
    "bags": "BAGS",
    "包": "BAGS",
    "箱包": "BAGS",
    "背包": "BAGS",
    "双肩包": "BAGS",
    "sports": "SPORTS",
    "运动": "SPORTS",
    "运动户外": "SPORTS",
    "jewelry": "JEWELRY",
    "珠宝": "JEWELRY",
    "珠宝饰品": "JEWELRY",
    "饰品": "JEWELRY",
    "首饰": "JEWELRY",
    "appliance": "APPLIANCE",
    "家电": "APPLIANCE",
    "家用电器": "APPLIANCE",
    "beauty": "BEAUTY",
    "美妆": "BEAUTY",
    "美妆个护": "BEAUTY",
    "food": "FOOD",
    "食品": "FOOD",
    "食品生鲜": "FOOD",
    "maternal": "MATERNAL",
    "母婴": "MATERNAL",
    "母婴玩具": "MATERNAL",
    "book": "BOOK",
    "图书": "BOOK",
    "home": "HOME",
    "家居": "HOME",
    "家具": "HOME",
    "pet": "PET",
    "宠物": "PET",
    "health": "HEALTH",
    "医疗": "HEALTH",
    "保健": "HEALTH",
    "car": "CAR",
    "汽车": "CAR",
}


def normalize_category(category: str | None) -> str | None:
    if not category:
        return None
    raw = category.strip().lower()
    return CATEGORY_MAP.get(raw, category.strip().upper())


def clean_search_keyword(keyword: str | None) -> str | None:
    if not keyword:
        return None
    kw = keyword.strip()
    # 纯代词与指代词过滤（防止模型误将代词传为检索关键词导致召回为空）
    if kw in {"这款", "这个", "它", "它们", "它俩", "第一个", "第二个", "第三个", "刚才那个", "上面那个", "前者", "后者"}:
        return None
    # 纯预算过滤（防止模型将纯预算数字误传为商品名称关键词）
    if re.match(r"^(?:只要)?\d+\s*(?:元|块)?\s*(?:左右|以内|以下|以上|上下|到\d+)?(?:的)?$", kw):
        return None
    # 移除常见的口语搜索前缀与量词修饰，保留核心商品词
    kw = re.sub(
        r"^(?:请问|请帮我|帮我找|帮我|麻烦|我想买|我想看|我想找|想买|想找|想要|求推荐|推荐|买|看下|看看|找一下|找个|找|有没有什么|有没有|有没|给我推荐|给推荐)\s*(?:一款|一个|个|一部|部|一台|台|几款|几个|一些|点)?\s*",
        "", kw,
    )
    kw = re.sub(r"(性价比高|性价比最高|性价比|便宜点|便宜|实用|好用|最新款|最新)的?", "", kw)
    kw = kw.strip()
    return kw if kw else None


def clean_kb_query(query: str | None) -> str:
    """清理知识库检索中的口语化前缀，保留核心政策咨询词"""
    if not query:
        return ""
    q = query.strip()
    q = re.sub(r"^(请问一下|请问|我想咨询|我想知道|我想了解|咨询一下|请教一下|麻烦问下|问一下|麻烦看一下|帮我查查|帮我查下)\s*", "", q)
    return q.strip() if q.strip() else query.strip()


# 检索节点打点（可观测：命中数与来源）
_observe_product = observe_retrieval("rag::product_search")(hybrid_product_search)


@tool
async def product_search(keyword: str | None = None, category: str | None = None,
                         min_price: float | None = None, max_price: float | None = None,
                         top_k: int = 5) -> dict:
    """检索在售商品。当用户表达购物需求（品类/预算/偏好关键词）时调用。
    采用语义混合检索：语义召回（拍照/夜拍/vlog/游戏本 等特性词效果更好）+ 类目/价格过滤，返回商品列表（含价格、库存、卖点与站内跳转链接 link 字段）。
    keyword 填商品特性词或短语，如"拍照""夜拍""游戏本""轻薄"。"""
    ctx = get_tool_ctx()
    entities = ctx.setdefault("active_entities", {})
    norm_category = normalize_category(category)
    cleaned_keyword = clean_search_keyword(keyword)

    # 若未显式指定品类，先判断 keyword 本身是否是一个新类目（如上一轮看电脑，本轮买家说"看下手机"）
    if not norm_category and cleaned_keyword:
        kw_category = normalize_category(cleaned_keyword)
        if kw_category and kw_category in set(CATEGORY_MAP.values()):
            norm_category = kw_category
            cleaned_keyword = None  # 核心词已作为类目过滤，清空关键词避免过度约束召回

    # 若仍无品类，从会话实体记忆中继承上一轮的品类偏好
    if not norm_category and entities.get("last_category"):
        norm_category = entities["last_category"]
    try:
        result = await _observe_product(
            keyword=cleaned_keyword, category=norm_category, min_price=min_price, max_price=max_price, top_k=top_k)
        if result is not None:
            if norm_category:
                entities["last_category"] = norm_category
            if isinstance(result, dict) and result.get("products"):
                entities["last_products"] = [
                    {"id": p.get("productId"), "name": p.get("name"), "price": p.get("price")}
                    for p in result["products"][:5] if p.get("productId")
                ]
            return result
    except Exception as e:
        logger.warning("hybrid product search failed, fallback to SQL: %s", e)
    res = await backend_client.product_search(
        user_id=int(ctx.get("user_id", 0)), keyword=cleaned_keyword or keyword, category=norm_category,
        min_price=min_price, max_price=max_price, top_k=top_k,
    )
    if norm_category:
        entities["last_category"] = norm_category
    if isinstance(res, dict) and res.get("products"):
        entities["last_products"] = [
            {"id": p.get("productId"), "name": p.get("name"), "price": p.get("price")}
            for p in res["products"][:5] if p.get("productId")
        ]
    return res


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
    entities = ctx.setdefault("active_entities", {})
    res = await backend_client.order_query(
        user_id=int(ctx.get("user_id", 0)), status=status,
    )
    if isinstance(res, dict) and res.get("orders") and isinstance(res["orders"], list) and res["orders"]:
        entities["last_order_id"] = res["orders"][0].get("orderId")
    return res


@tool
async def order_create(product_id: int = 0, quantity: int = 1,
                       receiver_name: str = "", receiver_phone: str = "",
                       receiver_address: str = "") -> dict:
    """生成待用户确认的下单动作，不创建订单。
    默认复用买家保存的默认收货地址；只有买家明确提供新信息时才传入覆盖值。
    返回确认卡片所需的商品、数量、金额、收货信息和 actionId。"""
    ctx = get_tool_ctx()
    entities = ctx.setdefault("active_entities", {})
    target_product_id = product_id
    if not target_product_id and entities.get("last_products"):
        target_product_id = entities["last_products"][0]["id"]
    if not target_product_id:
        return {"error": "未指定要下单的商品，请先挑选商品或告知商品名称"}
    result = await backend_client.order_prepare(
        user_id=int(ctx.get("user_id", 0)),
        conversation_id=int(ctx.get("conversation_id", 0)),
        product_id=target_product_id, quantity=quantity,
        receiver_name=receiver_name, receiver_phone=receiver_phone,
        receiver_address=receiver_address,
    )
    if "error" not in result:
        ctx.setdefault("actions", []).append({"type": "ORDER_CREATE", **result})
        result = {**result, "status": "PENDING_CONFIRMATION"}
    return result


@tool
async def order_cancel_prepare(order_id: int = 0, reason: str = "买家申请取消") -> dict:
    """准备取消待支付订单，返回待买家确认的动作卡片；绝不直接取消订单。
    order_id 必须来自 order_query，reason 是买家明确给出的取消原因。"""
    ctx = get_tool_ctx()
    entities = ctx.setdefault("active_entities", {})
    target_order_id = order_id or entities.get("last_order_id", 0)
    if not target_order_id:
        return {"error": "未找到需要取消的订单，请先提供订单号或查询订单"}
    result = await backend_client.order_cancel_prepare(
        user_id=int(ctx.get("user_id", 0)), conversation_id=int(ctx.get("conversation_id", 0)),
        order_id=target_order_id, reason=reason,
    )
    if "error" not in result:
        ctx.setdefault("actions", []).append({"type": "ORDER_CANCEL", **result})
        result = {**result, "status": "PENDING_CONFIRMATION"}
    return result


@tool
async def after_sale_prepare(order_id: int, order_item_id: int, service_type: str,
                             issue_category: str, reason: str, quantity: int = 1) -> dict:
    """准备售后申请并返回待买家确认的动作卡片；绝不直接创建售后单。
    order_id/order_item_id 必须来自 order_query。service_type 可选 RETURN_REFUND/EXCHANGE/
    REFUND_ONLY/ISSUE_REPORT；issue_category 可选 PERSONAL/QUALITY/MERCHANT/PLATFORM。"""
    ctx = get_tool_ctx()
    result = await backend_client.after_sale_prepare(
        user_id=int(ctx.get("user_id", 0)), conversation_id=int(ctx.get("conversation_id", 0)),
        order_id=order_id, order_item_id=order_item_id, service_type=service_type,
        issue_category=issue_category, reason=reason, quantity=quantity,
    )
    if "error" not in result:
        ctx.setdefault("actions", []).append({"type": "AFTER_SALE_APPLY", **result})
        result = {**result, "status": "PENDING_CONFIRMATION"}
    return result


@tool
async def kb_search(query: str, doc_type: str = "ALL", product_id: int | None = None, top_k: int = 4) -> dict:
    """检索知识库（商品介绍/售后政策/常见问题）。回答退换货政策、保修规则、商品介绍细节时调用。
    返回结构化来源 context；answerable=false 表示证据不足或检索不可用，禁止根据常识补全政策。
    top_k 仅为兼容既有工具调用保留，最终候选数由检索流水线统一配置。"""
    cleaned_query = clean_kb_query(query)
    result = await retrieval.get_retrieval_pipeline().search(
        cleaned_query or query, doc_type=doc_type, product_id=product_id
    )
    citations = (
        [asdict(citation) for citation in result.citations]
        if result.answerable else []
    )
    citation_titles = {
        citation["chunk_id"]: citation["title"] for citation in citations
    }
    hits = []
    for hit in result.hits if result.answerable else ():
        serialized = asdict(hit)
        serialized["matched_by"] = sorted(serialized["matched_by"])
        serialized["source"] = citation_titles.get(hit.chunk_id, "知识库资料")
        hits.append(serialized)

    ctx = get_tool_ctx()
    ctx.update({
        "rag_used": True,
        "rag_answerable": result.answerable,
        "rag_reason": result.reason,
        "rag_allowed_citations": {
            citation["id"]: citation for citation in citations
        } if result.answerable else {},
    })
    ctx["degraded"] = bool(
        ctx.get("degraded")
        or result.degraded
        or result.reason == "retrieval_unavailable"
    )

    return {
        "answerable": result.answerable,
        "reason": result.reason,
        "context": result.context if result.answerable else "",
        "citations": citations,
        "hits": hits,
        "degraded": result.degraded,
        "degraded_reasons": list(result.degraded_reasons),
    }


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


ALL_TOOLS = [product_search, product_detail, order_query, order_create, order_cancel_prepare,
             after_sale_prepare, kb_search, escalate_to_human, web_search]
