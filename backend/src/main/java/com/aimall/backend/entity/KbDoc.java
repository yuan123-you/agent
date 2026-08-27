package com.aimall.backend.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("kb_doc")
public class KbDoc {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** NULL 表示平台通用文档 */
    private Long productId;

    private String title;

    /** FAQ / INTRO / POLICY */
    private String docType;

    private String fileUrl;

    /** PDF / MD / TXT */
    private String fileFormat;

    /** PENDING / PROCESSING / ACTIVE / DISABLED / FAILED */
    private String status;

    private Integer chunkCount;

    /** 实际写入 Milvus 的向量数（0 = 未向量化 / 关键词降级模式） */
    private Integer vectorCount;

    private String failReason;

    private Integer version;

    private Long createdBy;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;

    @TableLogic
    private Integer deleted;
}
