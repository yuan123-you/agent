"""后端回调客户端：AI 工具执行业务动作（商品检索/订单/转人工/知识库回写）"""
import logging

import httpx

from app.config import settings
from app.resilience import budget_headers, run

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

    _READ_ONLY_POSTS = frozenset({
        "/internal/tools/product/search", "/internal/tools/product/detail",
        "/internal/tools/order/query", "/internal/tools/products/all",
        "/internal/kb/search", "/internal/kb/chunks/current", "/internal/kb/titles",
    })
    _KEYED_PREPARATIONS = frozenset({
        "/internal/tools/order/prepare", "/internal/tools/order/cancel/prepare",
        "/internal/tools/after-sale/prepare",
    })

    @classmethod
    def _replay_safe_post(cls, path, body):
        return path in cls._READ_ONLY_POSTS or (path in cls._KEYED_PREPARATIONS
            and isinstance(body.get("preparationKey"),str) and bool(body["preparationKey"].strip()))

    async def _perform(self, client, method, path, *, body=None, params=None,
                       replay_safe=False, max_attempts=3, timeout_s=None):
        async def attempt(timeout):
            response = await client.request(method,path,json=body,params=params,
                                            timeout=timeout,headers=budget_headers())
            response.raise_for_status()
            return response
        return await run("backend.read" if replay_safe else "backend.write",attempt,
                         replay_safe=replay_safe,max_attempts=max_attempts,
                         attempt_timeout_s=timeout_s or settings.tool_callback_timeout_s)

    @staticmethod
    def _envelope(response):
        payload = response.json()
        if not isinstance(payload,dict) or type(payload.get("code")) is not int:
            raise ValueError("invalid backend response envelope")
        return payload

    async def _get(self, path: str, params: dict | None = None, retries: int = 3) -> dict | list:
        try:
            response = await self._perform(self._client,"GET",path,params=params,
                                           replay_safe=True,max_attempts=retries)
            result = self._envelope(response)
            if result["code"] == 0:
                return result.get("data")
            return {"error":result.get("message","backend business error")}
        except Exception as error:
            logger.warning("backend read unavailable (%s)",type(error).__name__)
            return {"error":"后端服务暂时不可用，请稍后再试"}

    async def _post(self, path: str, body: dict, retries: int = 3) -> dict:
        # POST is not replay-safe merely because it is used as an RPC. Only the
        # explicit read allowlist or a backend-enforced stable preparation key qualifies.
        try:
            response = await self._perform(self._client,"POST",path,body=body,
                replay_safe=self._replay_safe_post(path,body),max_attempts=retries)
            result = self._envelope(response)
            if result["code"] == 0:
                return result.get("data") or {}
            return {"error":result.get("message","backend business error")}
        except Exception as error:
            logger.warning("backend operation unavailable (%s)",type(error).__name__)
            return {"error":"后端服务暂时不可用，请稍后再试"}

    async def record_ai_trace(self, trace_id: str, payload: dict) -> dict:
        return await self._post(f"/internal/ai-traces/{trace_id}", payload, retries=1)

    # ---------- 长期记忆管理 ----------

    async def get_user_memory(self, user_id: int) -> list[dict]:
        res = await self._get("/internal/memory", params={"userId": user_id})
        return res if isinstance(res, list) else []

    async def upsert_user_memory(self, user_id: int, memories: list[dict]) -> dict:
        return await self._post("/internal/memory/upsert", {
            "userId": user_id, "memories": memories,
        })

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
        """拉取全量在售商品（商品向量化 job 数据源：含参数/介绍/销量）。
        全量商品响应较大，必须走长超时客户端，避免 3s 默认超时导致同步失败。"""
        response = await self._perform(self._long_client,"POST","/internal/tools/products/all",
                                       body={},replay_safe=True,timeout_s=60)
        result = self._envelope(response)
        if result["code"] != 0:
            raise RuntimeError("product snapshot rejected")
        return (result.get("data") or {}).get("products") or []

    async def order_query(self, user_id: int, status: str = "ALL") -> dict:
        return await self._post("/internal/tools/order/query", {
            "userId": user_id, "status": status,
        })

    async def order_prepare(self, user_id: int, conversation_id: int, product_id: int, quantity: int,
                           receiver_name: str, receiver_phone: str, receiver_address: str,
                           preparation_key: str | None = None) -> dict:
        return await self._post("/internal/tools/order/prepare", {
            "userId": user_id, "conversationId": conversation_id, "productId": product_id,
            "quantity": quantity, "receiverName": receiver_name, "receiverPhone": receiver_phone,
            "receiverAddress": receiver_address,
            **({"preparationKey": preparation_key} if preparation_key is not None else {}),
        })

    async def order_cancel_prepare(self, user_id: int, conversation_id: int,
                                   order_id: int, reason: str, preparation_key: str | None = None) -> dict:
        return await self._post("/internal/tools/order/cancel/prepare", {
            "userId": user_id, "conversationId": conversation_id,
            "orderId": order_id, "reason": reason,
            **({"preparationKey": preparation_key} if preparation_key is not None else {}),
        })

    async def after_sale_prepare(self, user_id: int, conversation_id: int, order_id: int,
                                 order_item_id: int, service_type: str, issue_category: str,
                                 reason: str, quantity: int, preparation_key: str | None = None) -> dict:
        return await self._post("/internal/tools/after-sale/prepare", {
            "userId": user_id, "conversationId": conversation_id, "orderId": order_id,
            "orderItemId": order_item_id, "serviceType": service_type,
            "issueCategory": issue_category, "reason": reason, "quantity": quantity,
            **({"preparationKey": preparation_key} if preparation_key is not None else {}),
        })

    async def escalate(self, user_id: int, conversation_id: int, reason: str) -> dict:
        return await self._post("/internal/tools/escalate", {
            "userId": user_id, "conversationId": conversation_id, "reason": reason,
        })

    # ---------- 知识库回写 ----------

    async def kb_chunks_batch(self, doc_id: int, chunks: list[dict], *,
                              doc_version: int | None = None) -> dict:
        """分块元数据落库，返回预分配的 chunk id 列表"""
        return await self._post_long("/internal/kb/chunks/batch", {
            "docId": doc_id, "docVersion": doc_version, "chunks": chunks,
        })

    async def _post_long(self, path: str, body: dict) -> dict:
        try:
            # Chunk allocation is a mutation without a replay contract: one attempt.
            response = await self._perform(self._long_client,"POST",path,body=body,
                                           replay_safe=False,timeout_s=60)
            result = self._envelope(response)
            return (result.get("data") or {}) if result["code"] == 0 else {"error":result.get("message")}
        except Exception as error:
            logger.warning("backend long operation unavailable (%s)",type(error).__name__)
            return {"error":"后端服务暂时不可用，请稍后再试"}

    async def kb_result(self, doc_id: int, status: str, chunk_count: int = 0,
                        fail_reason: str | None = None, vector_count: int | None = None, *,
                        doc_version: int | None = None) -> None:
        try:
            body = {
                "docId": doc_id, "docVersion": doc_version, "status": status,
                "chunkCount": chunk_count, "failReason": fail_reason,
            }
            if vector_count is not None:
                body["vectorCount"] = vector_count
            await self._perform(self._long_client,"POST","/internal/kb/result",body=body,
                                replay_safe=False,timeout_s=60)
        except Exception as e:
            logger.warning("kb_result callback failed (%s)",type(e).__name__)

    async def kb_keyword_search(self, query: str, doc_type: str = "ALL",
                                product_id: int | None = None, top_k: int = 4) -> dict:
        """关键词检索（RAG 兜底）：向量 Embedding 不可用或无命中时调用后端检索 ACTIVE 文档分块"""
        body = {"query": query, "topK": top_k}
        if doc_type and doc_type != "ALL":
            body["docType"] = doc_type
        if product_id is not None:
            body["productId"] = product_id
        return await self._post("/internal/kb/search", body)

    async def kb_current_chunks(self, chunk_ids: list[int]) -> dict[int, str]:
        """校验候选分块仍属于 ACTIVE 文档当前版本，并返回 chunkId → title。"""
        if not chunk_ids:
            return {}
        r = await self._post("/internal/kb/chunks/current", {"chunkIds": list(chunk_ids)}, retries=1)
        if "error" in r:
            raise RuntimeError("current chunk validation unavailable")
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
        async def attempt(timeout):
            request = self._long_client.build_request("GET",url,timeout=timeout,headers=budget_headers())
            backend_url = self._long_client.base_url
            if (request.url.scheme,request.url.host,request.url.port) != (
                    backend_url.scheme,backend_url.host,backend_url.port):
                # Credentials and internal hop budgets never leave the trusted backend origin.
                for name in ("X-Internal-Token","X-Request-Timeout-Ms","X-Request-Retry-Budget"):
                    request.headers.pop(name,None)
            response = await self._long_client.send(request)
            response.raise_for_status()
            return response.content
        return await run("document.download",attempt,replay_safe=True,attempt_timeout_s=60)


backend_client = BackendClient()

