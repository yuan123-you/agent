"""后端回调客户端：AI 工具执行业务动作（商品检索/订单/转人工/知识库回写）"""
import asyncio
import logging

import httpx

from app.config import settings

logger = logging.getLogger("ai-service.backend")


class BackendClient:
    def __init__(self):
        self._client = httpx.AsyncClient(
            base_url=settings.backend_base_url,
            headers={"X-Internal-Token": settings.internal_token},
            timeout=httpx.Timeout(settings.tool_callback_timeout_s),
            trust_env=False,  # 内部服务间调用不走系统代理（本机 Clash 等可能造成 502）
        )
        self._long_client = httpx.AsyncClient(
            base_url=settings.backend_base_url,
            headers={"X-Internal-Token": settings.internal_token},
            timeout=httpx.Timeout(60),
            trust_env=False,
        )

    async def _post(self, path: str, body: dict, retries: int = 2) -> dict:
        """POST 并解包统一响应体；失败返回 {error: ...} 而不抛异常（交给 LLM 友好告知用户）"""
        for attempt in range(retries):
            try:
                r = await self._client.post(path, json=body)
                r.raise_for_status()
                resp = r.json()
                if resp.get("code") == 0:
                    return resp.get("data") or {}
                return {"error": resp.get("message", "backend business error")}
            except Exception as e:
                if attempt == retries - 1:
                    logger.warning("backend call failed %s: %s", path, e)
                    return {"error": "后端服务暂时不可用，请稍后再试"}
                await asyncio.sleep(0.3)
        return {"error": "后端服务暂时不可用"}

    # ---------- 工具回调 ----------

    async def product_search(self, user_id: int, keyword: str | None = None, category: str | None = None,
                             min_price: float | None = None, max_price: float | None = None,
                             top_k: int = 5) -> dict:
        return await self._post("/internal/tools/product/search", {
            "userId": user_id, "keyword": keyword, "category": category,
            "minPrice": min_price, "maxPrice": max_price, "topK": top_k,
        })

    async def product_detail(self, user_id: int, product_id: int) -> dict:
        return await self._post("/internal/tools/product/detail", {
            "userId": user_id, "productId": product_id,
        })

    async def products_all(self) -> list[dict]:
        """拉取全量在售商品（商品向量化 job 数据源：含参数/介绍/销量）"""
        r = await self._post("/internal/tools/products/all", {})
        if "error" in r:
            raise RuntimeError(r["error"])
        return r.get("products") or []

    async def order_query(self, user_id: int, status: str = "ALL") -> dict:
        return await self._post("/internal/tools/order/query", {
            "userId": user_id, "status": status,
        })

    async def order_prepare(self, user_id: int, conversation_id: int, product_id: int, quantity: int,
                           receiver_name: str, receiver_phone: str, receiver_address: str) -> dict:
        return await self._post("/internal/tools/order/prepare", {
            "userId": user_id, "conversationId": conversation_id, "productId": product_id,
            "quantity": quantity, "receiverName": receiver_name, "receiverPhone": receiver_phone,
            "receiverAddress": receiver_address,
        })

    async def order_cancel_prepare(self, user_id: int, conversation_id: int,
                                   order_id: int, reason: str) -> dict:
        return await self._post("/internal/tools/order/cancel/prepare", {
            "userId": user_id, "conversationId": conversation_id,
            "orderId": order_id, "reason": reason,
        })

    async def after_sale_prepare(self, user_id: int, conversation_id: int, order_id: int,
                                 order_item_id: int, service_type: str, issue_category: str,
                                 reason: str, quantity: int) -> dict:
        return await self._post("/internal/tools/after-sale/prepare", {
            "userId": user_id, "conversationId": conversation_id, "orderId": order_id,
            "orderItemId": order_item_id, "serviceType": service_type,
            "issueCategory": issue_category, "reason": reason, "quantity": quantity,
        })

    async def escalate(self, user_id: int, conversation_id: int, reason: str) -> dict:
        return await self._post("/internal/tools/escalate", {
            "userId": user_id, "conversationId": conversation_id, "reason": reason,
        })

    # ---------- 知识库回写 ----------

    async def kb_chunks_batch(self, doc_id: int, chunks: list[dict]) -> dict:
        """分块元数据落库，返回预分配的 chunk id 列表"""
        return await self._post_long("/internal/kb/chunks/batch", {
            "docId": doc_id, "chunks": chunks,
        })

    async def _post_long(self, path: str, body: dict) -> dict:
        try:
            r = await self._long_client.post(path, json=body)
            r.raise_for_status()
            resp = r.json()
            if resp.get("code") == 0:
                return resp.get("data") or {}
            return {"error": resp.get("message")}
        except Exception as e:
            logger.warning("backend long call failed %s: %s", path, e)
            return {"error": str(e)}

    async def kb_result(self, doc_id: int, status: str, chunk_count: int = 0, fail_reason: str | None = None) -> None:
        try:
            await self._long_client.post("/internal/kb/result", json={
                "docId": doc_id, "status": status, "chunkCount": chunk_count, "failReason": fail_reason,
            })
        except Exception as e:
            logger.warning("kb_result callback failed: %s", e)

    async def kb_keyword_search(self, query: str, doc_type: str = "ALL",
                                product_id: int | None = None, top_k: int = 4) -> dict:
        """关键词检索（RAG 兜底）：向量 Embedding 不可用或无命中时调用后端检索 ACTIVE 文档分块"""
        return await self._post("/internal/kb/search", {
            "query": query, "docType": doc_type, "productId": product_id, "topK": top_k,
        })

    async def kb_current_chunks(self, chunk_ids: list[int]) -> dict[int, str]:
        """校验候选分块仍属于 ACTIVE 文档当前版本，并返回 chunkId → title。"""
        if not chunk_ids:
            return {}
        r = await self._post("/internal/kb/chunks/current", {"chunkIds": list(chunk_ids)}, retries=1)
        if "error" in r:
            return {}
        return {int(k): str(v) for k, v in r.items()}

    async def kb_titles(self, doc_ids: list[int]) -> dict:
        """文档标题批量查询：docId → title 映射（向量命中后用于展示来源标题）"""
        if not doc_ids:
            return {}
        r = await self._post("/internal/kb/titles", {"docIds": list(doc_ids)}, retries=1)
        if "error" in r:
            return {}
        return {int(k): v for k, v in r.items()}

    async def download_file(self, url: str) -> bytes:
        r = await self._long_client.get(url)
        r.raise_for_status()
        return r.content


backend_client = BackendClient()

