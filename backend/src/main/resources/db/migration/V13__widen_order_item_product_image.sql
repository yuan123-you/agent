-- 扩展订单商品快照图片字段长度至 2048，兼容高质量/长 URL
ALTER TABLE order_item MODIFY COLUMN product_image VARCHAR(2048) NULL;
