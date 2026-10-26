package com.aimall.backend.config;

import com.aimall.backend.entity.User;
import com.aimall.backend.mapper.UserMapper;
import jakarta.servlet.Filter;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.test.context.junit.jupiter.SpringJUnitConfig;
import org.springframework.test.context.web.WebAppConfiguration;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.context.WebApplicationContext;

import java.util.Map;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringJUnitConfig(JwtAuthFilterSecurityTest.Config.class)
@WebAppConfiguration
class JwtAuthFilterSecurityTest {
    @Configuration
    @Import({SecurityFilterTestConfig.class, IdentityEndpoint.class})
    static class Config {}

    @RestController
    static class IdentityEndpoint {
        @GetMapping({"/api/v1/chat/security-probe", "/api/v1/merchant/security-probe",
                "/api/v1/workbench/security-probe", "/api/v1/admin/security-probe"})
        Map<String, Long> identity(@AuthenticationPrincipal Long userId) {
            return Map.of("userId", userId);
        }
    }

    @Autowired WebApplicationContext context;
    @Autowired @Qualifier("springSecurityFilterChain") Filter securityFilterChain;
    @Autowired JwtService jwtService;
    @Autowired UserMapper userMapper;
    @Autowired StringRedisTemplate redis;
    private MockMvc mvc;
    private User user;

    @BeforeEach
    void setUp() {
        reset(userMapper, redis);
        user = new User();
        user.setId(42L);
        user.setRole("AGENT");
        user.setStatus("ACTIVE");
        user.setDeleted(0);
        when(userMapper.selectById(42L)).thenReturn(user);
        mvc = MockMvcBuilders.webAppContextSetup(context).addFilters(securityFilterChain).build();
    }

    @ParameterizedTest
    @ValueSource(strings = {"CUSTOMER", "MERCHANT", "AGENT", "ADMIN"})
    void activeAccountRetainsItsRoleAndPrincipal(String role) throws Exception {
        user.setRole(role);
        mvc.perform(get(endpoint(role)).header("Authorization", bearer(jwtService.createAccessToken(42L, role))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.userId").value(42));
    }

    @ParameterizedTest
    @ValueSource(strings = {"CUSTOMER", "MERCHANT", "AGENT", "ADMIN"})
    void disablingAccountRejectsTheSamePreviouslyAcceptedAccessToken(String role) throws Exception {
        user.setRole(role);
        String authorization = bearer(jwtService.createAccessToken(42L, role));
        mvc.perform(get(endpoint(role)).header("Authorization", authorization)).andExpect(status().isOk());

        user.setStatus("DISABLED");

        mvc.perform(get(endpoint(role)).header("Authorization", authorization))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(1003))
                .andExpect(jsonPath("$.userId").doesNotExist());
    }

    @Test
    void deletedAccountCannotUseAnUnexpiredAccessToken() throws Exception {
        // UserMapper.selectById excludes logically deleted rows through MyBatis-Plus @TableLogic.
        when(userMapper.selectById(42L)).thenReturn(null);
        expectUnauthorized(jwtService.createAccessToken(42L, "AGENT"));
    }

    @Test
    void refreshTokenCannotAuthenticateAnActiveAccount() throws Exception {
        expectUnauthorized(jwtService.createRefreshToken(42L, "AGENT"));
    }

    @Test
    void revokedAccessTokenStillCannotAuthenticateAnActiveAccount() throws Exception {
        String token = jwtService.createAccessToken(42L, "AGENT");
        when(redis.hasKey("jwt:bl:" + jwtService.parse(token).getId())).thenReturn(true);
        expectUnauthorized(token);
    }

    @Test
    void redisOutageStillAllowsAnActiveAccountAsBefore() throws Exception {
        when(redis.hasKey(anyString())).thenThrow(new IllegalStateException("Redis unavailable"));
        mvc.perform(get(endpoint("AGENT")).header("Authorization", bearer(jwtService.createAccessToken(42L, "AGENT"))))
                .andExpect(status().isOk()).andExpect(jsonPath("$.userId").value(42));
    }

    @Test
    void redisOutageDoesNotBypassDisabledAccountCheck() throws Exception {
        user.setStatus("DISABLED");
        when(redis.hasKey(anyString())).thenThrow(new IllegalStateException("Redis unavailable"));
        expectUnauthorized(jwtService.createAccessToken(42L, "AGENT"));
    }

    @Test
    void accountLookupFailureFailsClosed() throws Exception {
        when(userMapper.selectById(42L)).thenThrow(new IllegalStateException("Database unavailable"));
        expectUnauthorized(jwtService.createAccessToken(42L, "AGENT"));
    }

    @Test
    void unknownAccountStatusCannotAuthenticate() throws Exception {
        user.setStatus("PENDING");
        expectUnauthorized(jwtService.createAccessToken(42L, "AGENT"));
    }

    @Test
    void missingAccountStatusCannotAuthenticate() throws Exception {
        user.setStatus(null);
        expectUnauthorized(jwtService.createAccessToken(42L, "AGENT"));
    }

    @Test
    void invalidSignatureStillCannotAuthenticateAnActiveAccount() throws Exception {
        AppProperties otherProps = new AppProperties();
        otherProps.getJwt().setSecret("different-synthetic-signing-key-ABCDEFGHIJKLMNOPQRSTUVWXYZ-0123456789-not-for-deployment");
        expectUnauthorized(new JwtService(otherProps).createAccessToken(42L, "AGENT"));
    }

    @Test
    void expiredAccessTokenStillCannotAuthenticateAnActiveAccount() throws Exception {
        AppProperties props = new AppProperties();
        props.getJwt().setSecret(context.getBean(AppProperties.class).getJwt().getSecret());
        props.getJwt().setAccessTtlMinutes(-1);
        expectUnauthorized(new JwtService(props).createAccessToken(42L, "AGENT"));
    }

    private void expectUnauthorized(String token) throws Exception {
        mvc.perform(get(endpoint("AGENT")).header("Authorization", bearer(token)))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(1003))
                .andExpect(jsonPath("$.userId").doesNotExist());
    }

    private static String bearer(String token) {
        return "Bearer " + token;
    }

    private static String endpoint(String role) {
        return switch (role) {
            case "CUSTOMER" -> "/api/v1/chat/security-probe";
            case "MERCHANT" -> "/api/v1/merchant/security-probe";
            case "ADMIN" -> "/api/v1/admin/security-probe";
            default -> "/api/v1/workbench/security-probe";
        };
    }
}
