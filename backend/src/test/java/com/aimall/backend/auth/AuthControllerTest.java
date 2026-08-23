package com.aimall.backend.auth;

import com.aimall.backend.common.GlobalExceptionHandler;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class AuthControllerTest {

    private final AuthService authService = mock(AuthService.class);
    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.standaloneSetup(new AuthController(authService))
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();
    }

    @Test
    void registersMerchant() throws Exception {
        when(authService.registerMerchant(any())).thenReturn(12L);

        mockMvc.perform(post("/api/v1/auth/register/merchant").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"seller01\",\"password\":\"123456\",\"nickname\":\"店主\",\"shopName\":\"源选店\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.user.role").value("MERCHANT"));
    }

    @Test
    void rejectsMerchantWithoutShopName() throws Exception {
        mockMvc.perform(post("/api/v1/auth/register/merchant").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"seller01\",\"password\":\"123456\",\"nickname\":\"店主\",\"shopName\":\"\"}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void registersCustomerAndLegacyRouteAsCustomers() throws Exception {
        when(authService.registerCustomer(any())).thenReturn(11L);
        when(authService.register(any())).thenReturn(10L);

        mockMvc.perform(post("/api/v1/auth/register/customer").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"buyer01\",\"password\":\"123456\",\"nickname\":\"买家\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.user.role").value("CUSTOMER"));
        mockMvc.perform(post("/api/v1/auth/register").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"buyer02\",\"password\":\"123456\",\"nickname\":\"买家\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.user.role").value("CUSTOMER"));
    }
}
