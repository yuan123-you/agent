-- ============================================================================
-- V11: 物流信息 + 商品搜索增强
--   order_info.delivery_company  发货物流公司（对标 mall oms_order.delivery_company）
--   product FULLTEXT(ngram)      商品名/品牌/卖点全文索引，提升中文搜索召回
-- ============================================================================

ALTER TABLE order_info
  ADD COLUMN delivery_company VARCHAR(64) NULL COMMENT '物流公司' AFTER logistics_no;

-- 中文检索用 ngram 分词（MySQL 8 内置）；搜索相关度排序见 ProductMapper.searchByKeyword
ALTER TABLE product
  ADD FULLTEXT INDEX ft_product_search (name, brand, selling_points) WITH PARSER ngram;
