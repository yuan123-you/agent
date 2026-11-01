package com.aimall.backend.order;

import com.aimall.backend.entity.OrderInfo;
import com.aimall.backend.internal.AgentOrderActionService;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.*;

class OrderActionControllerTest {
    @Test
    void nativeConfirmCancelAndRecoverOnlyCoordinateUsingAuthenticatedOwner() {
        var service = mock(AgentOrderActionService.class);
        var workflows = mock(com.aimall.backend.internal.ActionWorkflowCoordinator.class);
        when(workflows.requiresNative(7L,"act")).thenReturn(true);
        when(workflows.confirm(7L,"act",null)).thenReturn(java.util.Map.of("orderId",88L));
        when(workflows.recover(7L,"act")).thenReturn(java.util.Map.of("workflow",java.util.Map.of("workflowStatus","WAITING_APPROVAL")));
        var controller = new OrderActionController(service,workflows);
        assertEquals(88L,controller.confirm(7L,"act",null).getData().get("orderId"));
        controller.cancel(7L,"act");controller.recover(7L,"act");
        verify(workflows).confirm(7L,"act",null);verify(workflows).cancel(7L,"act");verify(workflows).recover(7L,"act");
        verifyNoInteractions(service);
    }

    @Test
    void flagOffNativeProvenanceCannotReachLegacyConfirmationOrCancellation() {
        var service=mock(AgentOrderActionService.class);
        var props=new com.aimall.backend.config.AppProperties();
        when(service.isNativeManaged(7L,"act")).thenReturn(true);
        var workflows=new com.aimall.backend.internal.ActionWorkflowCoordinator(service,mock(com.aimall.backend.internal.ActionWorkflowClient.class),props);
        var controller=new OrderActionController(service,workflows);
        org.junit.jupiter.api.Assertions.assertThrows(com.aimall.backend.common.BizException.class,()->controller.confirm(7L,"act",null));
        org.junit.jupiter.api.Assertions.assertThrows(com.aimall.backend.common.BizException.class,()->controller.cancel(7L,"act"));
        org.junit.jupiter.api.Assertions.assertThrows(com.aimall.backend.common.BizException.class,()->controller.recover(7L,"act"));
        verify(service,never()).confirm(anyLong(),anyString(),any());verify(service,never()).cancel(anyLong(),anyString());
    }

    @Test
    void confirmUsesAuthenticatedUserInsteadOfRequestSuppliedIdentity() {
        AgentOrderActionService service = mock(AgentOrderActionService.class);
        OrderInfo order = new OrderInfo();
        order.setId(88L);
        order.setOrderNo("A20260823001");
        order.setStatus("PENDING_PAYMENT");
        order.setTotalAmount(new BigDecimal("99.80"));
        when(service.typeOf(7L, "act_123")).thenReturn(AgentOrderActionService.ORDER_CREATE);
        when(service.confirm(7L, "act_123", null)).thenReturn(order);
        OrderActionController controller = new OrderActionController(service);

        var response = controller.confirm(7L, "act_123", null);

        verify(service).confirm(7L, "act_123", null);
        assertEquals(0, response.getCode());
        assertEquals(88L, response.getData().get("orderId"));
    }
    @Test
    void confirmForwardsApprovedDeliveryDataWithAuthenticatedIdentity() {
        AgentOrderActionService service = mock(AgentOrderActionService.class);
        OrderInfo order = new OrderInfo();
        order.setId(89L);
        order.setOrderNo("A20260823002");
        order.setStatus("PENDING_PAYMENT");
        order.setTotalAmount(new BigDecimal("99.80"));
        var approval = new AgentOrderActionService.ApprovalRequest("李四", "13900139000", "杭州文三路90号");
        when(service.typeOf(7L, "act_edited")).thenReturn(AgentOrderActionService.ORDER_CREATE);
        when(service.confirm(7L, "act_edited", approval)).thenReturn(order);
        OrderActionController controller = new OrderActionController(service);

        controller.confirm(7L, "act_edited", approval);

        verify(service).confirm(7L, "act_edited", approval);
    }

    @Test
    void confirmDispatchesPreparedAfterSaleWithoutCreatingOrder() {
        AgentOrderActionService service = mock(AgentOrderActionService.class);
        when(service.typeOf(7L, "act_after")).thenReturn(AgentOrderActionService.AFTER_SALE_APPLY);
        when(service.confirmBusiness(7L, "act_after")).thenReturn(
                new AgentOrderActionService.BusinessConfirmResult("AFTER_SALE_APPLY", "CONFIRMED",
                        30L, "ORD-30", "DELIVERED", 77L, "AS-77"));
        var response = new OrderActionController(service).confirm(7L, "act_after", null);
        assertEquals(77L, response.getData().get("afterSaleId"));
        verify(service, never()).confirm(anyLong(), anyString(), any());
    }

    @Test
    void cancelUsesAuthenticatedUserAndPersistsDecision() {
        AgentOrderActionService service = mock(AgentOrderActionService.class);
        OrderActionController controller = new OrderActionController(service);

        var response = controller.cancel(7L, "act_123");

        verify(service).cancel(7L, "act_123");
        assertEquals(0, response.getCode());
    }    @Test
    void statusUsesAuthenticatedUser() {
        AgentOrderActionService service = mock(AgentOrderActionService.class);
        var status = new AgentOrderActionService.ActionStatusResult("CANCELLED", null, null);
        when(service.status(7L, "act_123")).thenReturn(status);
        OrderActionController controller = new OrderActionController(service);

        var response = controller.status(7L, "act_123");

        verify(service).status(7L, "act_123");
        assertEquals("CANCELLED", response.getData().status());
    }
    @Test void publicStatusAlwaysSerializesAuthoritativeNativeManagedIncludingFalse() {
        var service=mock(AgentOrderActionService.class);
        var controller=new OrderActionController(service);
        var json=new com.fasterxml.jackson.databind.ObjectMapper().findAndRegisterModules();
        for (boolean managed : new boolean[]{false,true}) {
            when(service.status(7L,"act")).thenReturn(new AgentOrderActionService.ActionStatusResult(
                    "ORDER_CREATE","PENDING",null,null,null,null,managed));
            var data=json.valueToTree(controller.status(7L,"act")).path("data");
            org.junit.jupiter.api.Assertions.assertTrue(data.has("nativeManaged"));
            assertEquals(managed,data.path("nativeManaged").asBoolean());
        }
    }

}
