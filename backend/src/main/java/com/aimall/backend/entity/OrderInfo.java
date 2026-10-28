package com.aimall.backend.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("order_info")
public class OrderInfo {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String orderNo;

    private Long userId;

    private BigDecimal totalAmount;

    /** 券优惠金额 */
    private BigDecimal discountAmount;

    /** 使用的用户券ID */
    private Long couponUserId;

    /** PENDING_PAYMENT / PAID / SHIPPED / DELIVERED / CANCELLED / REFUNDED */
    private String status;

    private String receiverName;

    private String receiverPhone;

    private String receiverAddress;

    private String logisticsNo;

    /** 物流公司 */
    private String deliveryCompany;

    /** USER / AI */
    private String source;

    private Long conversationId;

    private LocalDateTime paidAt;

    private LocalDateTime shippedAt;

    private LocalDateTime deliveredAt;

    private LocalDateTime createdAt;

    private LocalDateTime updatedAt;
}
