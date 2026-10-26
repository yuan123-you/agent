package com.aimall.backend.internal;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.common.ExactNumberDeserializers;
import com.aimall.backend.chat.UserMemoryService;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 内部长期记忆接口：/internal/memory/**（仅 AI 服务，X-Internal-Token 鉴权）
 */
@RestController
@RequestMapping("/internal/memory")
@RequiredArgsConstructor
public class InternalMemoryController {

    private final UserMemoryService userMemoryService;

    @Data
    public static class MemoryUpsertBody {
        @JsonDeserialize(using = ExactNumberDeserializers.LongValue.class)
        private Long userId;
        private List<Map<String, String>> memories;
    }

    /** 查询用户长期记忆 */
    @GetMapping
    public ApiResponse<List<Map<String, String>>> getMemories(@RequestParam Long userId) {
        return ApiResponse.ok(userMemoryService.getMemoriesDto(userId));
    }

    /** 批量写入或更新长期记忆 */
    @PostMapping("/upsert")
    public ApiResponse<Map<String, Object>> upsertMemories(@RequestBody MemoryUpsertBody body) {
        if (body.getUserId() != null && body.getMemories() != null) {
            userMemoryService.batchUpsert(body.getUserId(), body.getMemories());
        }
        return ApiResponse.ok(Map.of("success", true));
    }

    /** 清空用户长期记忆 */
    @DeleteMapping
    public ApiResponse<Map<String, Object>> clearMemories(@RequestParam Long userId) {
        userMemoryService.clearMemories(userId);
        return ApiResponse.ok(Map.of("success", true));
    }
}
