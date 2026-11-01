package com.aimall.backend.internal;

import com.aimall.backend.common.GlobalExceptionHandler;
import com.aimall.backend.common.RequestBudget;
import com.aimall.backend.config.AppProperties;
import com.aimall.backend.config.InternalAuthFilter;
import com.aimall.backend.entity.OrderInfo;
import com.aimall.backend.order.OrderService;
import com.aimall.backend.mapper.*;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.assertNull;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import java.math.BigDecimal;
import java.time.Instant;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class ActionWorkflowControllerTest {
    private final AgentOrderActionService actions = mock(AgentOrderActionService.class);
    private final ActionWorkflowCoordinator coordinator = mock(ActionWorkflowCoordinator.class);
    private final AgentOrderActionService.ActionSnapshot snapshot = new AgentOrderActionService.ActionSnapshot(
            "act",7L,20L,"ORDER_CREATE","PENDING",Instant.parse("2026-11-01T12:00:00Z"),"hash");
    private MockMvc mvc() {
        var props = new AppProperties(); props.getAi().setInternalToken("test-token");
        return MockMvcBuilders.standaloneSetup(new ActionWorkflowController(actions,coordinator))
                .setControllerAdvice(new GlobalExceptionHandler()).addFilters(new InternalAuthFilter(props)).build();
    }
    @AfterEach void clearAuth() { SecurityContextHolder.clearContext(); assertNull(RequestBudget.current()); }
    @Test void callbacksRequireInternalTokenAndSnapshotHasOnlyFrozenFields() throws Exception {
        var mvc=mvc();
        mvc.perform(post("/internal/tools/action-workflows/snapshot").contentType("application/json")
                .content("{\"userId\":7,\"actionId\":\"act\"}")).andExpect(status().isUnauthorized());
        verifyNoInteractions(actions);
        when(actions.snapshot(7L,"act")).thenReturn(snapshot);
        mvc.perform(post("/internal/tools/action-workflows/snapshot").header("X-Internal-Token","test-token")
                .contentType("application/json").content("{\"userId\":7,\"actionId\":\"act\"}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.length()").value(7))
                .andExpect(jsonPath("$.data.fingerprint").value("hash")).andExpect(jsonPath("$.data.payload").doesNotExist());
    }
    @Test void executionUsesGuardedDomainConfirmationAndReturnsCanonicalEditedDelivery() throws Exception {
        when(actions.snapshot(7L,"act")).thenReturn(snapshot);
        var approval=new AgentOrderActionService.ApprovalRequest("Edited","13900000000","Saved new address");
        var order=new OrderInfo(); order.setId(88L);order.setOrderNo("O88");order.setStatus("PENDING_PAYMENT");
        order.setTotalAmount(BigDecimal.TEN);order.setReceiverName("Edited");order.setReceiverPhone("13900000000");order.setReceiverAddress("Saved new address");
        when(actions.confirm(7L,"act",approval)).thenReturn(order);
        mvc().perform(post("/internal/tools/action-workflows/execute").header("X-Internal-Token","test-token")
                .contentType("application/json").content("{\"userId\":7,\"actionId\":\"act\",\"approval\":{\"receiverName\":\"Edited\",\"receiverPhone\":\"13900000000\",\"receiverAddress\":\"Saved new address\"}}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.orderId").value(88))
                .andExpect(jsonPath("$.data.receiverAddress").value("Saved new address"));
        verify(actions).confirm(7L,"act",approval); verify(coordinator).requireEnabled();
    }
    @Test void unknownResultsAndNonIntegralOwnersAreRejectedBeforeExecution() throws Exception {
        for(String body : new String[]{"{\"userId\":7,\"actionId\":\"act\",\"result\":{}}",
                "{\"userId\":7.1,\"actionId\":\"act\"}",
                "{\"userId\":7,\"actionId\":\"act\",\"approval\":{\"result\":{}}}"}) {
            mvc().perform(post("/internal/tools/action-workflows/execute").header("X-Internal-Token","test-token")
                    .contentType("application/json").content(body)).andExpect(status().isBadRequest());
        }
        verifyNoInteractions(actions);
    }
    @Test void cancelAndBusinessCallbacksUseDomainServicesAndOwnerValidation() throws Exception {
        when(actions.snapshot(7L,"act")).thenReturn(snapshot);
        mvc().perform(post("/internal/tools/action-workflows/cancel").header("X-Internal-Token","test-token")
                .contentType("application/json").content("{\"userId\":7,\"actionId\":\"act\"}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.actionStatus").value("CANCELLED"));
        verify(actions).cancel(7L,"act");
        when(actions.snapshot(8L,"act")).thenThrow(new com.aimall.backend.common.BizException(2003,"forbidden"));
        mvc().perform(post("/internal/tools/action-workflows/execute").header("X-Internal-Token","test-token")
                .contentType("application/json").content("{\"userId\":8,\"actionId\":\"act\"}"))
                .andExpect(status().isForbidden());
        verify(actions,never()).confirm(anyLong(),anyString(),any());
        for(String type : new String[]{"ORDER_CANCEL","AFTER_SALE_APPLY"}) {
            when(actions.snapshot(7L,"act")).thenReturn(new AgentOrderActionService.ActionSnapshot("act",7L,20L,type,"PENDING",snapshot.expiresAt(),"hash"));
            when(actions.confirmBusiness(7L,"act")).thenReturn(new AgentOrderActionService.BusinessConfirmResult(type,"CONFIRMED",30L,"O30","DELIVERED",77L,"AS77"));
            mvc().perform(post("/internal/tools/action-workflows/execute").header("X-Internal-Token","test-token")
                    .contentType("application/json").content("{\"userId\":7,\"actionId\":\"act\"}"))
                    .andExpect(status().isOk()).andExpect(jsonPath("$.data.type").value(type));
        }
    }
    @Test void legacyInternalConfirmCannotBypassNativeFramework() throws Exception {
        var props=new AppProperties(); props.getAi().setActionWorkflowsEnabled(true);
        var realCoordinator=new ActionWorkflowCoordinator(actions,mock(ActionWorkflowClient.class),props);
        var legacy=new InternalToolController(mock(ProductMapper.class),mock(OrderInfoMapper.class),mock(OrderService.class),mock(ConversationMapper.class),actions);
        ReflectionTestUtils.setField(legacy,"workflows",realCoordinator);
        var mvc=MockMvcBuilders.standaloneSetup(legacy).setControllerAdvice(new GlobalExceptionHandler()).build();
        String body="{\"userId\":7,\"actionId\":\"act\"}";
        mvc.perform(post("/internal/tools/order/confirm").contentType("application/json").content(body)).andExpect(status().isConflict());
        props.getAi().setActionWorkflowsEnabled(false);when(actions.isNativeManaged(7L,"act")).thenReturn(true);
        mvc.perform(post("/internal/tools/order/confirm").contentType("application/json").content(body)).andExpect(status().isConflict());
        verify(actions,never()).confirm(anyLong(),anyString());
    }
    @Test void gatewayErrorsExposeRecoverabilityWithoutPrivateUpstreamBody() throws Exception {
        doThrow(new ActionWorkflowClient.GatewayException("act",503,true)).when(coordinator).requireEnabled();
        mvc().perform(post("/internal/tools/action-workflows/execute").header("X-Internal-Token","test-token")
                .contentType("application/json").content("{\"userId\":7,\"actionId\":\"act\"}"))
                .andExpect(status().isServiceUnavailable()).andExpect(jsonPath("$.data.recoverable").value(true));
        verifyNoInteractions(actions);
    }
    @ParameterizedTest
    @CsvSource({"execute,0", "execute,1", "execute,25", "cancel,0", "cancel,1", "cancel,25"})
    void expiredOrReservationTooSmallBudgetRejectsBeforeControllerAndDomain(String operation,String timeout) throws Exception {
        when(actions.snapshot(7L,"act")).thenReturn(snapshot);
        when(actions.confirm(7L,"act",null)).thenReturn(new OrderInfo());
        mvc().perform(post("/internal/tools/action-workflows/"+operation).header("X-Internal-Token","test-token")
                .header(RequestBudget.TIMEOUT_HEADER,timeout).header(RequestBudget.RETRY_HEADER,"6")
                .contentType("application/json").content("{\"userId\":7,\"actionId\":\"act\"}"))
                .andExpect(status().isServiceUnavailable())
                .andExpect(content().contentTypeCompatibleWith("application/json"))
                .andExpect(jsonPath("$.code").value(5002));
        verifyNoInteractions(coordinator,actions);
        assertNull(RequestBudget.current());
    }
    @ParameterizedTest @ValueSource(strings={"execute","cancel"})
    void sufficientDeadlineAdmitsDomainCallbackEvenWithZeroRetryPermits(String operation) throws Exception {
        when(actions.snapshot(7L,"act")).thenReturn(snapshot);
        when(actions.confirm(7L,"act",null)).thenReturn(new OrderInfo());
        mvc().perform(post("/internal/tools/action-workflows/"+operation).header("X-Internal-Token","test-token")
                .header(RequestBudget.TIMEOUT_HEADER,"15000").header(RequestBudget.RETRY_HEADER,"0")
                .contentType("application/json").content("{\"userId\":7,\"actionId\":\"act\"}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.code").value(0));
        verify(coordinator).requireEnabled();
        if (operation.equals("execute")) verify(actions).confirm(7L,"act",null);
        else verify(actions).cancel(7L,"act");
        assertNull(RequestBudget.current());
    }
}
