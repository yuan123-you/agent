package com.aimall.backend.chat;

import com.aimall.backend.common.BizException;
import com.aimall.backend.common.JsonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Supplier;

/** Reconnects replay events, never invoke the model or its business tools a second time. */
@Service
public class ChatStreamRecovery {
    private static final Duration RETENTION = Duration.ofHours(24);
    private static final long RUN_DEADLINE_MS = 300_000;
    private final StringRedisTemplate redis;
    private final Supplier<SseEmitter> emitterFactory;
    private final Map<SseEmitter, String> producers = Collections.synchronizedMap(new WeakHashMap<>());
    private final Map<SseEmitter, Replay> replays = new ConcurrentHashMap<>();

    @Autowired
    public ChatStreamRecovery(StringRedisTemplate redis) {
        this(redis, () -> new SseEmitter(310_000L));
    }

    ChatStreamRecovery(StringRedisTemplate redis, Supplier<SseEmitter> emitterFactory) {
        this.redis = redis;
        this.emitterFactory = emitterFactory;
    }

    public record Ticket(SseEmitter emitter, boolean replay) {}
    private static final class Replay {
        final String key;
        final long deadline;
        long cursor;
        long lastHeartbeat = System.currentTimeMillis();
        Replay(String key, long deadline) { this.key = key; this.deadline = deadline; }
    }

    public Ticket open(Long userId, Long conversationId, String requestId, String content,
                       boolean webSearch, Long retryMessageId, boolean resumeOnly) {
        if (requestId == null) {
            if (resumeOnly) throw new BizException(1001, "恢复请求缺少请求标识");
            // Legacy callers still acquire the same conversation lock; they cannot bypass it.
            requestId = UUID.randomUUID().toString();
        }
        if (!requestId.matches("[a-zA-Z0-9_-]{8,80}")) throw new BizException(1001, "请求标识无效");
        String key = "chat:replay:" + userId + ":" + conversationId + ":" + requestId;
        String fingerprint = fingerprint(content + "\n" + webSearch + "\n" + retryMessageId);
        try {
            String metadata = redis.opsForValue().get(key);
            if (metadata == null) {
                if (resumeOnly || Boolean.TRUE.equals(redis.hasKey(key + ":events"))) {
                    throw new BizException(2010, "恢复记录已过期，请重新提问");
                }
                String fresh = fingerprint + ":" + (System.currentTimeMillis() + RUN_DEADLINE_MS);
                if (Boolean.TRUE.equals(redis.opsForValue().setIfAbsent(key, fresh, RETENTION))) {
                    SseEmitter emitter = emitterFactory.get();
                    producers.put(emitter, key);
                    String activeKey = key.substring(0, key.lastIndexOf(':')) + ":active";
                    if (!Boolean.TRUE.equals(redis.opsForValue().setIfAbsent(activeKey, requestId, Duration.ofMillis(RUN_DEADLINE_MS)))) {
                        record(emitter, "error", "{\"code\":2006,\"message\":\"上一条回复仍在处理中\"}");
                        throw new BizException(2006, "上一条回复仍在处理中，请稍后再试");
                    }
                    return new Ticket(emitter, false);
                }
                metadata = redis.opsForValue().get(key);
            }
            if (metadata == null || !metadata.startsWith(fingerprint + ":")) {
                throw new BizException(2010, "请求记录不匹配，请重新提问");
            }
            if (replays.values().stream().filter(r -> r.key.equals(key)).count() >= 3) {
                throw new BizException(1005, "恢复连接过于频繁，请稍后再试");
            }
            SseEmitter emitter = emitterFactory.get();
            Replay replay = new Replay(key, Long.parseLong(metadata.substring(fingerprint.length() + 1)));
            replays.put(emitter, replay);
            emitter.onCompletion(() -> replays.remove(emitter));
            emitter.onTimeout(() -> replays.remove(emitter));
            emitter.onError(e -> replays.remove(emitter));
            return new Ticket(emitter, true);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            // Fail closed: an unavailable replay store must not cause duplicate tool execution.
            throw new BizException(5003, "暂时无法恢复连接，请稍后再试");
        }
    }

    /** Called before writing to the socket, so a disconnected client cannot lose the result. */
    public void record(SseEmitter emitter, String name, String data) {
        String key = producers.get(emitter);
        if (key == null) return;
        String eventsKey = key + ":events";
        try {
            redis.opsForList().rightPush(eventsKey, JsonUtil.write(Map.of("event", name, "data", data)));
            redis.expire(eventsKey, RETENTION);
            // Metadata must outlive the events; otherwise a reused identity can inherit an old tail.
            redis.expire(key, RETENTION);
        } catch (RuntimeException e) {
            throw new RecordingException(e);
        }
        if ("done".equals(name) || "error".equals(name)) {
            producers.remove(emitter);
            // Compare-and-delete: an old run must never release a newer run's conversation lock.
            String activeKey = key.substring(0, key.lastIndexOf(':')) + ":active";
            String requestId = key.substring(key.lastIndexOf(':') + 1);
            try {
                redis.execute(new DefaultRedisScript<>(
                        "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end", Long.class),
                        List.of(activeKey), requestId);
            } catch (RuntimeException ignored) {
                // The terminal event is durable. Keep the lease until expiry rather than undo it.
            }
        }
    }

    /** Redis-backed polling also works when a reconnect reaches another backend instance. */
    @Scheduled(fixedDelay = 250)
    public void pump() {
        replays.forEach((emitter, replay) -> {
            try {
                // Bound each tick; large completed replies are drained over successive ticks.
                List<String> frames = redis.opsForList().range(replay.key + ":events", replay.cursor, replay.cursor + 255);
                if (frames != null) for (String frame : frames) {
                    var node = JsonUtil.parse(frame);
                    if (node == null) throw new IllegalStateException("Invalid replay frame");
                    String name = node.path("event").asText();
                    synchronized (emitter) {
                        emitter.send(SseEmitter.event().name(name).data(node.path("data").asText()));
                    }
                    replay.cursor++;
                    if ("done".equals(name) || "error".equals(name)) {
                        replays.remove(emitter);
                        emitter.complete();
                        return;
                    }
                }
                if ((frames == null || frames.isEmpty()) && System.currentTimeMillis() > replay.deadline) {
                    synchronized (emitter) {
                        emitter.send(SseEmitter.event().name("error").data("{\"code\":2011,\"message\":\"未能恢复这次回复，请重新提问\"}"));
                    }
                    replays.remove(emitter);
                    emitter.complete();
                } else if (System.currentTimeMillis() - replay.lastHeartbeat >= 15_000) {
                    synchronized (emitter) { emitter.send(SseEmitter.event().comment("ping")); }
                    replay.lastHeartbeat = System.currentTimeMillis();
                }
            } catch (Exception e) {
                replays.remove(emitter);
                emitter.completeWithError(e);
            }
        });
    }

    public static final class RecordingException extends RuntimeException {
        RecordingException(Throwable cause) { super("Unable to persist chat recovery event", cause); }
    }

    private static String fingerprint(String value) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) { throw new IllegalStateException(e); }
    }
}
