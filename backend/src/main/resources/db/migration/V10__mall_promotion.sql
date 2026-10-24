-- ============================================================================
-- V10: 营销中心（对标 macrozheng/mall 的 SMS 模块精简版）
--   mall_coupon  <- sms_coupon（满减券模板）
--   user_coupon  <- sms_coupon_history（用户持券，每人每券限领一张）
--   mall_seckill <- sms_seckill_*（商品级秒杀活动，时间窗 + 专属价 + 专属库存）
-- ============================================================================

-- ---------- 优惠券模板 ----------
CREATE TABLE mall_coupon (
  id             BIGINT        NOT NULL AUTO_INCREMENT COMMENT '券ID',
  name           VARCHAR(64)   NOT NULL COMMENT '券名称',
  -- 满减类型（对标 sms_coupon 的 money/min_amount；折扣券后续扩展）
  discount_value DECIMAL(10,2) NOT NULL COMMENT '优惠金额',
  min_amount     DECIMAL(10,2) NOT NULL DEFAULT 0 COMMENT '使用门槛(订单满X可用,0=无门槛)',
  total_count    INT           NOT NULL DEFAULT 0 COMMENT '发行总量',
  received_count INT           NOT NULL DEFAULT 0 COMMENT '已领取数量',
  per_limit      INT           NOT NULL DEFAULT 1 COMMENT '每人限领(当前版本固定1)',
  status         VARCHAR(16)   NOT NULL DEFAULT 'ENABLE' COMMENT 'ENABLE/DISABLE',
  start_time     DATETIME(3)   NULL COMMENT '领取开始时间(NULL=立即)',
  end_time       DATETIME(3)   NULL COMMENT '领取结束时间(NULL=长期)',
  valid_days     INT           NOT NULL DEFAULT 7 COMMENT '领券后有效天数',
  created_at     DATETIME(3)   NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at     DATETIME(3)   NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  deleted        TINYINT       NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  KEY idx_status (status, end_time)
) ENGINE=InnoDB COMMENT='优惠券模板表(对标mall sms_coupon)';

-- ---------- 用户持券 ----------
CREATE TABLE user_coupon (
  id           BIGINT      NOT NULL AUTO_INCREMENT COMMENT '持券ID',
  coupon_id    BIGINT      NOT NULL COMMENT '券模板ID',
  user_id      BIGINT      NOT NULL COMMENT '用户ID',
  status       VARCHAR(16) NOT NULL DEFAULT 'UNUSED' COMMENT 'UNUSED/USED/EXPIRED',
  received_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '领取时间',
  expire_at    DATETIME(3) NOT NULL COMMENT '过期时间(领取时间+valid_days)',
  used_order_id BIGINT     NULL COMMENT '核销订单ID',
  used_at      DATETIME(3) NULL COMMENT '核销时间',
  created_at   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  deleted      TINYINT     NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uk_coupon_user (coupon_id, user_id),  -- 每人每券限领一张（与 per_limit=1 对应）
  KEY idx_user_status (user_id, status, expire_at)
) ENGINE=InnoDB COMMENT='用户优惠券表(对标mall sms_coupon_history)';

-- ---------- 商品秒杀活动 ----------
CREATE TABLE mall_seckill (
  id            BIGINT        NOT NULL AUTO_INCREMENT COMMENT '活动ID',
  product_id    BIGINT        NOT NULL COMMENT '商品ID',
  seckill_price DECIMAL(10,2) NOT NULL COMMENT '秒杀价',
  seckill_stock INT           NOT NULL DEFAULT 0 COMMENT '秒杀专属库存',
  seckill_limit INT           NOT NULL DEFAULT 1 COMMENT '每人限购件数',
  start_time    DATETIME(3)   NOT NULL COMMENT '开始时间',
  end_time      DATETIME(3)   NOT NULL COMMENT '结束时间',
  status        VARCHAR(16)   NOT NULL DEFAULT 'ENABLE' COMMENT 'ENABLE/DISABLE',
  version       INT           NOT NULL DEFAULT 0 COMMENT '乐观锁版本',
  created_at    DATETIME(3)   NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at    DATETIME(3)   NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  deleted       TINYINT       NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  KEY idx_product (product_id),
  KEY idx_window (status, start_time, end_time)
) ENGINE=InnoDB COMMENT='商品秒杀活动表(对标mall sms_seckill)';

-- ---------- 订单记录优惠与秒杀（取消回补依据） ----------
ALTER TABLE order_info
  ADD COLUMN discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0 COMMENT '券优惠金额' AFTER total_amount,
  ADD COLUMN coupon_user_id  BIGINT       NULL COMMENT '使用的用户券ID' AFTER discount_amount;

ALTER TABLE order_item
  ADD COLUMN seckill_id BIGINT NULL COMMENT '秒杀活动ID(NULL=非秒杀下单)' AFTER sku_id;
