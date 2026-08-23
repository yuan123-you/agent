package com.aimall.backend.admin;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class AdminDashboardControllerTest {

    private final AdminDashboardService service = mock(AdminDashboardService.class);
    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.standaloneSetup(new AdminDashboardController(service)).build();
    }

    @Test
    void returnsDashboardThroughDedicatedAdminRoute() throws Exception {
        when(service.dashboard()).thenReturn(new AdminDashboardService.DashboardVO(
                new AdminDashboardService.SummaryVO(10, 2, 3, 4, new BigDecimal("99.00"), 5),
                List.of(new AdminDashboardService.OrderTrendPoint(LocalDate.of(2026, 8, 23), 4, new BigDecimal("99.00"))),
                List.of(), new AdminDashboardService.OperationsVO(2),
                new AdminDashboardService.AiQualityVO(100, 50, 20, 1234), List.of(), List.of()));

        mockMvc.perform(get("/api/v1/admin/dashboard"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.summary.userCount").value(10))
                .andExpect(jsonPath("$.data.orderTrend").isArray())
                .andExpect(jsonPath("$.data.operations.waitingHumanConversationCount").value(2));
    }
}
