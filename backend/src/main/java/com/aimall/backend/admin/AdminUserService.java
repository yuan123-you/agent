package com.aimall.backend.admin;

import com.aimall.backend.auth.AuthDtos;
import com.aimall.backend.common.BizException;
import com.aimall.backend.common.PageResult;
import com.aimall.backend.entity.User;
import com.aimall.backend.mapper.UserMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;
import java.util.Set;

@Service
@RequiredArgsConstructor
public class AdminUserService {

    private static final Set<String> LISTABLE_ROLES = Set.of("CUSTOMER", "MERCHANT", "AGENT");
    private static final Set<String> STATUSES = Set.of("ACTIVE", "DISABLED");

    private final UserMapper userMapper;
    private final PasswordEncoder passwordEncoder;

    public Long createAgent(CreateAgentRequest request) {
        String username = request.getUsername().trim();
        Long exists = userMapper.selectCount(new LambdaQueryWrapper<User>()
                .eq(User::getUsername, username));
        if (exists != null && exists > 0) {
            throw new BizException(2005, "用户名已存在");
        }
        User user = new User();
        user.setUsername(username);
        user.setPassword(passwordEncoder.encode(request.getPassword()));
        user.setNickname(request.getNickname().trim());
        user.setPhone(request.getPhone() == null ? null : request.getPhone().trim());
        user.setRole("AGENT");
        user.setStatus("ACTIVE");
        try {
            userMapper.insert(user);
        } catch (DuplicateKeyException exception) {
            throw new BizException(2005, "用户名已存在");
        }
        return user.getId();
    }

    public PageResult<Map<String, Object>> list(String role, String keyword, long page, long size) {
        if (role != null && !role.isBlank() && !LISTABLE_ROLES.contains(role)) {
            throw new BizException(2001, "角色参数不正确");
        }
        Page<User> result = userMapper.selectPage(new Page<>(page, size),
                new LambdaQueryWrapper<User>()
                        .ne(User::getRole, "ADMIN")
                        .eq(role != null && !role.isBlank(), User::getRole, role)
                        .and(keyword != null && !keyword.isBlank(),
                                w -> w.like(User::getUsername, keyword).or().like(User::getNickname, keyword))
                        .orderByDesc(User::getId));
        return PageResult.of(result, this::toVo);
    }

    public void updateStatus(Long operatorId, Long targetId, String status) {
        if (!STATUSES.contains(status)) {
            throw new BizException(2001, "状态参数不正确");
        }
        User user = userMapper.selectById(targetId);
        if (user == null) {
            throw new BizException(2002, "用户不存在");
        }
        if (user.getId().equals(operatorId)) {
            throw new BizException(2004, "不能修改自己的账号");
        }
        if ("ADMIN".equals(user.getRole())) {
            throw new BizException(2004, "不能修改管理员账号");
        }
        User update = new User();
        update.setId(targetId);
        update.setStatus(status);
        userMapper.updateById(update);
    }

    private Map<String, Object> toVo(User user) {
        Map<String, Object> vo = new HashMap<>();
        vo.put("userId", user.getId());
        vo.put("username", user.getUsername());
        vo.put("nickname", user.getNickname());
        vo.put("role", user.getRole());
        vo.put("status", user.getStatus());
        vo.put("phone", maskPhone(user.getPhone()));
        vo.put("createdAt", user.getCreatedAt());
        return vo;
    }

    private String maskPhone(String phone) {
        if (phone == null) {
            return "";
        }
        return phone.length() >= 7 ? phone.substring(0, 3) + "****" + phone.substring(phone.length() - 4) : phone;
    }

    @Data
    @EqualsAndHashCode(callSuper = true)
    public static class CreateAgentRequest extends AuthDtos.CustomerRegisterRequest {
    }
}
