package com.aimall.backend.auth;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 认证模块 DTO
 */
public class AuthDtos {

    @Data
    public static class CustomerRegisterRequest {
        @NotBlank
        @Pattern(regexp = "^\\w{4,32}$", message = "用户名须为4~32位字母数字下划线")
        private String username;
        @NotBlank
        @Size(min = 6, max = 32, message = "密码长度6~32位")
        private String password;
        @NotBlank
        @Size(max = 32)
        private String nickname;
        @Pattern(regexp = "^$|1\\d{10}$", message = "手机号格式不正确")
        private String phone;
    }

    /** 兼容原有买家注册接口。 */
    @Data
    @EqualsAndHashCode(callSuper = true)
    public static class RegisterRequest extends CustomerRegisterRequest {
    }

    @Data
    @EqualsAndHashCode(callSuper = true)
    public static class MerchantRegisterRequest extends CustomerRegisterRequest {
        @NotBlank
        @Size(max = 64)
        private String shopName;
    }

    @Data
    public static class LoginRequest {
        @NotBlank
        private String username;
        @NotBlank
        private String password;
    }

    @Data
    public static class RefreshRequest {
        @NotBlank
        private String refreshToken;
    }

    public record LoginResponse(String accessToken, String refreshToken, long expiresIn, UserVO user) {
    }

    public record UserVO(Long userId, String username, String nickname, String role, String phone, String email) {
    }
}
