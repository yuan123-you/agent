package com.aimall.backend.order;

import com.aimall.backend.entity.OrderInfo;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 订单状态 SSE 推送：每个买家持有一个订阅连接，状态变更时推 "order_status" 事件。
 */
@Component
public class OrderSseNotifier {

    private final Map<Long, SseEmitter> emitters = new ConcurrentHashMap<>();

    public void register(Long userId, SseEmitter emitter) {
        emitters.put(userId, emitter);
        emitter.onCompletion(() -> emitters.remove(userId));
        emitter.onTimeout(() -> emitters.remove(userId));
        emitter.onError(e -> emitters.remove(userId));
    }

    public void publish(OrderInfo order) {
        SseEmitter emitter = emitters.get(order.getUserId());
        if (emitter == null) {
            return; // 未订阅或已断开
        }
        String body = "{\"orderId\":" + order.getId()
                + ",\"orderNo\":\"" + order.getOrderNo()
                + "\",\"status\":\"" + order.getStatus() + "\"}";
        try {
            synchronized (emitter) {
                emitter.send(SseEmitter.event().name("order_status").data(body));
            }
        } catch (Exception e) {
            emitters.remove(order.getUserId());
        }
    }

    /** 每 15s 心跳，防中间层超时断连 */
    @Scheduled(fixedRate = 15000)
    public void heartbeat() {
        emitters.forEach((userId, emitter) -> {
            try {
                synchronized (emitter) {
                    emitter.send(SseEmitter.event().comment("ping"));
                }
            } catch (Exception e) {
                emitters.remove(userId);
            }
        });
    }
}