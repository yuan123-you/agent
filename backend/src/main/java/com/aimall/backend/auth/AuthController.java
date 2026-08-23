package com.aimall.backend.auth;

import com.aimall.backend.common.ApiResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

/**
 * 认证接口：/api/v1/auth
 */
@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    @PostMapping("/register")
    public ApiResponse<AuthDtos.LoginResponse> register(@Valid @RequestBody AuthDtos.RegisterRequest req) {
        return registrationResponse(authService.register(req), req, "CUSTOMER");
    }

    @PostMapping("/register/customer")
    public ApiResponse<AuthDtos.LoginResponse> registerCustomer(@Valid @RequestBody AuthDtos.CustomerRegisterRequest req) {
        return registrationResponse(authService.registerCustomer(req), req, "CUSTOMER");
    }

    @PostMapping("/register/merchant")
    public ApiResponse<AuthDtos.LoginResponse> registerMerchant(@Valid @RequestBody AuthDtos.MerchantRegisterRequest req) {
        return registrationResponse(authService.registerMerchant(req), req, "MERCHANT");
    }

    @PostMapping("/login")
    public ApiResponse<AuthDtos.LoginResponse> login(@Valid @RequestBody AuthDtos.LoginRequest req,
                                                     HttpServletRequest request) {
        return ApiResponse.ok(authService.login(req, clientIp(request)));
    }

    @PostMapping("/refresh")
    public ApiResponse<AuthDtos.LoginResponse> refresh(@Valid @RequestBody AuthDtos.RefreshRequest req) {
        String access = authService.refresh(req.getRefreshToken());
        return ApiResponse.ok(new AuthDtos.LoginResponse(access, null, 0, null));
    }

    @PostMapping("/logout")
    public ApiResponse<Void> logout(@RequestHeader(value = "Authorization", required = false) String header) {
        if (header != null && header.startsWith("Bearer ")) {
            authService.logout(header.substring(7));
        }
        return ApiResponse.ok();
    }

    @GetMapping("/me")
    public ApiResponse<AuthDtos.UserVO> me(@AuthenticationPrincipal Long userId) {
        return ApiResponse.ok(authService.me(userId));
    }

    private ApiResponse<AuthDtos.LoginResponse> registrationResponse(Long userId,
                                                                      AuthDtos.CustomerRegisterRequest request,
                                                                      String role) {
        return ApiResponse.ok(new AuthDtos.LoginResponse(null, null, 0,
                new AuthDtos.UserVO(userId, request.getUsername(), request.getNickname(), role, null, null)));
    }

    private String clientIp(HttpServletRequest request) {
        String ip = request.getHeader("X-Forwarded-For");
        return (ip != null && !ip.isBlank()) ? ip.split(",")[0].trim() : request.getRemoteAddr();
    }
}
