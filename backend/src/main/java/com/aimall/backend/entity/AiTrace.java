package com.aimall.backend.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("ai_trace")
public class AiTrace {
    @TableId(type = IdType.AUTO)
    private Long id;
    private String traceId;
    private Long conversationId;
    private Long userId;
    private Long messageId;
    private String status;
    private String inputPreview;
    private Integer modelCalls;
    private Long totalTokens;
    private Integer stageCount;
    private Long durationMs;
    private String detailJson;
    private LocalDateTime createdAt;
    private LocalDateTime finishedAt;
}
