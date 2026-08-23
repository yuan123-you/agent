package com.aimall.backend.admin;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.method.annotation.AuthenticationPrincipalArgumentResolver;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class AdminUserControllerTest {

    private final AdminUserService adminUserService = mock(AdminUserService.class);
    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        SecurityContextHolder.getContext().setAuthentication(new UsernamePasswordAuthenticationToken(1L, null));
        mockMvc = MockMvcBuilders.standaloneSetup(new AdminUserController(adminUserService))
                .setCustomArgumentResolvers(new AuthenticationPrincipalArgumentResolver())
                .build();
    }

    @Test
    void createsAgentThroughDedicatedRoute() throws Exception {
        when(adminUserService.createAgent(any())).thenReturn(12L);

        mockMvc.perform(post("/api/v1/admin/users/agents").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"agent02\",\"password\":\"123456\",\"nickname\":\"客服\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data").value(12));
    }

    @Test
    void updatesStatusThroughDedicatedRoute() throws Exception {
        mockMvc.perform(put("/api/v1/admin/users/22/status").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"status\":\"DISABLED\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0));

        verify(adminUserService).updateStatus(eq(1L), eq(22L), eq("DISABLED"));
    }

    @Test
    void oldRoleOnlyUpdateRouteCannotMutateRole() throws Exception {
        mockMvc.perform(put("/api/v1/admin/users/22").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"role\":\"AGENT\"}"))
                .andExpect(status().isNotFound());

        verifyNoInteractions(adminUserService);
    }
}
