package com.aimall.backend.admin;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.common.PageResult;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 用户管理接口：/api/v1/admin/users（仅 ADMIN）
 */
@RestController
@RequestMapping("/api/v1/admin/users")
@RequiredArgsConstructor
public class AdminUserController {

    private final AdminUserService adminUserService;

    @Data
    public static class UserStatusUpdateRequest {
        @NotBlank
        private String status;
    }

    @GetMapping
    public ApiResponse<PageResult<Map<String, Object>>> list(
            @RequestParam(required = false) String role,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long size) {
        return ApiResponse.ok(adminUserService.list(role, keyword, page, size));
    }

    @PostMapping("/agents")
    public ApiResponse<Long> createAgent(@Valid @RequestBody AdminUserService.CreateAgentRequest request) {
        return ApiResponse.ok(adminUserService.createAgent(request));
    }

    @PutMapping("/{id}/status")
    public ApiResponse<Void> updateStatus(@AuthenticationPrincipal Long operatorId, @PathVariable Long id,
                                          @Valid @RequestBody UserStatusUpdateRequest request) {
        adminUserService.updateStatus(operatorId, id, request.getStatus());
        return ApiResponse.ok();
    }
}
