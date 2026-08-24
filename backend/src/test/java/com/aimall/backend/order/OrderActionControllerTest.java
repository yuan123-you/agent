package com.aimall.backend.order;

import com.aimall.backend.entity.OrderInfo;
import com.aimall.backend.internal.AgentOrderActionService;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.*;

class OrderActionControllerTest {
    @Test
    void confirmUsesAuthenticatedUserInsteadOfRequestSuppliedIdentity() {
        AgentOrderActionService service = mock(AgentOrderActionService.class);
        OrderInfo order = new OrderInfo();
        order.setId(88L);
        order.setOrderNo("A20260823001");
        order.setStatus("PENDING_PAYMENT");
        order.setTotalAmount(new BigDecimal("99.80"));
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
        when(service.confirm(7L, "act_edited", approval)).thenReturn(order);
        OrderActionController controller = new OrderActionController(service);

        controller.confirm(7L, "act_edited", approval);

        verify(service).confirm(7L, "act_edited", approval);
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
}
