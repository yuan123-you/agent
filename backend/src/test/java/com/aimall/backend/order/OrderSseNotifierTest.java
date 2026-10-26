package com.aimall.backend.order;

import com.aimall.backend.entity.OrderInfo;
import java.io.IOException;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class OrderSseNotifierTest {
    private OrderInfo order() {
        OrderInfo order = new OrderInfo(); order.setId(5L); order.setUserId(7L);
        order.setOrderNo("ORD-5"); order.setStatus("PAID"); return order;
    }
    @Test
    void completionOfOldConnectionCannotRemoveItsReplacement() throws Exception {
        OrderSseNotifier notifier = new OrderSseNotifier();
        SseEmitter old = mock(SseEmitter.class), current = mock(SseEmitter.class);
        AtomicReference<Runnable> completion = new AtomicReference<>();
        doAnswer(call -> { completion.set(call.getArgument(0)); return null; }).when(old).onCompletion(any());
        notifier.register(7L, old); notifier.register(7L, current); completion.get().run();
        notifier.publish(order());
        verify(current).send(any(SseEmitter.SseEventBuilder.class));
    }
    @Test
    void replacingASubscriptionClosesThePreviousConnection() {
        OrderSseNotifier notifier = new OrderSseNotifier();
        SseEmitter old = mock(SseEmitter.class), current = mock(SseEmitter.class);
        notifier.register(7L, old); notifier.register(7L, current);
        verify(old).complete(); verify(current, never()).complete();
    }
    @Test
    void sendFailureOnAnOldConnectionCannotRemoveAConcurrentReplacement() throws Exception {
        OrderSseNotifier notifier = new OrderSseNotifier();
        SseEmitter old = mock(SseEmitter.class), current = mock(SseEmitter.class);
        notifier.register(7L, old);
        doAnswer(call -> { notifier.register(7L, current); throw new IOException("connection closed"); })
                .when(old).send(any(SseEmitter.SseEventBuilder.class));
        notifier.publish(order()); notifier.publish(order());
        verify(current).send(any(SseEmitter.SseEventBuilder.class));
    }
}
