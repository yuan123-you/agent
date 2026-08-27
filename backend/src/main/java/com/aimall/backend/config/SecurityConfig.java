package com.aimall.backend.config;

import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.util.List;

/**
 * 安全配置：JWT 无状态认证 + RBAC 三角色（ADMIN/AGENT/CUSTOMER）+ 内部令牌
 */
@Configuration
@EnableWebSecurity
@RequiredArgsConstructor
public class SecurityConfig {

    private final JwtAuthFilter jwtAuthFilter;
    private final InternalAuthFilter internalAuthFilter;

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http.csrf(csrf -> csrf.disable())
                .cors(cors -> cors.configurationSource(corsSource()))
                .sessionManagement(sm -> sm.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(auth -> auth
                        // ASYNC dispatch 放行：SseEmitter.complete() 会触发请求重入过滤链（ASYNC dispatch），
                        // 此时 SecurityContext 不随线程传播，若被授权规则拒绝会导致响应异常中断、
                        // chunked 终止块丢失（前端 ERR_INCOMPLETE_CHUNKED_ENCODING）。首次请求已完成鉴权，此处放行安全。
                        .dispatcherTypeMatchers(jakarta.servlet.DispatcherType.ASYNC).permitAll()
                        // 开放接口
                        .requestMatchers("/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/register/customer",
                                "/api/v1/auth/register/merchant", "/api/v1/auth/refresh").permitAll()
                        .requestMatchers("/actuator/**", "/api/v1/product-images/**").permitAll()
                        // 商品浏览（列表/详情/分类）：游客公开可见
                        .requestMatchers("/api/v1/products/**").permitAll()
                        .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
                        // 内部接口：仅 AI 服务（内部令牌）
                        .requestMatchers("/internal/**").hasRole("INTERNAL")
                        // 管理后台：仅 ADMIN
                        .requestMatchers("/api/v1/admin/**").hasRole("ADMIN")
                        // 商家端：仅 MERCHANT
                        .requestMatchers("/api/v1/merchant/**").hasRole("MERCHANT")
                        // 客服工作台：AGENT / ADMIN
                        .requestMatchers("/api/v1/workbench/**").hasAnyRole("AGENT", "ADMIN")
                        // AI 对话：仅 CUSTOMER
                        .requestMatchers("/api/v1/chat/**").hasRole("CUSTOMER")
                        // 其余（商品/订单/通知等）：登录即可
                        .anyRequest().authenticated()
                )
                // 未认证/无权限：返回统一 JSON 错误体（而非默认空响应）
                .exceptionHandling(e -> e
                        .authenticationEntryPoint((req, res, ex) -> {
                            res.setStatus(401);
                            res.setContentType("application/json;charset=UTF-8");
                            res.getWriter().write("{\"code\":1003,\"message\":\"令牌无效或未登录\"}");
                        })
                        .accessDeniedHandler((req, res, ex) -> {
                            res.setStatus(403);
                            res.setContentType("application/json;charset=UTF-8");
                            res.getWriter().write("{\"code\":2003,\"message\":\"无权访问该资源\"}");
                        })
                )
                .addFilterBefore(internalAuthFilter, UsernamePasswordAuthenticationFilter.class)
                .addFilterBefore(jwtAuthFilter, UsernamePasswordAuthenticationFilter.class);
        return http.build();
    }

    private CorsConfigurationSource corsSource() {
        CorsConfiguration config = new CorsConfiguration();
        config.setAllowedOriginPatterns(List.of("*"));
        config.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "OPTIONS"));
        config.setAllowedHeaders(List.of("*"));
        config.setAllowCredentials(true);
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", config);
        return source;
    }
}
