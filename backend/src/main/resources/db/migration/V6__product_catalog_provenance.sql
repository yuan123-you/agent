-- Product catalog provenance. Existing V1 products have no source facts, so all
-- provenance columns stay nullable. The two UTF-8 source keys total at most
-- 2,040 indexed bytes (255 * 4 * 2), below MySQL 8 InnoDB's 3,072-byte limit;
-- no prefix index is used so source identity remains exact.
ALTER TABLE product
  MODIFY COLUMN image_url VARCHAR(512) NULL COMMENT '主图URL',
  ADD COLUMN currency VARCHAR(16) NULL COMMENT '价格币种',
  ADD COLUMN source_name VARCHAR(255) NULL COMMENT '来源名称',
  ADD COLUMN source_url VARCHAR(2048) NULL COMMENT '来源商品URL',
  ADD COLUMN source_product_id VARCHAR(255) NULL COMMENT '来源商品标识',
  ADD COLUMN source_updated_at DATETIME(3) NULL COMMENT '来源更新时间',
  ADD COLUMN collected_at DATETIME(3) NULL COMMENT '采集时间',
  ADD COLUMN original_image_url VARCHAR(2048) NULL COMMENT '原始图片URL',
  ADD COLUMN image_sha256 CHAR(64) NULL COMMENT '图片SHA-256',
  ADD COLUMN simulated_commerce_fields TINYINT NOT NULL DEFAULT 0 COMMENT '库存销量是否模拟',
  ADD UNIQUE KEY uk_product_source (source_name, source_product_id),
  ADD KEY idx_product_collected_status (collected_at, status);