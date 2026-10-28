package com.aimall.backend.order;

import com.aimall.backend.address.AddressService;
import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.*;
import com.aimall.backend.mapper.*;
import com.aimall.backend.promotion.PromotionService;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.*;
import org.mockito.ArgumentCaptor;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class AdminOrderShippingValidationTest {
    final OrderInfoMapper orders=mock(OrderInfoMapper.class);
    final OrderItemMapper items=mock(OrderItemMapper.class);
    final OrderSseNotifier notifier=mock(OrderSseNotifier.class);
    final OrderService service=new OrderService(orders,items,mock(ProductMapper.class),mock(MallSkuMapper.class),mock(PromotionService.class),notifier,mock(AddressService.class));
    final AdminOrderController admin=new AdminOrderController(service,mock(UserMapper.class));
    @ParameterizedTest @NullSource @ValueSource(strings={"", "  "})
    void missingTrackingNeverGeneratesSyntheticShipment(String tracking) {
        var body=new HashMap<String,String>(); if(tracking!=null)body.put("logisticsNo",tracking);
        assertEquals(2001,assertThrows(BizException.class,()->admin.ship(30L,body)).getCode());
        verifyNoInteractions(orders,items,notifier);
    }
    @Test void directShippingAlsoRejectsOversizedTrackingOrCarrierBeforeWrites() {
        assertEquals(2001,assertThrows(BizException.class,()->service.ship(30L,"X".repeat(101),null)).getCode());
        assertEquals(2001,assertThrows(BizException.class,()->service.ship(30L,"TRACK","C".repeat(81))).getCode());
        verifyNoInteractions(orders,items,notifier);
    }
    @Test void operatorEnteredTrackingAndOptionalCarrierAreTrimmedAndPersisted() {
        OrderInfo order=new OrderInfo();order.setId(30L);order.setUserId(7L);order.setStatus("PAID");
        when(orders.selectById(30L)).thenReturn(order);when(orders.transition(eq("PAID"),any())).thenReturn(1);
        OrderItem item=new OrderItem();item.setId(1L);item.setOrderId(30L);item.setQuantity(1);when(items.selectList(any())).thenReturn(List.of(item));
        admin.ship(30L,Map.of("logisticsNo","  REAL-TRACK  ","deliveryCompany"," Carrier "));
        var capture=ArgumentCaptor.forClass(OrderInfo.class);verify(orders).transition(eq("PAID"),capture.capture());
        assertEquals("REAL-TRACK",capture.getValue().getLogisticsNo());assertEquals("Carrier",capture.getValue().getDeliveryCompany());
    }
}
