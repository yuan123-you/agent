-- 知识库文档：记录实际写入 Milvus 的向量数（0 = 未向量化 /关键词降级）
ALTER TABLE kb_doc
    ADD COLUMN vector_count INT NOT NULL DEFAULT 0 COMMENT '实际写入Milvus的向量数(0=关键词降级模式)' AFTER chunk_count;