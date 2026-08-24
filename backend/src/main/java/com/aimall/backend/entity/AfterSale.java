package com.aimall.backend.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("after_sale")
public class AfterSale {
    @TableId(type = IdType.AUTO)
    private Long id;
    private String afterSaleNo;
    private String actionId;
    private Long orderId;
    private Long orderItemId;
    private Long userId;
    private Long merchantId;
    private Long conversationId;
    private String serviceType;
    private String issueCategory;
    private String reason;
    private Integer quantity;
    private BigDecimal requestedRefundAmount;
    private String status;
    private String currentHandler;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
