package com.aimall.backend.admin;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.common.BizException;
import com.aimall.backend.common.PageResult;
import com.aimall.backend.entity.User;
import com.aimall.backend.mapper.UserMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;
import java.util.Set;

/**
 * 用户管理接口：/api/v1/admin/users（仅 ADMIN）
 */
@RestController
@RequestMapping("/api/v1/admin/users")
@RequiredArgsConstructor
public class AdminUserController {

    private static final Set<String> ASSIGNABLE_ROLES = Set.of("AGENT", "CUSTOMER");

    private final UserMapper userMapper;

    @Data
    public static class UserUpdateRequest {
        private String status;
        private String role;
    }

    @GetMapping
    public ApiResponse<PageResult<Map<String, Object>>> list(
            @RequestParam(required = false) String role,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long size) {
        Page<User> result = userMapper.selectPage(new Page<>(page, size),
                new LambdaQueryWrapper<User>()
                        .eq(role != null && !role.isBlank(), User::getRole, role)
                        .and(keyword != null && !keyword.isBlank(),
                                w -> w.like(User::getUsername, keyword).or().like(User::getNickname, keyword))
                        .orderByDesc(User::getId));
        return ApiResponse.ok(PageResult.of(result, this::toVo));
    }

    @PutMapping("/{id}")
    public ApiResponse<Void> update(@AuthenticationPrincipal Long operatorId, @PathVariable Long id,
                                    @RequestBody UserUpdateRequest req) {
        User user = userMapper.selectById(id);
        if (user == null) {
            throw new BizException(2002, "用户不存在");
        }
        if (user.getId().equals(operatorId)) {
            throw new BizException(2004, "不能修改自己的账号");
        }
        if ("ADMIN".equals(user.getRole())) {
            throw new BizException(2004, "不能修改管理员账号");
        }
        User upd = new User();
        upd.setId(id);
        if (req.getStatus() != null && Set.of("ACTIVE", "DISABLED").contains(req.getStatus())) {
            upd.setStatus(req.getStatus());
        }
        if (req.getRole() != null && ASSIGNABLE_ROLES.contains(req.getRole())) {
            upd.setRole(req.getRole());
        }
        userMapper.updateById(upd);
        return ApiResponse.ok();
    }

    private Map<String, Object> toVo(User u) {
        Map<String, Object> vo = new HashMap<>();
        vo.put("userId", u.getId());
        vo.put("username", u.getUsername());
        vo.put("nickname", u.getNickname());
        vo.put("role", u.getRole());
        vo.put("status", u.getStatus());
        vo.put("phone", u.getPhone() == null ? "" :
                (u.getPhone().length() >= 7 ? u.getPhone().substring(0, 3) + "****" + u.getPhone().substring(u.getPhone().length() - 4) : u.getPhone()));
        vo.put("createdAt", u.getCreatedAt());
        return vo;
    }
}
