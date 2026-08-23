package com.aimall.backend.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("message")
public class Message {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long conversationId;

    /** USER / AI / AGENT / SYSTEM */
    private String role;

    /** 正文（AI 消息含 mall:// 链接原文） */
    private String content;

    /** 工具调用记录 JSON：[{tool,args,result,elapsed_ms}] */
    private String toolCalls;

    /** {prompt_tokens, completion_tokens} JSON */
    private String tokenUsage;

    private String imageUrl;

    private Integer latencyMs;

    /** SUCCESS / FAILED / DEGRADED */
    private String status;

    private LocalDateTime createdAt;
}
