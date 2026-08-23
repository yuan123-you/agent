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
        when(service.confirm(7L, "act_123")).thenReturn(order);
        OrderActionController controller = new OrderActionController(service);

        var response = controller.confirm(7L, "act_123");

        verify(service).confirm(7L, "act_123");
        assertEquals(0, response.getCode());
        assertEquals(88L, response.getData().get("orderId"));
    }
}
