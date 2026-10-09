package com.aimall.backend.order;

import com.aimall.backend.address.AddressService;
import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.OrderInfo;
import com.aimall.backend.entity.OrderItem;
import com.aimall.backend.entity.Product;
import com.aimall.backend.mapper.OrderInfoMapper;
import com.aimall.backend.mapper.OrderItemMapper;
import com.aimall.backend.mapper.ProductMapper;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.mockito.ArgumentCaptor;
import org.mockito.Answers;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class OrderLifecycleTest {
    private final AtomicInteger affectedRows = new AtomicInteger(1);
    private final OrderInfoMapper orders = mock(OrderInfoMapper.class, invocation ->
            invocation.getMethod().getReturnType() == int.class ? affectedRows.get()
                    : Answers.RETURNS_DEFAULTS.answer(invocation));
    private final OrderItemMapper items = mock(OrderItemMapper.class);
    private final ProductMapper products = mock(ProductMapper.class);
    private final OrderSseNotifier notifier = mock(OrderSseNotifier.class);
    private final OrderService service = new OrderService(orders, items, products, notifier, mock(AddressService.class));

    private OrderInfo order(String state) {
        OrderInfo order = new OrderInfo();
        order.setId(30L);
        order.setUserId(7L);
        order.setOrderNo("ORD-30");
        order.setStatus(state);
        when(orders.selectById(30L)).thenReturn(order);
        return order;
    }

    private void command(String name) {
        switch (name) {
            case "pay" -> service.pay(7L, 30L);
            case "cancel" -> service.cancel(7L, 30L);
            case "ship" -> service.ship(30L, "TRACK-30");
            case "deliver" -> service.deliver(30L);
            default -> throw new AssertionError(name);
        }
    }

    @ParameterizedTest
    @CsvSource({"pay,PENDING_PAYMENT,PAID", "cancel,PENDING_PAYMENT,CANCELLED", "ship,PAID,SHIPPED", "deliver,SHIPPED,DELIVERED"})
    void losingDatabaseTransitionMustNotAnnounceSuccessOrApplyInventory(String command, String from, String to) {
        OrderInfo selected = order(from);
        affectedRows.set(0); // Another command already won after the stale read.
        BizException error = assertThrows(BizException.class, () -> command(command));
        assertEquals(2004, error.getCode());
        assertEquals(from, selected.getStatus());
        verifyNoInteractions(notifier, products, items);
    }

    @ParameterizedTest
    @CsvSource({"pay,PENDING_PAYMENT,PAID", "cancel,PENDING_PAYMENT,CANCELLED", "ship,PAID,SHIPPED", "deliver,SHIPPED,DELIVERED"})
    void winningTransitionRetainsExistingStateRules(String command, String from, String to) {
        OrderInfo selected = order(from);
        command(command);
        assertEquals(to, selected.getStatus());
        verify(notifier).publish(any(OrderInfo.class));
    }

    @Test
    void successfulCancelRestoresStockExactlyOnce() {
        order("PENDING_PAYMENT");
        OrderItem item = new OrderItem(); item.setProductId(1L); item.setQuantity(2);
        when(items.selectList(any())).thenReturn(List.of(item));
        Product product = new Product(); product.setId(1L); product.setStock(3); product.setVersion(1);
        when(products.selectById(1L)).thenReturn(product);
        when(products.updateById(any(Product.class))).thenReturn(1);
        service.cancel(7L, 30L);
        ArgumentCaptor<Product> update = ArgumentCaptor.forClass(Product.class);
        verify(products).updateById(update.capture());
        assertEquals(5, update.getValue().getStock());
    }

    @Test
    void nonOwnerStillCannotChangeOrderState() {
        order("PENDING_PAYMENT");
        BizException error = assertThrows(BizException.class, () -> service.pay(8L, 30L));
        assertEquals(2003, error.getCode());
        verifyNoInteractions(notifier, products, items);
    }

    @Test
    void repeatedPayStillFailsWithoutASecondNotification() {
        order("PAID");
        BizException error = assertThrows(BizException.class, () -> service.pay(7L, 30L));
        assertEquals(2004, error.getCode());
        verifyNoInteractions(notifier);
    }

    private void transaction(Runnable test) {
        TransactionSynchronizationManager.initSynchronization();
        TransactionSynchronizationManager.setActualTransactionActive(true);
        try { test.run(); }
        finally {
            TransactionSynchronizationManager.clearSynchronization();
            TransactionSynchronizationManager.setActualTransactionActive(false);
        }
    }

    @Test
    void notificationWaitsUntilSuccessfulCommit() {
        order("PENDING_PAYMENT");
        transaction(() -> {
            service.pay(7L, 30L);
            verifyNoInteractions(notifier);
            TransactionSynchronizationManager.getSynchronizations().forEach(TransactionSynchronization::afterCommit);
            verify(notifier).publish(any(OrderInfo.class));
        });
    }

    @Test
    void rollbackDoesNotAnnounceAStateThatNeverCommitted() {
        order("PENDING_PAYMENT");
        transaction(() -> {
            service.pay(7L, 30L);
            TransactionSynchronizationManager.getSynchronizations()
                    .forEach(callback -> callback.afterCompletion(TransactionSynchronization.STATUS_ROLLED_BACK));
            verifyNoInteractions(notifier);
        });
    }

    @Test
    void pendingEventValuesAreDetachedFromMutableOrderObjects() {
        OrderInfo selected = order("PENDING_PAYMENT");
        transaction(() -> {
            service.pay(7L, 30L);
            selected.setStatus("CANCELLED");
            TransactionSynchronizationManager.getSynchronizations().forEach(TransactionSynchronization::afterCommit);
            ArgumentCaptor<OrderInfo> event = ArgumentCaptor.forClass(OrderInfo.class);
            verify(notifier).publish(event.capture());
            assertEquals("PAID", event.getValue().getStatus());
            assertEquals(30L, event.getValue().getId());
            assertEquals(7L, event.getValue().getUserId());
        });
    }

    @Test
    void notificationFailureDoesNotTurnCommittedBusinessIntoAnApiFailure() {
        order("PENDING_PAYMENT");
        doThrow(new IllegalStateException("subscriber disconnected")).when(notifier).publish(any(OrderInfo.class));
        transaction(() -> {
            assertDoesNotThrow(() -> service.pay(7L, 30L));
            assertDoesNotThrow(() -> TransactionSynchronizationManager.getSynchronizations().forEach(TransactionSynchronization::afterCommit));
        });
    }
}
