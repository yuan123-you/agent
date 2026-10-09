package com.aimall.backend.order;

import com.aimall.backend.address.AddressService;
import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.OrderInfo;
import com.aimall.backend.entity.OrderItem;
import com.aimall.backend.entity.Product;
import com.aimall.backend.mapper.OrderInfoMapper;
import com.aimall.backend.mapper.OrderItemMapper;
import com.aimall.backend.mapper.ProductMapper;
import java.math.BigDecimal;
import java.util.Arrays;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.*;
import org.mockito.ArgumentCaptor;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

/** Direct service regressions: no controller Bean Validation or external services. */
class OrderInputIntegrityTest {
    private final OrderInfoMapper orders = mock(OrderInfoMapper.class);
    private final OrderItemMapper orderItems = mock(OrderItemMapper.class);
    private final ProductMapper products = mock(ProductMapper.class);
    private final OrderSseNotifier notifier = mock(OrderSseNotifier.class);
    private final OrderService service = new OrderService(orders, orderItems, products, notifier,
            mock(AddressService.class));

    private OrderDtos.CreateOrderRequest request(Integer quantity) {
        var req = new OrderDtos.CreateOrderRequest();
        req.setProductId(1L);
        req.setQuantity(quantity);
        req.setReceiverName("Receiver");
        req.setReceiverPhone("13800000000");
        req.setReceiverAddress("Test address");
        return req;
    }

    private Product product(Long id, BigDecimal price) {
        var p = new Product();
        p.setId(id);
        p.setName("Snapshot product");
        p.setImageUrl("snapshot.png");
        p.setStatus("ON_SALE");
        p.setPrice(price);
        p.setStock(1000);
        p.setVersion(1);
        when(products.selectById(id)).thenReturn(p);
        when(products.updateById(any(Product.class))).thenReturn(1);
        return p;
    }

    private void assertInvalid(Runnable action) {
        assertEquals(2001, assertThrows(BizException.class, action::run).getCode());
        verify(products, never()).updateById(any(Product.class));
        verifyNoInteractions(orders, orderItems, notifier);
    }

    @ParameterizedTest @NullSource @ValueSource(ints = {0, -1, Integer.MIN_VALUE})
    void createRejectsInvalidQuantityForRestAndAi(Integer quantity) {
        product(1L, new BigDecimal("12.50"));
        for (String source : List.of("USER", "AI")) {
            assertInvalid(() -> service.create(7L, request(quantity), source, 9L));
        }
    }

    @Test void createRejectsNullRequest() {
        assertInvalid(() -> service.create(7L, null, "AI", 9L));
        verifyNoInteractions(products);
    }

    @Test void createRejectsNullProductIdBeforeMapperLookup() {
        var req = request(1);
        req.setProductId(null);
        assertInvalid(() -> service.create(7L, req, "USER", null));
        verifyNoInteractions(products);
    }

    @ParameterizedTest @NullSource @ValueSource(strings = {"-0.01", "-12.50"})
    void createRejectsMalformedPriceBeforeStockChange(String price) {
        product(1L, price == null ? null : new BigDecimal(price));
        assertInvalid(() -> service.create(7L, request(2), "AI", 9L));
    }

    static List<OrderService.CheckoutItem> malformedEntries() {
        return Arrays.asList(null, new OrderService.CheckoutItem(null, 1),
                new OrderService.CheckoutItem(2L, null), new OrderService.CheckoutItem(2L, 0),
                new OrderService.CheckoutItem(2L, -1));
    }

    @ParameterizedTest @MethodSource("malformedEntries")
    void checkoutPreflightsMalformedLaterEntryBeforeAnyStockChange(OrderService.CheckoutItem invalid) {
        product(1L, new BigDecimal("12.50"));
        assertInvalid(() -> checkout(Arrays.asList(new OrderService.CheckoutItem(1L, 1), invalid)));
        verifyNoInteractions(products);
    }

    @Test void checkoutRejectsMissingItems() {
        assertInvalid(() -> checkout(null));
        assertInvalid(() -> checkout(List.of()));
        verifyNoInteractions(products);
    }

    @ParameterizedTest @NullSource @ValueSource(strings = {"-0.01", "-12.50"})
    void checkoutRejectsMalformedPriceBeforeStockChange(String price) {
        product(1L, price == null ? null : new BigDecimal(price));
        assertInvalid(() -> checkout(List.of(new OrderService.CheckoutItem(1L, 2))));
    }

    @ParameterizedTest @ValueSource(strings = {"0.00", "12.50"})
    void createPreservesSnapshotWithoutInventingServiceQuantityMaximum(String price) {
        Product original = product(1L, new BigDecimal(price));
        var result = service.create(7L, request(100), "AI", 9L);
        BigDecimal subtotal = original.getPrice().multiply(BigDecimal.valueOf(100));
        assertEquals(subtotal, result.getTotalAmount());
        assertEquals("AI", result.getSource());
        assertEquals(9L, result.getConversationId());
        var stock = ArgumentCaptor.forClass(Product.class);
        verify(products).updateById(stock.capture());
        assertEquals(900, stock.getValue().getStock());
        var item = ArgumentCaptor.forClass(OrderItem.class);
        verify(orderItems).insert(item.capture());
        assertEquals(original.getPrice(), item.getValue().getPrice());
        assertEquals(original.getName(), item.getValue().getProductName());
        assertEquals(original.getImageUrl(), item.getValue().getProductImage());
        assertEquals(100, item.getValue().getQuantity());
        assertEquals(subtotal, item.getValue().getSubtotal());
        verify(orders).insert(result);
        verify(notifier).publish(any(OrderInfo.class));
    }

    @Test void checkoutPreservesMixedZeroAndPositivePriceTotal() {
        product(1L, new BigDecimal("0.00"));
        product(2L, new BigDecimal("12.50"));
        var result = checkout(List.of(new OrderService.CheckoutItem(1L, 2),
                new OrderService.CheckoutItem(2L, 3)));
        assertEquals(new BigDecimal("37.50"), result.getTotalAmount());
        verify(products, times(2)).updateById(any(Product.class));
        var captured = ArgumentCaptor.forClass(OrderItem.class);
        verify(orderItems, times(2)).insert(captured.capture());
        assertEquals(new BigDecimal("0.00"), captured.getAllValues().get(0).getSubtotal());
        assertEquals(new BigDecimal("37.50"), captured.getAllValues().get(1).getSubtotal());
        verify(notifier).publish(any(OrderInfo.class));
    }

    private OrderInfo checkout(List<OrderService.CheckoutItem> entries) {
        return service.checkout(7L, entries, null, "Receiver", "13800000000", "Test address");
    }
}