"""工具定义：身份上下文由服务端 ContextVar 注入（不信任模型生成的身份），支持会话级实体记忆"""
import asyncio
import contextvars
import logging
import re
from dataclasses import asdict

from langchain_core.tools import tool

from app.rag import retrieval
from app.request_policy import requests_human
from app.clients.backend_client import backend_client
from app.observability.telemetry import observe_retrieval
from app.rag.product_index import _match, hybrid_product_search, _is_phone_accessory
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
    "轻薄本": "COMPUTER",
    "游戏本": "COMPUTER",
    "超极本": "COMPUTER",
    "平板": "DIGITAL",
    "平板电脑": "COMPUTER",
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


def category_from_user_text(text: str) -> str | None:
    """Only unambiguous category words from the buyer, never assistant examples."""
    matches = set()
    for alias, category in CATEGORY_MAP.items():
        if len(alias) < 2:
            continue
        pattern = rf"\b{re.escape(alias)}\b" if alias.isascii() else re.escape(alias)
        if re.search(pattern, text, re.IGNORECASE):
            matches.add(category)
    return next(iter(matches)) if len(matches) == 1 else None


def clean_search_keyword(keyword: str | None) -> str | None:
    if not keyword:
        return None
    kw = keyword.strip()
    # 纯代词与指代词过滤（防止模型误将代词传为检索关键词导致召回为空）
    if kw in {"这款", "这个", "它", "它们", "它俩", "第一个", "第二个", "第三个", "刚才那个", "上面那个", "前者", "后者", "第一款", "第二款", "第三款"}:
        return None
    # 移除句尾无要求/随便/都行等口语短语
    kw = re.sub(r"(?:[，,、\s]+)?(?:没有要求|无要求|没什么要求|随便|都行|都可以|没要求)$", "", kw).strip()
    # 纯预算过滤（防止模型将纯预算数字误传为商品名称关键词）
    if re.match(r"^(?:只要)?\d+\s*(?:元|块)?\s*(?:左右|以内|以下|以上|上下|到\d+)?(?:的)?$", kw):
        return None
    # 移除常见的口语搜索与下单前缀与量词修饰，保留核心商品词
    kw = re.sub(
        r"^(?:请问|请帮我|帮我找|帮我下单|帮下单|我想下单|想下单|帮我买|帮买|购买|订购|帮我|麻烦|我想买|我想看|我想找|想买|想找|想要|求推荐|推荐|下单|买|看下|看看|找一下|找个|找|有没有什么|有没有|有没|给我推荐|给推荐|再推荐|重新推荐|换一个|换一款|换个|换)\s*(?:一款|一个|个|一部|部|一台|台|几款|几个|一些|点)?\s*",
        "", kw,
    )
    # 移除口语形容词和比较词
    kw = re.sub(r"(?:性价比高|性价比最高|性价比|便宜一点|便宜点|便宜|稍便宜|更便宜|实用|好用|最新款|最新|其它|其他|别的|另外的?)(?:的)?", "", kw)
    kw = re.sub(r"^(?:有|要|只要|需要)\s*", "", kw)
    # 移除嵌入的纯预算修饰（如 3000元的、2000-3000元的）
    kw = re.sub(r"\d+(?:\.\d+)?\s*(?:元|块)?\s*(?:左右|以内|以下|以上|上下)?(?:的)?", "", kw)
    kw = re.sub(r"^\d+(?:\.\d+)?\s*(?:元|块)?\s*(?:左右|以内|以下|以上|上下)?(?:的)?", "", kw)
    kw = re.sub(r"^[，,、\s]+|[，,、\s]+$", "", kw).strip()
    if kw in {"一点", "一点的", "点", "点的", "的", "换", "个", "款", "一下"}:
        return None
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


def _resolve_product_reference(product_id: int, products: list[dict], text: str) -> int | None:
    """Resolve only an explicit position or an unambiguous single remembered item."""
    if product_id:
        return product_id
    positions = re.findall(
        r"第\s*([一二两三四五六七八九十\d]+)\s*(?:款|个(?!月)|件|台|部|(?=$|[，。？！!?、,.的]))",
        text,
    )
    if positions:
        numbers = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
                   "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        ordinals = {int(value) if value.isdigit() else numbers.get(value, 0)
                    for value in positions}
        if len(ordinals) != 1:
            return None
        ordinal = ordinals.pop()
        return products[ordinal - 1].get("id") if 1 <= ordinal <= len(products) else None
    if "最后一" in text and products:
        return products[-1].get("id")
    return products[0].get("id") if len(products) == 1 else None


