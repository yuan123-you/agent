-- Application-owned, administrator-only AI turn diagnostics. No hidden model reasoning.
CREATE TABLE ai_trace (
  id BIGINT NOT NULL AUTO_INCREMENT,
  trace_id VARCHAR(64) NOT NULL,
  conversation_id BIGINT NOT NULL,
  user_id BIGINT NOT NULL,
  message_id BIGINT NULL,
  status VARCHAR(16) NOT NULL,
  input_preview VARCHAR(500) NOT NULL,
  model_calls INT NOT NULL DEFAULT 0,
  total_tokens BIGINT NULL,
  stage_count INT NOT NULL DEFAULT 0,
  duration_ms BIGINT NULL,
  detail_json MEDIUMTEXT NULL,
  created_at DATETIME(3) NOT NULL,
  finished_at DATETIME(3) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_ai_trace_id (trace_id),
  KEY idx_ai_trace_created (created_at, id),
  KEY idx_ai_trace_conversation (conversation_id, created_at),
  KEY idx_ai_trace_status (status, created_at)
) ENGINE=InnoDB COMMENT='AI turn execution diagnostics';
