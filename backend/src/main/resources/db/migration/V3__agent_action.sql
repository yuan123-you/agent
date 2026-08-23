CREATE TABLE agent_action (
  action_id       VARCHAR(64)    NOT NULL,
  user_id         BIGINT         NOT NULL,
  conversation_id BIGINT         NOT NULL,
  type            VARCHAR(32)    NOT NULL,
  payload         JSON           NOT NULL COMMENT 'prepare 时的完整请求快照',
  amount          DECIMAL(10,2)  NOT NULL COMMENT 'prepare 金额；confirm 时更新为最新金额',
  status          VARCHAR(16)    NOT NULL DEFAULT 'PENDING' COMMENT 'PENDING/CONFIRMED/EXPIRED/CANCELLED',
  expires_at      DATETIME(3)    NOT NULL,
  order_id        BIGINT         NULL COMMENT '确认后生成的订单，用于数据库级幂等',
  created_at      DATETIME(3)    NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at      DATETIME(3)    NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (action_id),
  UNIQUE KEY uk_agent_action_order (order_id),
  KEY idx_agent_action_owner (user_id, conversation_id),
  KEY idx_agent_action_expiry (status, expires_at)
) ENGINE=InnoDB COMMENT='AI 高风险操作确认记录';
