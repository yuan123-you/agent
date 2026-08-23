package com.aimall.backend.chat;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * SSE 连接生命周期管理：注册/移除 + 心跳，防止内存泄漏
 * <p>线程安全：SseEmitter 非线程安全，业务事件线程（Reactor）与心跳调度线程
 * 可能并发写同一 emitter，导致 chunked 输出流损坏（前端表现为
 * ERR_INCOMPLETE_CHUNKED_ENCODING）。因此所有 send/complete 均以
 * emitter 自身为锁串行化。</p>
 */
@Component
public class SseEmitterManager {

    private final Map<String, SseEmitter> emitters = new ConcurrentHashMap<>();

    public void register(Long userId, Long conversationId, SseEmitter emitter) {
        String key = key(userId, conversationId);
        emitters.put(key, emitter);
        emitter.onCompletion(() -> emitters.remove(key));
        emitter.onTimeout(() -> emitters.remove(key));
        emitter.onError(e -> emitters.remove(key));
    }

    public void remove(Long userId, Long conversationId) {
        emitters.remove(key(userId, conversationId));
    }

    /** 每 15s 心跳（SSE 注释行），防中间层超时断连 */
    @Scheduled(fixedRate = 15000)
    public void heartbeat() {
        emitters.forEach((key, emitter) -> {
            try {
                synchronized (emitter) {
                    emitter.send(SseEmitter.event().comment("ping"));
                }
            } catch (Exception e) {
                emitters.remove(key);
            }
        });
    }

    private String key(Long userId, Long conversationId) {
        return userId + ":" + conversationId;
    }
}
