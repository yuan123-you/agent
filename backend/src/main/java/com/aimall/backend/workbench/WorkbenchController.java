package com.aimall.backend.workbench;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.entity.Conversation;
import com.aimall.backend.entity.Message;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 客服工作台接口：/api/v1/workbench（AGENT / ADMIN）
 */
@RestController
@RequestMapping("/api/v1/workbench")
@RequiredArgsConstructor
public class WorkbenchController {

    private final WorkbenchService workbenchService;

    @Data
    public static class AgentMessageRequest {
        private String content;
    }

    /** SLA 看板指标 */
    @GetMapping("/sla")
    public ApiResponse<Map<String, Object>> sla() {
        return ApiResponse.ok(workbenchService.sla());
    }

    @GetMapping("/pending")
    public ApiResponse<List<Map<String, Object>>> pending() {
        return ApiResponse.ok(workbenchService.pending().stream().map(this::toVo).toList());
    }

    @GetMapping("/servicing")
    public ApiResponse<List<Map<String, Object>>> servicing(@AuthenticationPrincipal Long agentId) {
        return ApiResponse.ok(workbenchService.servicing(agentId).stream().map(this::toVo).toList());
    }

    @PostMapping("/conversations/{id}/claim")
    public ApiResponse<Void> claim(@AuthenticationPrincipal Long agentId, @PathVariable Long id) {
        workbenchService.claim(agentId, id);
        return ApiResponse.ok();
    }

    @PostMapping("/conversations/{id}/messages")
    public ApiResponse<Void> sendMessage(@AuthenticationPrincipal Long agentId, @PathVariable Long id,
                                         @RequestBody AgentMessageRequest req) {
        if (req.getContent() == null || req.getContent().isBlank()) {
            return ApiResponse.fail(2001, "消息内容不能为空");
        }
        workbenchService.sendMessage(agentId, id, req.getContent());
        return ApiResponse.ok();
    }

    @PostMapping("/conversations/{id}/finish")
    public ApiResponse<Void> finish(@AuthenticationPrincipal Long agentId, @PathVariable Long id) {
        workbenchService.finish(agentId, id);
        return ApiResponse.ok();
    }

    @GetMapping("/conversations/{id}/messages")
    public ApiResponse<List<Message>> messages(@PathVariable Long id) {
        return ApiResponse.ok(workbenchService.history(id));
    }

    /** 会话状态（客服端轮询：感知买家主动结束会话） */
    @GetMapping("/conversations/{id}/status")
    public ApiResponse<Map<String, Object>> status(@AuthenticationPrincipal Long agentId,
                                                   @PathVariable Long id) {
        return ApiResponse.ok(workbenchService.statusVo(agentId, id));
    }

    private Map<String, Object> toVo(Conversation conv) {
        Map<String, Object> vo = new HashMap<>();
        vo.put("conversationId", conv.getId());
        vo.put("convNo", conv.getConvNo());
        vo.put("userNickname", workbenchService.userNickname(conv.getUserId()));
        vo.put("title", conv.getTitle());
        vo.put("summary", conv.getSummary());
        vo.put("status", conv.getStatus());
        vo.put("messageCount", conv.getMessageCount());
        vo.put("updatedAt", conv.getUpdatedAt());
        return vo;
    }
}
