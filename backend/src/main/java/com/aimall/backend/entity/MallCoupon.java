package com.aimall.backend.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 优惠券模板（对标 mall sms_coupon 精简版：满减券）。
 */
@Data
@TableName("mall_coupon")
public class MallCoupon {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String name;

    /** 优惠金额 */
    private BigDecimal discountValue;

    /** 使用门槛(订单满X可用,0=无门槛) */
    private BigDecimal minAmount;

    /** 发行总量 */
    private Integer totalCount;

    /** 已领取数量 */
    private Integer receivedCount;

    /** 每人限领(当前版本固定1) */
    private Integer perLimit;

    /** ENABLE / DISABLE */
    private String status;

    /** 领取开始时间(NULL=立即) */
    private LocalDateTime startTime;

    /** 领取结束时间(NULL=长期) */
    private LocalDateTime endTime;

    /** 领券后有效天数 */
    private Integer validDays;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;

    @TableLogic
    private Integer deleted;
}
