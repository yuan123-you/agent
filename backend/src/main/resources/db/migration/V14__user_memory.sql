-- 用户长期记忆表（支持称谓人设、消费偏好与情景事实跨会话持久化）
CREATE TABLE IF NOT EXISTS user_memory (
  id           BIGINT       NOT NULL AUTO_INCREMENT COMMENT '记忆ID',
  user_id      BIGINT       NOT NULL COMMENT '买家用户ID',
  category     VARCHAR(32)  NOT NULL COMMENT '分类: IDENTITY/PREFERENCE/FACT',
  memory_key   VARCHAR(64)  NOT NULL COMMENT '记忆键名',
  memory_value TEXT         NOT NULL COMMENT '记忆内容',
  created_at   DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at   DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  deleted      TINYINT      NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uk_user_cat_key (user_id, category, memory_key),
  KEY idx_user_updated (user_id, updated_at)
) ENGINE=InnoDB COMMENT='买家用户长期记忆表';
