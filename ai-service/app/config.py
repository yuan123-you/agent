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
    embedding_fallback_models: str = "text-embedding-v1,text-embedding-v3,text-embedding-v2"
    embedding_dim: int = 1536
    embedding_provider: str = "openai"  # openai | maas | ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_keep_alive: str = "10m"
    ollama_num_ctx: int = Field(default=2048, ge=512)
    ollama_num_gpu: int = Field(default=10, ge=0)

    # Optional Qwen3 second-stage reranker
    reranker_enabled: bool = False
    reranker_base_url: str = "http://localhost:11434"
    reranker_model: str = "dengcao/Qwen3-Reranker-4B:Q4_K_M"
    reranker_candidates: int = Field(default=8, ge=1, le=32)
    reranker_timeout_s: float = Field(default=120.0, gt=0)

    @property
    def embedding_model_order(self) -> tuple[str, ...]:
        """Primary model followed by unique, ordered CSV fallback models."""
        models = [self.embedding_model, *self.embedding_fallback_models.split(",")]
        return tuple(dict.fromkeys(model.strip() for model in models if model.strip()))

    # Milvus
    milvus_uri: str = "http://localhost:19530"
    milvus_collection: str = "kb_chunks"
    # Existing collections are checked before ingest so paid/already-generated vectors are never regenerated.
    milvus_legacy_collections: str = ""

    @property
    def milvus_legacy_collection_names(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(
            name.strip() for name in self.milvus_legacy_collections.split(",")
            if name.strip() and name.strip() != self.milvus_collection
        ))
    # 商品向量库（区别于政策/FAQ 知识库）：商品语料 + 混合检索
    milvus_product_collection: str = "product_index"
    product_sync_enabled: bool = True
    product_sync_interval_s: int = 600

    # RAG 文档分块（字符数；中文字符通常接近一个 token）
    rag_chunk_size: int = Field(default=600, ge=200)
    rag_chunk_overlap: int = Field(default=90, ge=0)

    # T10 RAG 检索与回答置信度
    rag_vector_recall_k: int = Field(default=20, gt=0)
    rag_bm25_recall_k: int = Field(default=20, gt=0)
    rag_rrf_k: int = Field(default=60, gt=0)
    rag_rrf_top_k: int = Field(default=10, gt=0)
    rag_final_top_k: int = Field(default=4, gt=0)
    rag_answer_min_score: float = Field(default=0.45, ge=0, le=1)
    rag_answer_high_confidence_score: float = Field(default=0.65, ge=0, le=1)
    rag_answer_min_margin: float = Field(default=0.05, ge=0, le=1)
    rag_vector_score_center: float = Field(default=0.45, ge=0, le=1)
    rag_vector_score_scale: float = Field(default=0.12, gt=0)
    rag_bm25_score_scale: float = Field(default=8.0, gt=0)

    # T10 HTTP reranker（默认关闭；不影响 Stage 1 本地 reranker）
    rag_reranker_enabled: bool = False
    rag_reranker_model: str = "Qwen/Qwen3-Reranker-4B"
    rag_reranker_base_url: str = "http://localhost:8001"
    rag_reranker_endpoint: str = "/v1/rerank"
    rag_reranker_api_key: str = ""
    rag_reranker_timeout_s: float = Field(default=10.0, gt=0)
    rag_reranker_batch_size: int = Field(default=10, gt=0)

    @model_validator(mode="after")
    def validate_chunk_window(self):
        if self.rag_chunk_overlap >= self.rag_chunk_size:
            raise ValueError("rag_chunk_overlap must be smaller than rag_chunk_size")
        if self.rag_final_top_k > self.rag_rrf_top_k:
            raise ValueError("rag_final_top_k must not exceed rag_rrf_top_k")
        if self.rag_rrf_top_k > min(self.rag_vector_recall_k, self.rag_bm25_recall_k):
            raise ValueError("rag_rrf_top_k must fit within recall windows")
        if self.rag_answer_min_score > self.rag_answer_high_confidence_score:
            raise ValueError("rag_answer_min_score must not exceed high confidence score")
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



