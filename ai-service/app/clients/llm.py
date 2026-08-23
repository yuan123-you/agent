"""LLM 工厂：ChatOpenAI（OpenAI 兼容接口）+ Embeddings，全部配置来自环境变量
Embedding 供应商适配：
- maas.aliyuncs.com 专属端点 → MaaSEmbeddings（input.contents 格式）
- 其他 OpenAI 兼容端点     → OpenAIEmbeddings（input 数组格式）
"""
from functools import lru_cache

import httpx
from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI

from app.config import settings


def get_chat_llm(streaming: bool = True) -> ChatOpenAI:
    """对话模型（导购生成用，支持流式）"""
    return ChatOpenAI(
        base_url=settings.llm_api_base,
        api_key=settings.llm_api_key,
        model=settings.llm_chat_model,
        temperature=settings.temperature,
        streaming=streaming,
        timeout=60,
        max_retries=1,
    )


def get_intent_llm() -> ChatOpenAI:
    """意图识别模型（低延迟、温度 0）"""
    return ChatOpenAI(
        base_url=settings.llm_api_base,
        api_key=settings.llm_api_key,
        model=settings.llm_intent_model,
        temperature=0,
        streaming=False,
        timeout=20,
        max_retries=1,
    )


class MaaSEmbeddings(Embeddings):
    """阿里云百炼专属 MaaS 端点 Embedding 适配器
    请求格式为 OpenAI 风格（input 数组），响应为阿里原生风格（output.embeddings）"""

    def __init__(self, base_url: str, api_key: str, model: str):
        self._url = base_url.rstrip("/") + "/embeddings"
        self._headers = {"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"}
        self._model = model

    async def _acall(self, texts: list[str]) -> list[list[float]]:
        payload = {"model": self._model, "input": texts}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(self._url, headers=self._headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        # 兼容两种响应：标准 OpenAI（data[].embedding）/ 阿里原生（output.embeddings[].embedding）
        items = data.get("data") or data.get("output", {}).get("embeddings", [])
        # 按 index 排序保证与输入顺序一致
        items.sort(key=lambda e: e.get("index", 0))
        return [e["embedding"] for e in items]

    async def aembed_query(self, text: str) -> list[float]:
        return (await self._acall([text]))[0]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """分批调用（MaaS 专属端点限制单请求 token 上限，大批量会 400）"""
        results: list[list[float]] = []
        batch_size = 4
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            results.extend(await self._acall(batch))
        return results

    def embed_query(self, text: str) -> list[float]:
        import asyncio
        return asyncio.run(self.aembed_query(text))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        import asyncio
        return asyncio.run(self.aembed_documents(texts))


@lru_cache
def get_embeddings() -> Embeddings:
    """Embedding 模型：按端点类型适配（MaaS 专属 / OpenAI 兼容），供应商可与对话模型不同"""
    base = settings.embedding_api_base or settings.llm_api_base
    key = settings.embedding_api_key or settings.llm_api_key
    if "maas.aliyuncs.com" in base:
        return MaaSEmbeddings(base, key, settings.embedding_model)
    return OpenAIEmbeddings(
        base_url=base,
        api_key=key,
        model=settings.embedding_model,
    )
