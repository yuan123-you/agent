package com.aimall.backend.chat;

import lombok.Data;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

/**
 * 对话模块 DTO
 */
public class ChatDtos {

    @Data
    public static class SendMessageRequest {
        @NotNull
        private Long conversationId;
        @NotBlank
        @Size(max = 4000, message = "消息长度不能超过4000字符")
        private String content;
        /** 联网搜索开关（AI 优先搜索网络内容） */
        private Boolean webSearchEnabled;
    }

    @Data
    public static class HumanMessageRequest {
        @NotBlank
        @Size(max = 4000, message = "消息长度不能超过4000字符")
        private String content;
    }

    @Data
    public static class SatisfactionRequest {
        @NotNull
        @jakarta.validation.constraints.Min(1)
        @jakarta.validation.constraints.Max(5)
        private Integer score;
    }
}
