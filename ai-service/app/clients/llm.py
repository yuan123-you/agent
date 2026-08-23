"""LLM and embedding factories backed entirely by environment configuration."""
from __future__ import annotations

import logging
from functools import lru_cache
from langchain_openai import ChatOpenAI

from app.config import settings
from app.clients.ollama import OllamaEmbeddings

logger = logging.getLogger(__name__)

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


@lru_cache
def get_embeddings() -> OllamaEmbeddings:
    """Return the single local Qwen3 embedding client."""
    return OllamaEmbeddings(
        base_url=settings.ollama_base_url,
        model=settings.embedding_model,
        dimensions=settings.embedding_dim,
        keep_alive=settings.ollama_keep_alive,
        num_ctx=settings.ollama_num_ctx,
        num_gpu=settings.ollama_num_gpu,
    )
