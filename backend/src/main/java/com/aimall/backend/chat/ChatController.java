package com.aimall.backend.chat;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.common.PageResult;
import com.aimall.backend.entity.Conversation;
import com.aimall.backend.entity.Message;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.HashMap;
import java.util.Map;

/**
 * 对话接口：/api/v1/chat（仅 CUSTOMER）
 */
@RestController
@RequestMapping("/api/v1/chat")
@RequiredArgsConstructor
public class ChatController {

    private final ChatService chatService;

    /** ⭐ 发送消息：SSE 流式响应（token/tool_call/tool_result/error/done） */
    @PostMapping(value = "/messages", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter sendMessage(@AuthenticationPrincipal Long userId,
                                  @Valid @RequestBody ChatDtos.SendMessageRequest req) {
        return chatService.sendMessage(userId, req);
    }

    @PostMapping("/conversations")
    public ApiResponse<Map<String, Object>> createConversation(@AuthenticationPrincipal Long userId) {
        Conversation conv = chatService.createConversation(userId);
        Map<String, Object> data = new HashMap<>();
        data.put("conversationId", conv.getId());
        data.put("convNo", conv.getConvNo());
        data.put("status", conv.getStatus());
        return ApiResponse.ok(data);
    }

    @GetMapping("/conversations")
    public ApiResponse<PageResult<Map<String, Object>>> conversations(
            @AuthenticationPrincipal Long userId,
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long size) {
        return ApiResponse.ok(PageResult.of(chatService.myConversations(userId, page, size), this::toVo));
    }

    @GetMapping("/conversations/{id}")
    public ApiResponse<Map<String, Object>> detail(@AuthenticationPrincipal Long userId,
                                                   @PathVariable Long id) {
        return ApiResponse.ok(toVo(chatService.requireOwned(userId, id)));
    }

    /** 人工服务中买家发消息：落库 USER 消息（客服端轮询可见），不走 AI */
    @PostMapping("/conversations/{id}/human-message")
    public ApiResponse<Void> humanMessage(@AuthenticationPrincipal Long userId,
                                          @PathVariable Long id,
                                          @Valid @RequestBody ChatDtos.HumanMessageRequest req) {
        chatService.humanMessage(userId, id, req.getContent());
        return ApiResponse.ok();
    }

    /** 会话状态（转人工后前端轮询：感知客服接入/服务结束） */
    @GetMapping("/conversations/{id}/status")
    public ApiResponse<Map<String, Object>> status(@AuthenticationPrincipal Long userId,
                                                   @PathVariable Long id) {
        return ApiResponse.ok(chatService.statusVo(userId, id));
    }

    @PostMapping("/conversations/{id}/close")
    public ApiResponse<Void> close(@AuthenticationPrincipal Long userId, @PathVariable Long id) {
        chatService.close(userId, id);
        return ApiResponse.ok();
    }

    @PostMapping("/conversations/{id}/satisfaction")
    public ApiResponse<Void> satisfaction(@AuthenticationPrincipal Long userId, @PathVariable Long id,
                                          @Valid @RequestBody ChatDtos.SatisfactionRequest req) {
        chatService.satisfaction(userId, id, req.getScore());
        return ApiResponse.ok();
    }

    /** 历史消息（分页）；afterId > 0 时为增量轮询（转人工后拉取人工消息） */
    @GetMapping("/conversations/{id}/messages")
    public ApiResponse<?> messages(@AuthenticationPrincipal Long userId,
                                   @PathVariable Long id,
                                   @RequestParam(required = false) Long afterId,
                                   @RequestParam(defaultValue = "1") long page,
                                   @RequestParam(defaultValue = "20") long size) {
        if (afterId != null && afterId > 0) {
            return ApiResponse.ok(chatService.messagesAfter(userId, id, afterId));
        }
        return ApiResponse.ok(PageResult.of(chatService.messages(userId, id, page, size)));
    }

    private Map<String, Object> toVo(Conversation conv) {
        Map<String, Object> vo = new HashMap<>();
        vo.put("conversationId", conv.getId());
        vo.put("convNo", conv.getConvNo());
        vo.put("title", conv.getTitle());
        vo.put("status", conv.getStatus());
        vo.put("summary", conv.getSummary());
        vo.put("satisfaction", conv.getSatisfaction());
        vo.put("messageCount", conv.getMessageCount());
        vo.put("createdAt", conv.getCreatedAt());
        vo.put("updatedAt", conv.getUpdatedAt());
        return vo;
    }
}
