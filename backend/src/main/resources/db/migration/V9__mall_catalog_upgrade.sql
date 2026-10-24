-- ============================================================================
-- V9: 商城目录升级（对标 macrozheng/mall 的 PMS 模型改造）
--   mall_category  <- pms_product_category（层级分类 + 导航控制）
--   mall_brand     <- pms_brand（品牌 + 展示控制）
--   mall_sku       <- pms_sku_stock（SKU 规格与库存）
--   product        <- 增加 category_id / brand_id 关联（保留原字符串冗余列，
--                     AI 客服的 category 字符串检索链路不受影响）
--   order_item     <- 增加 sku 快照列
--   cart_item      <- 增加 sku_id
-- ============================================================================

-- ---------- 商品分类（层级，parent_id=0 为一级） ----------
CREATE TABLE mall_category (
  id           BIGINT       NOT NULL AUTO_INCREMENT COMMENT '分类ID',
  parent_id    BIGINT       NOT NULL DEFAULT 0 COMMENT '上级分类ID(0=一级分类)',
  name         VARCHAR(64)  NOT NULL COMMENT '分类名称',
  level        TINYINT      NOT NULL DEFAULT 1 COMMENT '分类级别:1->一级;2->二级',
  icon         VARCHAR(255) NULL COMMENT '图标URL',
  sort         INT          NOT NULL DEFAULT 0 COMMENT '排序(越小越靠前)',
  nav_status   TINYINT      NOT NULL DEFAULT 1 COMMENT '是否显示在导航栏:0->否;1->是',
  show_status  TINYINT      NOT NULL DEFAULT 1 COMMENT '显示状态:0->隐藏;1->显示',
  keywords     VARCHAR(255) NULL COMMENT '搜索关键词',
  description  VARCHAR(255) NULL COMMENT '描述',
  created_at   DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at   DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  deleted      TINYINT      NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  KEY idx_parent (parent_id, sort),
  KEY idx_name (name)
) ENGINE=InnoDB COMMENT='商品分类表(对标mall pms_product_category)';

-- ---------- 品牌 ----------
CREATE TABLE mall_brand (
  id            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '品牌ID',
  name          VARCHAR(64)  NOT NULL COMMENT '品牌名称',
  first_letter  VARCHAR(8)   NULL COMMENT '首字母(检索用)',
  logo          VARCHAR(255) NULL COMMENT '品牌logo',
  big_pic       VARCHAR(255) NULL COMMENT '专区大图',
  brand_story   VARCHAR(1024) NULL COMMENT '品牌故事',
  sort          INT          NOT NULL DEFAULT 0 COMMENT '排序',
  show_status   TINYINT      NOT NULL DEFAULT 1 COMMENT '显示状态:0->隐藏;1->显示',
  product_count INT          NOT NULL DEFAULT 0 COMMENT '品牌下商品数量(冗余)',
  created_at    DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at    DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  deleted       TINYINT      NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  KEY idx_name (name),
  KEY idx_first_letter (first_letter)
) ENGINE=InnoDB COMMENT='品牌表(对标mall pms_brand)';

-- ---------- SKU 规格库存 ----------
CREATE TABLE mall_sku (
  id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT 'SKU ID',
  product_id  BIGINT       NOT NULL COMMENT '所属商品ID',
  sku_code    VARCHAR(64)  NULL COMMENT 'SKU编码',
  sp_data     VARCHAR(512) NULL COMMENT '销售属性JSON:[{"key":"颜色","value":"黑色"}]',
  price       DECIMAL(10,2) NOT NULL COMMENT 'SKU价格',
  stock       INT          NOT NULL DEFAULT 0 COMMENT '库存',
  lock_stock  INT          NOT NULL DEFAULT 0 COMMENT '锁定库存',
  low_stock   INT          NULL COMMENT '库存预警值',
  pic         VARCHAR(255) NULL COMMENT 'SKU图片',
  sale        INT          NOT NULL DEFAULT 0 COMMENT '销量',
  status      VARCHAR(16)  NOT NULL DEFAULT 'ENABLE' COMMENT 'ENABLE/DISABLE',
  version     INT          NOT NULL DEFAULT 0 COMMENT '乐观锁版本',
  created_at  DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at  DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  deleted     TINYINT      NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  KEY idx_product (product_id),
  KEY idx_product_code (product_id, sku_code)
) ENGINE=InnoDB COMMENT='SKU规格库存表(对标mall pms_sku_stock)';

-- ---------- product 关联分类/品牌 ----------
ALTER TABLE product
  ADD COLUMN category_id BIGINT NULL COMMENT '分类ID(mall_category.id,NULL=历史数据未归一)' AFTER category,
  ADD COLUMN brand_id    BIGINT NULL COMMENT '品牌ID(mall_brand.id,NULL=历史数据未归一)' AFTER brand,
  ADD KEY idx_category_id (category_id),
  ADD KEY idx_brand_id (brand_id);

-- ---------- 订单明细增加 SKU 快照 ----------
ALTER TABLE order_item
  ADD COLUMN sku_id BIGINT NULL COMMENT 'SKU ID(NULL=无规格商品)' AFTER product_id,
  ADD COLUMN sku_sp VARCHAR(512) NULL COMMENT 'SKU销售属性快照JSON' AFTER sku_id;

-- ---------- 购物车条目增加 SKU ----------
-- 0 = 无规格商品；唯一键扩展到 SKU 粒度（同商品不同规格为不同购物车行）
ALTER TABLE cart_item
  ADD COLUMN sku_id BIGINT NOT NULL DEFAULT 0 COMMENT 'SKU ID(0=无规格商品)' AFTER product_id,
  DROP INDEX uk_user_product,
  ADD UNIQUE KEY uk_user_product_sku (user_id, product_id, sku_id);

-- ============================================================================
-- 种子归一化：把 product 现有 category / brand 字符串归一化成分类与品牌记录，
-- 并回填关联 ID。同一字符串归并为同一分类/品牌，商品数据无需变动。
-- ============================================================================

-- 一级分类：来自现有商品的类目字符串
INSERT INTO mall_category (parent_id, name, level, nav_status, show_status, sort)
SELECT 0, p.category, 1, 1, 1, 0
FROM product p
WHERE p.deleted = 0
GROUP BY p.category;

-- 品牌：来自现有商品的品牌字符串，并统计商品数
INSERT INTO mall_brand (name, show_status, sort, product_count)
SELECT p.brand, 1, 0, COUNT(*)
FROM product p
WHERE p.deleted = 0
GROUP BY p.brand;

-- 回填商品 -> 分类/品牌 关联
UPDATE product p
JOIN mall_category c ON c.name = p.category AND c.level = 1 AND c.deleted = 0
SET p.category_id = c.id
WHERE p.deleted = 0 AND p.category_id IS NULL;

UPDATE product p
JOIN mall_brand b ON b.name = p.brand AND b.deleted = 0
SET p.brand_id = b.id
WHERE p.deleted = 0 AND p.brand_id IS NULL;

