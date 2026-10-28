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
    /** Units whose original pre-shipment reservation was released by this case; never purchase quantity. */
    private Integer cancelledFulfillmentQuantity = 0;
    private BigDecimal requestedRefundAmount;
    private String evidenceJson;
    private String historyJson;
    private String returnRecipient;
    private String returnPhone;
    private String returnAddress;
    private String returnCompany;
    private String returnTrackingNo;
    private String exchangeCompany;
    private String exchangeTrackingNo;
    private String decisionReason;
    private BigDecimal approvedRefundAmount;
    private String refundReference;
    private String refundMode;
    private Boolean appealed;
    @com.baomidou.mybatisplus.annotation.TableField(updateStrategy = com.baomidou.mybatisplus.annotation.FieldStrategy.ALWAYS)
    private LocalDateTime completedAt;
    private String status;
    private String currentHandler;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
