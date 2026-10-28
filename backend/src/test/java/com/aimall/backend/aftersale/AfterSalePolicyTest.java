package com.aimall.backend.aftersale;

import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.OrderItem;
import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class AfterSalePolicyTest {
    private OrderItem item(long id, String subtotal, int quantity) {
        OrderItem item = new OrderItem(); item.setId(id); item.setSubtotal(new BigDecimal(subtotal)); item.setQuantity(quantity); return item;
    }
    @Test void unpaidAndCancelledOrdersHaveNoServices() {
        assertTrue(AfterSalePolicy.services("PENDING_PAYMENT").isEmpty());
        assertTrue(AfterSalePolicy.services("CANCELLED").isEmpty());
        assertEquals(List.of("REFUND_ONLY"), AfterSalePolicy.services("PAID"));
        assertTrue(AfterSalePolicy.services("DELIVERED").contains("EXCHANGE"));
    }
    @Test void allocationsUseActualPaidAmountAndNeverLoseACent() {
        var items = List.of(item(1,"1.00",1),item(2,"1.00",1),item(3,"1.00",1));
        assertEquals(new BigDecimal("0.33"), AfterSalePolicy.allocation(new BigDecimal("1.00"),items,1L));
        assertEquals(new BigDecimal("0.34"), AfterSalePolicy.allocation(new BigDecimal("1.00"),items,2L));
        assertEquals(new BigDecimal("0.33"), AfterSalePolicy.allocation(new BigDecimal("1.00"),items,3L));
    }
    @Test void partialQuantityRoundingIsCumulativeAndCappedByRemainingMoney() {
        assertEquals(new BigDecimal("0.33"), AfterSalePolicy.refundCap(new BigDecimal("1.00"),3,0,1,BigDecimal.ZERO));
        assertEquals(new BigDecimal("0.34"), AfterSalePolicy.refundCap(new BigDecimal("1.00"),3,1,1,new BigDecimal("0.33")));
        assertEquals(new BigDecimal("0.33"), AfterSalePolicy.refundCap(new BigDecimal("1.00"),3,2,1,new BigDecimal("0.67")));
        assertThrows(BizException.class, () -> AfterSalePolicy.refundCap(new BigDecimal("10"),2,1,2,BigDecimal.ONE));
    }
    @Test void aReturnCannotJumpStraightToRefundAndAnExchangeRequiresShipment() {
        assertEquals("WAITING_RETURN", AfterSalePolicy.next("RETURN_REFUND","PENDING_MERCHANT","APPROVE"));
        assertEquals("WAITING_REFUND", AfterSalePolicy.next("RETURN_REFUND","RETURN_SHIPPED","RECEIVE"));
        assertEquals("EXCHANGE_SHIPPED", AfterSalePolicy.next("EXCHANGE","WAITING_EXCHANGE","SHIP_EXCHANGE"));
        assertThrows(BizException.class, () -> AfterSalePolicy.next("RETURN_REFUND","WAITING_RETURN","REFUND"));
        assertThrows(BizException.class, () -> AfterSalePolicy.next("EXCHANGE","WAITING_EXCHANGE","REFUND"));
        assertThrows(BizException.class, () -> AfterSalePolicy.next("REFUND_ONLY","REFUNDED","APPROVE"));
    }

    @Test void receivedExchangeCanBeConvertedToARefundButAnUnreturnedExchangeCannot() {
        assertEquals("WAITING_REFUND",AfterSalePolicy.next("EXCHANGE","WAITING_EXCHANGE","CONVERT_REFUND"));
        assertThrows(BizException.class,()->AfterSalePolicy.next("EXCHANGE","WAITING_RETURN","CONVERT_REFUND"));
    }
}
