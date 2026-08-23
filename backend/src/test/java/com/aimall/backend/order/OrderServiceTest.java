package com.aimall.backend.order;

import com.aimall.backend.address.AddressService;
import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.Address;
import com.aimall.backend.entity.Product;
import com.aimall.backend.mapper.OrderInfoMapper;
import com.aimall.backend.mapper.OrderItemMapper;
import com.aimall.backend.mapper.ProductMapper;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

/** 订单创建的库存与收货地址回归测试。 */
class OrderServiceTest {

    private final ProductMapper productMapper = mock(ProductMapper.class);
    private final AddressService addressService = mock(AddressService.class);
    private final OrderService service = new OrderService(
            mock(OrderInfoMapper.class), mock(OrderItemMapper.class), productMapper,
            mock(OrderSseNotifier.class), addressService);

    private static Product product(int stock, int version) {
        Product p = new Product();
        p.setId(1L);
        p.setStatus("ON_SALE");
        p.setName("测试商品");
        p.setPrice(new BigDecimal("99.00"));
        p.setStock(stock);
        p.setVersion(version);
        return p;
    }

    private static OrderDtos.CreateOrderRequest req(int quantity) {
        OrderDtos.CreateOrderRequest r = new OrderDtos.CreateOrderRequest();
        r.setProductId(1L);
        r.setQuantity(quantity);
        r.setReceiverName("张三");
        r.setReceiverPhone("13800000000");
        r.setReceiverAddress("测试地址");
        return r;
    }

    private static Address savedAddress(long id) {
        Address address = new Address();
        address.setId(id);
        address.setUserId(7L);
        address.setReceiverName("李四");
        address.setReceiverPhone("13900000000");
        address.setReceiverAddress("浙江省杭州市西湖区文三路90号");
        return address;
    }

    @Test
    void createUsesSelectedOwnedSavedAddress() {
        OrderDtos.CreateOrderRequest request = req(1);
        request.setAddressId(9L);
        request.setReceiverName(null);
        request.setReceiverPhone(null);
        request.setReceiverAddress(null);
        when(addressService.forOrder(7L, 9L)).thenReturn(savedAddress(9L));
        when(productMapper.selectById(1L)).thenReturn(product(10, 1));
        when(productMapper.updateById(any(Product.class))).thenReturn(1);

        var order = service.create(7L, request, "USER", null);

        assertEquals("李四", order.getReceiverName());
        assertEquals("13900000000", order.getReceiverPhone());
        assertEquals("浙江省杭州市西湖区文三路90号", order.getReceiverAddress());
    }

    @Test
    void createFallsBackToDefaultAddressWhenDeliveryFieldsAreMissing() {
        OrderDtos.CreateOrderRequest request = req(1);
        request.setReceiverName(null);
        request.setReceiverPhone(null);
        request.setReceiverAddress(null);
        when(addressService.defaultFor(7L)).thenReturn(savedAddress(12L));
        when(productMapper.selectById(1L)).thenReturn(product(10, 1));
        when(productMapper.updateById(any(Product.class))).thenReturn(1);

        var order = service.create(7L, request, "USER", null);

        assertEquals("李四", order.getReceiverName());
        verify(addressService).defaultFor(7L);
    }

    @Test
    void createResolvesDeliveryBeforeChangingStock() {
        OrderDtos.CreateOrderRequest request = req(1);
        request.setAddressId(99L);
        when(addressService.forOrder(7L, 99L)).thenThrow(new BizException(2002, "地址不存在"));

        assertThrows(BizException.class, () -> service.create(7L, request, "USER", null));

        verifyNoInteractions(productMapper);
    }

    @Test
    void create_throwsWhenOptimisticConflictPersists() {
        when(productMapper.selectById(1L)).thenReturn(product(10, 5));
        when(productMapper.updateById(any(Product.class))).thenReturn(0);

        BizException ex = assertThrows(BizException.class,
                () -> service.create(1L, req(5), "USER", null));
        assertEquals(2006, ex.getCode());
    }

    @Test
    void create_failsWhenStockInsufficient() {
        when(productMapper.selectById(1L)).thenReturn(product(3, 1));

        BizException ex = assertThrows(BizException.class,
                () -> service.create(1L, req(5), "USER", null));
        assertEquals(2006, ex.getCode());
    }

    @Test
    void create_succeedsOnFirstAttemptWithLegacyDeliveryFields() {
        when(productMapper.selectById(1L)).thenReturn(product(10, 5));
        when(productMapper.updateById(any(Product.class))).thenReturn(1);

        var order = service.create(1L, req(5), "USER", null);
        assertNotNull(order);
        assertEquals("PENDING_PAYMENT", order.getStatus());
        assertEquals("张三", order.getReceiverName());
        verifyNoInteractions(addressService);
    }
}
