package com.aimall.backend.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 用户优惠券（对标 mall sms_coupon_history）。
 * 每人每券限领一张（uk_coupon_user）。
 */
@Data
@TableName("user_coupon")
public class UserCoupon {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long couponId;

    private Long userId;

    /** UNUSED / USED / EXPIRED */
    private String status;

    private LocalDateTime receivedAt;

    /** 过期时间(领取时间+券有效天数) */
    private LocalDateTime expireAt;

    /** 核销订单ID */
    private Long usedOrderId;

    private LocalDateTime usedAt;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;

    @TableLogic
    private Integer deleted;
}
