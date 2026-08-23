"""全局配置：全部来自环境变量 / .env，禁止硬编码密钥"""
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_chat_model: str = "gpt-4o-mini"
    llm_intent_model: str = "gpt-4o-mini"
    temperature: float = 0.3

    # Embedding（可独立配置：对话与向量模型可为不同供应商，如 DeepSeek 对话 + 千问 embedding）
    embedding_api_base: str = ""   # 空 = 复用 llm_api_base
    embedding_api_key: str = ""    # 空 = 复用 llm_api_key
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # Milvus
    milvus_uri: str = "http://localhost:19530"
    milvus_collection: str = "kb_chunks"
    # 商品向量库（区别于政策/FAQ 知识库）：商品语料 + 混合检索
    milvus_product_collection: str = "product_index"
    product_sync_enabled: bool = True
    product_sync_interval_s: int = 600

    # RAG 文档分块（字符数；中文字符通常接近一个 token）
    rag_chunk_size: int = Field(default=600, ge=200)
    rag_chunk_overlap: int = Field(default=90, ge=0)

    @model_validator(mode="after")
    def validate_chunk_window(self):
        if self.rag_chunk_overlap >= self.rag_chunk_size:
            raise ValueError("rag_chunk_overlap must be smaller than rag_chunk_size")
        return self

    # 后端
    backend_base_url: str = "http://localhost:8080"
    internal_token: str = "dev-internal-token"
    tool_callback_timeout_s: int = 3
    max_tool_loops: int = 4
    # Agent 会话：单次请求总超时（秒）与图递归深度上限（防工具循环/异常深递归失控）
    chat_timeout_s: int = 60
    agent_recursion_limit: int = 20

    # 链接后验校验
    link_guard_enabled: bool = True

    # ── Langfuse 全链路追踪（可观测性）────
    # 关闭时全部 notrace 零开销；开启后各意图/工具/RAG/生成节点写入 Langfuse
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"
    langfuse_release: str = "ai-service"   # 便于区分版本对比指标

    log_level: str = "INFO"


settings = Settings()