async def _refresh_product_results(result: dict, user_id: int, category: str | None,
                                   min_price: float | None, max_price: float | None,
                                   allow_accessories: bool = False) -> dict:
    """Use the catalog only to rank; publish current business facts, never stale prices."""
    products = result.get("products") or []
    if not products:
        return result
    details = await asyncio.gather(*(
        backend_client.product_detail(user_id=user_id, product_id=int(product["productId"]))
        for product in products
    ), return_exceptions=True)
    current = []
    unavailable = False
    for product, detail in zip(products, details, strict=True):
        if (not isinstance(detail, dict) or "error" in detail
                or detail.get("productId") != product.get("productId")):
            get_tool_ctx()["degraded"] = True
            unavailable = True
            continue
        if (int(detail.get("stock") or 0) > 0 and detail.get("price") is not None
                and _match(detail, category, min_price, max_price, allow_accessories=allow_accessories)):
            current.append({**product, **detail, "link": f"mall://product/{detail['productId']}"})
    refreshed = {**result, "products": current, "total": len(current)}
    if unavailable and not current:
        refreshed["error"] = "商品实时信息暂不可用，请重新查询或稍后再试"
    return refreshed


@tool
async def product_search(keyword: str | None = None, category: str | None = None,
                         min_price: float | None = None, max_price: float | None = None,
                         top_k: int = 5) -> dict:
    """检索在售商品。当用户表达购物需求（品类/预算/偏好关键词）时调用。
    采用语义混合检索：语义召回（拍照/夜拍/vlog/游戏本 等特性词效果更好）+ 类目/价格过滤，返回商品列表（含价格、库存、卖点与站内跳转链接 link 字段）。
    keyword 填商品特性词或短语，如"拍照""夜拍""游戏本""轻薄"。"""
    ctx = get_tool_ctx()
    entities = ctx.setdefault("active_entities", {})
    norm_category = ctx.get("requested_category") or normalize_category(category)
    cleaned_keyword = clean_search_keyword(keyword)
    keyword_category = category_from_user_text(cleaned_keyword or "")
    if ctx.get("requested_category") and keyword_category and keyword_category != norm_category:
        cleaned_keyword = None
    budget = ctx.get("requested_budget") or {}
    if budget:
        min_price, max_price = budget.get("min_price"), budget.get("max_price")

    # 若未显式指定品类，先判断 keyword 本身是否是一个新类目（如上一轮看电脑，本轮买家说"看下手机"）
    if not norm_category and cleaned_keyword:
        kw_category = normalize_category(cleaned_keyword)
        if kw_category and kw_category in set(CATEGORY_MAP.values()):
            norm_category = kw_category
            cleaned_keyword = None  # 核心词已作为类目过滤，清空关键词避免过度约束召回
    elif norm_category and cleaned_keyword:
        kw_category = normalize_category(cleaned_keyword)
        if kw_category == norm_category:
            cleaned_keyword = None  # 关键词与已知类目完全一致，清空避免过度约束召回

    # 若仍无品类，从会话实体记忆中继承上一轮的品类偏好
    if not norm_category and entities.get("last_category"):
        norm_category = entities["last_category"]
    allow_accessories = _is_phone_accessory(cleaned_keyword or "")
    try:
        result = await _observe_product(
            keyword=cleaned_keyword, category=norm_category, min_price=min_price, max_price=max_price, top_k=top_k)
        if result is not None:
            result = await _refresh_product_results(
                result, int(ctx.get("user_id", 0)), norm_category, min_price, max_price,
                allow_accessories=allow_accessories)
            if norm_category:
                entities["last_category"] = norm_category
            if isinstance(result, dict) and isinstance(result.get("products"), list):
                entities["last_products"] = [
                    {"id": p.get("productId"), "name": p.get("name"), "price": p.get("price")}
                    for p in result["products"][:10] if p.get("productId")
                ]
            return result
    except Exception as e:
        logger.warning("hybrid product search failed, fallback to SQL: %s", e)
    res = await backend_client.product_search(
        user_id=int(ctx.get("user_id", 0)), keyword=cleaned_keyword, category=norm_category,
        min_price=min_price, max_price=max_price, top_k=top_k,
    )
    if isinstance(res, dict) and isinstance(res.get("products"), list):
        filtered = [
            p for p in res["products"]
            if _match(p, norm_category, min_price, max_price, allow_accessories=allow_accessories)
        ]
        res = {**res, "products": filtered, "total": len(filtered)}
    if norm_category:
        entities["last_category"] = norm_category
    if isinstance(res, dict) and isinstance(res.get("products"), list):
        entities["last_products"] = [
            {"id": p.get("productId"), "name": p.get("name"), "price": p.get("price")}
            for p in res["products"][:10] if p.get("productId")
        ]
    return res


