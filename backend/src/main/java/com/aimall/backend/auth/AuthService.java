package com.aimall.backend.auth;

import com.aimall.backend.common.BizException;
import com.aimall.backend.config.JwtService;
import com.aimall.backend.entity.User;
import com.aimall.backend.mapper.UserMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import io.jsonwebtoken.Claims;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.Date;
import java.util.concurrent.TimeUnit;

/**
 * 认证服务：注册/登录/刷新/登出/当前用户
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserMapper userMapper;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;
    private final StringRedisTemplate redisTemplate;
    private final RegistrationService registrationService;

    public Long register(AuthDtos.RegisterRequest req) {
        return registrationService.registerCustomer(req);
    }

    public Long registerCustomer(AuthDtos.CustomerRegisterRequest req) {
        return registrationService.registerCustomer(req);
    }

    public Long registerMerchant(AuthDtos.MerchantRegisterRequest req) {
        return registrationService.registerMerchant(req);
    }
    public AuthDtos.LoginResponse login(AuthDtos.LoginRequest req, String ip) {
        // 登录防爆破：同 IP 每分钟 5 次
        try {
            String key = "login:rl:" + ip;
            Long n = redisTemplate.opsForValue().increment(key);
            if (n != null && n == 1) {
                redisTemplate.expire(key, 60, TimeUnit.SECONDS);
            }
            if (n != null && n > 5) {
                throw new BizException(1005, "尝试过于频繁，请1分钟后再试");
            }
        } catch (BizException e) {
            throw e;
        } catch (Exception ignore) {
            // Redis 不可用时 fail-open
        }

        User user = userMapper.selectOne(new LambdaQueryWrapper<User>()
                .eq(User::getUsername, req.getUsername()));
        // 模糊提示防枚举
        if (user == null || !passwordEncoder.matches(req.getPassword(), user.getPassword())) {
            throw new BizException(1001, "用户名或密码错误");
        }
        if (!"ACTIVE".equals(user.getStatus())) {
            throw new BizException(1002, "账号已禁用");
        }
        User update = new User();
        update.setId(user.getId());
        update.setLastLoginAt(java.time.LocalDateTime.now());
        userMapper.updateById(update);

        String access = jwtService.createAccessToken(user.getId(), user.getRole());
        String refresh = jwtService.createRefreshToken(user.getId(), user.getRole());
        return new AuthDtos.LoginResponse(access, refresh, 7200, toVO(user));
    }

    public String refresh(String refreshToken) {
        Claims claims;
        try {
            claims = jwtService.parse(refreshToken);
        } catch (Exception e) {
            throw new BizException(1004, "刷新令牌无效或已过期");
        }
        if (!JwtService.TYPE_REFRESH.equals(claims.get(JwtService.CLAIM_TYPE, String.class))) {
            throw new BizException(1004, "刷新令牌无效");
        }
        Long userId = Long.valueOf(claims.getSubject());
        User user = userMapper.selectById(userId);
        if (user == null || !"ACTIVE".equals(user.getStatus())) {
            throw new BizException(1004, "刷新令牌无效");
        }
        return jwtService.createAccessToken(user.getId(), user.getRole());
    }

    public void logout(String token) {
        try {
            Claims claims = jwtService.parse(token);
            long ttlMs = claims.getExpiration().getTime() - System.currentTimeMillis();
            if (ttlMs > 0) {
                redisTemplate.opsForValue().set("jwt:bl:" + claims.getId(), "1",
                        Duration.ofMillis(ttlMs));
            }
        } catch (Exception ignore) {
            // 无效令牌登出：直接忽略
        }
    }

    public AuthDtos.UserVO me(Long userId) {
        User user = userMapper.selectById(userId);
        if (user == null) {
            throw new BizException(2002, "用户不存在");
        }
        return toVO(user);
    }

    private AuthDtos.UserVO toVO(User u) {
        return new AuthDtos.UserVO(u.getId(), u.getUsername(), u.getNickname(),
                u.getRole(), maskPhone(u.getPhone()), u.getEmail());
    }

    private String maskPhone(String phone) {
        if (phone == null || phone.length() < 7) {
            return phone;
        }
        return phone.substring(0, 3) + "****" + phone.substring(phone.length() - 4);
    }
}
