package com.aimall.backend.order;
import com.aimall.backend.common.BizException;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
class OrderShippingAuthorityTest {
 @Test void buyerCannotTurnAnOwnedPaidOrderIntoAnApparentlyRealShipment() {
  OrderService orders=mock(OrderService.class);
  var controller=new OrderController(orders,mock(OrderSseNotifier.class));
  var order=new com.aimall.backend.entity.OrderInfo();order.setId(30L);order.setUserId(7L);order.setStatus("PAID");
  when(orders.requireOwned(7L,30L)).thenReturn(order);
  BizException error=assertThrows(BizException.class,()->controller.simulateShip(7L,30L));
  assertEquals(2003,error.getCode());verify(orders,never()).ship(anyLong(),anyString(),anyString());
 }
}
