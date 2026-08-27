package com.aimall.backend.entity;

import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDateTime;

@Data
@TableName("agent_action")
public class AgentAction {
    @TableId
    private String actionId;
    private Long userId;
    private Long conversationId;
    private String type;
    private String payload;
    private BigDecimal amount;
    private String status;
    private Instant expiresAt;
    private Long orderId;
    private Long targetOrderId;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