@tool
async def product_detail(product_id: int = 0) -> dict:
    """查询指定商品的详细信息（参数、介绍、价格、库存）。用于商品比较或深度介绍。
    product_id 必须来自 product_search 结果。"""
    ctx = get_tool_ctx()
    entities = ctx.setdefault("active_entities", {})
    target_id = _resolve_product_reference(
        product_id, entities.get("last_products") or [], ctx.get("latest_user_text", ""))
    if not target_id:
        return {"error": "请明确要查询的商品，或说明列表中的第几款"}
    return await backend_client.product_detail(
        user_id=int(ctx.get("user_id", 0)), product_id=target_id,
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
    target_product_id = _resolve_product_reference(
        product_id, entities.get("last_products") or [], ctx.get("latest_user_text", ""))
    if not target_product_id:
        return {"error": "请明确要下单的商品，或说明列表中的第几款"}
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
    ctx = get_tool_ctx()
    allowed = ctx.setdefault("rag_allowed_citations", {})
    chunk_sources = {value["chunk_id"]: key for key, value in allowed.items()}
    next_id = max((int(key[1:]) for key in allowed), default=0) + 1
    remap = {}
    citations = []
    for citation in result.citations if result.answerable else ():
        source_id = chunk_sources.get(citation.chunk_id)
        if source_id is None:
            source_id = f"S{next_id}"
            next_id += 1
            chunk_sources[citation.chunk_id] = source_id
        remap[citation.id] = source_id
        serialized = {**asdict(citation), "id": source_id}
        allowed[source_id] = serialized
        citations.append(serialized)
    context = re.sub(
        r'(<source\s+id=")(S[1-9][0-9]*)(")',
        lambda match: match[1] + remap.get(match[2], match[2]) + match[3],
        result.context,
    ) if result.answerable else ""
    citation_titles = {
        citation["chunk_id"]: citation["title"] for citation in citations
    }
    hits = []
    for hit in result.hits if result.answerable else ():
        serialized = asdict(hit)
        serialized["matched_by"] = sorted(serialized["matched_by"])
        serialized["source"] = citation_titles.get(hit.chunk_id, "知识库资料")
        hits.append(serialized)

    previous_answerable = bool(ctx.get("rag_answerable"))
    if result.answerable or not previous_answerable:
        if result.answerable or ctx.get("rag_reason") != "retrieval_unavailable":
            ctx["rag_reason"] = result.reason
    ctx.update({"rag_used": True, "rag_answerable": previous_answerable or result.answerable})
    ctx["degraded"] = bool(
        ctx.get("degraded")
        or result.degraded
        or result.reason == "retrieval_unavailable"
    )

    return {
        "answerable": result.answerable,
        "reason": result.reason,
        "context": context,
        "citations": citations,
        "hits": hits,
        "degraded": result.degraded,
        "degraded_reasons": list(result.degraded_reasons),
    }


@tool
async def escalate_to_human(reason: str = "") -> dict:
    """转接人工客服。仅在用户明确要求转人工/投诉时调用，不得因无法解答擅自转接。"""
    ctx = get_tool_ctx()
    if not requests_human(ctx.get("latest_user_text", "")):
        return {"error": "买家未要求转人工，请继续回答当前问题，不得擅自转接"}
    result = await backend_client.escalate(
        user_id=int(ctx.get("user_id", 0)),
        conversation_id=int(ctx.get("conversation_id", 0)),
        reason=reason[:200],
    )
    ctx["escalated"] = "error" not in result
    return result


ALL_TOOLS = [product_search, product_detail, order_query, order_create, order_cancel_prepare,
             after_sale_prepare, kb_search, escalate_to_human, web_search]
