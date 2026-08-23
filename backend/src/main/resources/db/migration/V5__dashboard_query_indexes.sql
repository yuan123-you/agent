CREATE INDEX idx_order_created_at ON order_info (created_at);
CREATE INDEX idx_conversation_created_deleted ON conversation (created_at, deleted);
CREATE INDEX idx_product_status_deleted ON product (status, deleted);
