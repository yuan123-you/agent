package com.aimall.backend.config;

import io.jsonwebtoken.Claims;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;

/**
 * JWT 认证过滤器：校验签名/过期/黑名单，注入 userId 与角色
 */
@Component
@RequiredArgsConstructor
public class JwtAuthFilter extends OncePerRequestFilter {

    private final JwtService jwtService;
    private final StringRedisTemplate redisTemplate;

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        return path.startsWith("/internal/") || path.startsWith("/actuator");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain chain) throws ServletException, IOException {
        String header = request.getHeader("Authorization");
        if (header != null && header.startsWith("Bearer ")) {
            String token = header.substring(7);
            try {
                Claims claims = jwtService.parse(token);
                // 仅接受 access 令牌
                if (!JwtService.TYPE_ACCESS.equals(claims.get(JwtService.CLAIM_TYPE, String.class))) {
                    throw new IllegalArgumentException("not access token");
                }
                // 登出黑名单校验（Redis 不可用时 fail-open）
                try {
                    if (Boolean.TRUE.equals(redisTemplate.hasKey("jwt:bl:" + claims.getId()))) {
                        throw new IllegalArgumentException("token revoked");
                    }
                } catch (IllegalArgumentException e) {
                    throw e;
                } catch (Exception ignore) {
                }
                Long userId = Long.valueOf(claims.getSubject());
                String role = claims.get(JwtService.CLAIM_ROLE, String.class);
                var auth = new UsernamePasswordAuthenticationToken(
                        userId, null, List.of(new SimpleGrantedAuthority("ROLE_" + role)));
                SecurityContextHolder.getContext().setAuthentication(auth);
            } catch (Exception ignore) {
                // 无效令牌：不设置认证信息，由授权规则拦截
                SecurityContextHolder.clearContext();
            }
        }
        chain.doFilter(request, response);
    }
}
