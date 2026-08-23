package com.aimall.backend.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("kb_chunk")
public class KbChunk {

    /** 与 Milvus 主键一致 */
    @TableId(type = IdType.AUTO)
    private Long id;

    private Long docId;

    private Long productId;

    private String docType;

    private Integer docVersion;

    private Integer chunkIndex;

    private String content;

    private Integer tokenCount;

    private LocalDateTime createdAt;
}
