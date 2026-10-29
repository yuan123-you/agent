package com.aimall.backend.admin;

import com.aimall.backend.chat.AiTraceService;
import com.aimall.backend.common.PageResult;
import com.aimall.backend.config.*;
import com.aimall.backend.entity.User;
import com.aimall.backend.mapper.UserMapper;
import com.aimall.backend.internal.InternalAiTraceController;
import jakarta.servlet.Filter;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.*;
import org.springframework.context.annotation.*;
import org.springframework.http.MediaType;
import org.springframework.test.context.junit.jupiter.SpringJUnitConfig;
import org.springframework.test.context.web.WebAppConfiguration;
import org.springframework.test.web.servlet.*;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;
import java.util.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringJUnitConfig(AiTraceAccessTest.Config.class)
@WebAppConfiguration
class AiTraceAccessTest {
    @Configuration
    @Import({SecurityFilterTestConfig.class,AiTraceController.class,InternalAiTraceController.class})
    static class Config { @Bean AiTraceService aiTraceService(){return mock(AiTraceService.class);} }
    @Autowired WebApplicationContext context;
    @Autowired @Qualifier("springSecurityFilterChain") Filter filter;
    @Autowired AiTraceService service;
    @Autowired UserMapper users;
    @Autowired JwtService jwt;
    MockMvc mvc;
    @BeforeEach void setup(){ reset(service,users); mvc=MockMvcBuilders.webAppContextSetup(context).addFilters(filter).build(); }
    String auth(String role){
        var user=new User();user.setId(1L);user.setRole(role);user.setStatus("ACTIVE");user.setDeleted(0);
        when(users.selectById(1L)).thenReturn(user);return "Bearer "+jwt.createAccessToken(1L,role);
    }
    @Test void anonymousCannotReadTraces() throws Exception {
        mvc.perform(get("/api/v1/admin/ai-traces")).andExpect(status().isUnauthorized());verifyNoInteractions(service);
    }
    @ParameterizedTest @ValueSource(strings={"CUSTOMER","AGENT","MERCHANT"})
    void nonAdminsCannotReadListOrDetail(String role)throws Exception{
        String token=auth(role);
        mvc.perform(get("/api/v1/admin/ai-traces").header("Authorization",token)).andExpect(status().isForbidden());
        mvc.perform(get("/api/v1/admin/ai-traces/run-1").header("Authorization",token)).andExpect(status().isForbidden());
        verifyNoInteractions(service);
    }
    @Test void administratorReadsPaginatedListAndDetail()throws Exception{
        when(service.list(any(),any(),any(),anyLong(),anyLong())).thenReturn(new PageResult<>(List.of(),0,1,20));
        when(service.detail("run-1")).thenReturn(Map.of("traceId","run-1","stages",List.of()));
        String token=auth("ADMIN");
        mvc.perform(get("/api/v1/admin/ai-traces").header("Authorization",token)).andExpect(status().isOk()).andExpect(jsonPath("$.data.records").isArray());
        mvc.perform(get("/api/v1/admin/ai-traces/run-1").header("Authorization",token)).andExpect(status().isOk()).andExpect(jsonPath("$.data.traceId").value("run-1"));
        when(service.getLatestBenchmark()).thenReturn(Map.of("overallScore", 99.67));
        mvc.perform(get("/api/v1/admin/ai-traces/benchmark").header("Authorization",token)).andExpect(status().isOk()).andExpect(jsonPath("$.data.overallScore").value(99.67));
    }
    @Test void traceWriteRequiresInternalTokenEvenForAdmin()throws Exception{
        mvc.perform(post("/internal/ai-traces/run-1").header("Authorization",auth("ADMIN")).contentType(MediaType.APPLICATION_JSON).content("{}"))
            .andExpect(status().isUnauthorized());verifyNoInteractions(service);
        mvc.perform(post("/internal/ai-traces/run-1").header("X-Internal-Token","synthetic-internal-token").contentType(MediaType.APPLICATION_JSON).content("{}"))
            .andExpect(status().isOk());verify(service).record("run-1","{}");
    }
}
