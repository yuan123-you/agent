ALTER TABLE agent_action
  ADD COLUMN target_order_id BIGINT NULL COMMENT '取消/售后动作关联的原订单' AFTER order_id,
  ADD KEY idx_agent_action_target_order (target_order_id);

CREATE TABLE after_sale (
  id                      BIGINT         NOT NULL AUTO_INCREMENT,
  after_sale_no           VARCHAR(32)    NOT NULL,
  action_id               VARCHAR(64)    NOT NULL COMMENT '来源 agent_action，保证确认幂等',
  order_id                BIGINT         NOT NULL,
  order_item_id           BIGINT         NOT NULL,
  user_id                 BIGINT         NOT NULL,
  merchant_id             BIGINT         NULL,
  conversation_id         BIGINT         NULL,
  service_type            VARCHAR(24)    NOT NULL COMMENT 'RETURN_REFUND/EXCHANGE/REFUND_ONLY/ISSUE_REPORT',
  issue_category          VARCHAR(16)    NOT NULL COMMENT 'PERSONAL/QUALITY/MERCHANT/PLATFORM',
  reason                  VARCHAR(500)   NOT NULL,
  quantity                INT            NOT NULL,
  requested_refund_amount DECIMAL(10,2)  NOT NULL DEFAULT 0.00,
  status                  VARCHAR(24)    NOT NULL COMMENT 'PENDING_MERCHANT/PENDING_PLATFORM',
  current_handler         VARCHAR(16)    NOT NULL COMMENT 'MERCHANT/PLATFORM',
  created_at              DATETIME(3)    NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at              DATETIME(3)    NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uk_after_sale_no (after_sale_no),
  UNIQUE KEY uk_after_sale_action (action_id),
  KEY idx_after_sale_buyer (user_id, status, created_at),
  KEY idx_after_sale_order_item (order_item_id)
) ENGINE=InnoDB COMMENT='售后申请';
