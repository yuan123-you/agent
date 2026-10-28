package com.aimall.backend.chat;

import com.aimall.backend.common.BizException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.data.redis.core.ListOperations;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.time.Duration;
import java.util.*;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class ChatStreamRecoveryTest {
    StringRedisTemplate redis = mock(StringRedisTemplate.class);
    ValueOperations<String, String> values = mock(ValueOperations.class);
    ListOperations<String, String> lists = mock(ListOperations.class);
    Map<String, String> metadata = new HashMap<>();
    Map<String, List<String>> events = new HashMap<>();
    List<SseEmitter> emitters = new ArrayList<>();
    ChatStreamRecovery recovery;

    @BeforeEach void setup() {
        when(redis.opsForValue()).thenReturn(values);
        when(redis.opsForList()).thenReturn(lists);
        when(values.get(anyString())).thenAnswer(i -> metadata.get(i.getArgument(0)));
        when(values.setIfAbsent(anyString(), anyString(), any(Duration.class))).thenAnswer(i -> {
            String key = i.getArgument(0);
            if (metadata.containsKey(key)) return false;
            metadata.put(key, i.getArgument(1));
            return true;
        });
        when(lists.rightPush(anyString(), anyString())).thenAnswer(i -> {
            var list = events.computeIfAbsent(i.getArgument(0), k -> new ArrayList<>());
            list.add(i.getArgument(1));
            return (long) list.size();
        });
        when(lists.range(anyString(), anyLong(), anyLong())).thenAnswer(i -> {
            var list = events.getOrDefault(i.getArgument(0), List.of());
            int from = Math.min(list.size(), ((Long) i.getArgument(1)).intValue());
            return new ArrayList<>(list.subList(from, list.size()));
        });
        when(redis.execute(any(org.springframework.data.redis.core.script.RedisScript.class), anyList(), anyString())).thenAnswer(i -> {
            String key = ((List<String>) i.getArgument(1)).get(0);
            if (Objects.equals(metadata.get(key), i.getArgument(2))) { metadata.remove(key); return 1L; }
            return 0L;
        });
        recovery = new ChatStreamRecovery(redis, () -> {
            var emitter = mock(SseEmitter.class);
            emitters.add(emitter);
            return emitter;
        });
    }

    @Test void reconnectReplaysTheSameRequestWithoutStartingGenerationAgain() throws Exception {
        var first = recovery.open(1L, 7L, "request-123", "hello", false, null, false);
        assertThat(first.replay()).isFalse();
        recovery.record(first.emitter(), "token", "{\"content\":\"hello\"}");
        recovery.record(first.emitter(), "done", "{\"messageId\":42}");
        var second = recovery.open(1L, 7L, "request-123", "hello", false, null, true);
        assertThat(second.replay()).isTrue();
        recovery.pump();
        verify(second.emitter(), times(2)).send(any(SseEmitter.SseEventBuilder.class));
        verify(second.emitter()).complete();
        assertThat(events.values().iterator().next()).hasSize(2);
    }

    @Test void reconnectDoesNotReserveAnExpiredOrNeverAcceptedRequest() {
        assertThatThrownBy(() -> recovery.open(1L, 7L, "missing", "hello", false, null, true))
                .isInstanceOf(BizException.class);
        verify(values, never()).setIfAbsent(anyString(), anyString(), any(Duration.class));
    }

    @Test void sameRequestIdCannotBeReusedWithDifferentContentOrRetryTarget() {
        recovery.open(1L, 7L, "request-123", "hello", false, null, false);
        assertThatThrownBy(() -> recovery.open(1L, 7L, "request-123", "buy", false, null, true))
                .isInstanceOf(BizException.class);
        assertThatThrownBy(() -> recovery.open(1L, 7L, "request-123", "hello", false, 42L, true))
                .isInstanceOf(BizException.class);
    }

    @Test void requestIdsAreScopedToOwnerAndConversation() {
        assertThat(recovery.open(1L, 7L, "shared-id", "hello", false, null, false).replay()).isFalse();
        assertThat(recovery.open(2L, 7L, "shared-id", "hello", false, null, false).replay()).isFalse();
        assertThat(recovery.open(1L, 8L, "shared-id", "hello", false, null, false).replay()).isFalse();
    }

    @Test void redisFailureFailsClosedInsteadOfRiskingDuplicateTools() {
        when(values.get(anyString())).thenThrow(new IllegalStateException("redis down"));
        assertThatThrownBy(() -> recovery.open(1L, 7L, "request-123", "hello", false, null, true))
                .isInstanceOf(BizException.class);
    }
    @Test void anotherRequestCannotStartToolsWhileTheConversationIsStillRunning() {
        recovery.open(1L, 7L, "request-one", "hello", false, null, false);
        assertThatThrownBy(() -> recovery.open(1L, 7L, "request-two", "new question", false, null, false))
                .isInstanceOf(BizException.class)
                .extracting(e -> ((BizException) e).getCode()).isEqualTo(2006);
    }

    @Test void staleRunsHaveABoundedRecoveryDeadline() throws Exception {
        recovery.open(1L, 7L, "request-old", "hello", false, null, false);
        metadata.replaceAll((key, value) -> key.endsWith("request-old") ? value.substring(0, value.lastIndexOf(':') + 1) + "0" : value);
        var replay = recovery.open(1L, 7L, "request-old", "hello", false, null, true);
        recovery.pump();
        verify(replay.emitter()).send(any(SseEmitter.SseEventBuilder.class));
        verify(replay.emitter()).complete();
    }
    @Test void terminalCompletionReleasesOnlyItsOwnConversationLock() {
        var first = recovery.open(1L, 7L, "request-one", "hello", false, null, false);
        assertThatThrownBy(() -> recovery.open(1L, 7L, "request-two", "other", false, null, false)).isInstanceOf(BizException.class);
        // The rejected second request must not release the first request's lock.
        assertThatThrownBy(() -> recovery.open(1L, 7L, "request-three", "other", false, null, false)).isInstanceOf(BizException.class);
        recovery.record(first.emitter(), "done", "{}");
        assertThat(recovery.open(1L, 7L, "request-four", "other", false, null, false).replay()).isFalse();
    }

    @Test void missingIdentityCannotBypassRecoveryOrTheConversationLock() {
        assertThatThrownBy(() -> recovery.open(1L, 7L, null, "hello", false, null, true)).isInstanceOf(BizException.class);
        assertThat(recovery.open(1L, 7L, null, "hello", false, null, false).replay()).isFalse();
        assertThatThrownBy(() -> recovery.open(1L, 7L, "request-next", "other", false, null, false)).isInstanceOf(BizException.class);
    }
    @Test void orphanedEventsCannotBeInheritedByANewRunWithTheSameId() {
        when(redis.hasKey("chat:replay:1:7:request-old:events")).thenReturn(true);
        assertThatThrownBy(() -> recovery.open(1L, 7L, "request-old", "hello", false, null, false)).isInstanceOf(BizException.class);
    }
    @Test void metadataRetentionIsRefreshedAfterTheEventListRetention() {
        var ticket = recovery.open(1L, 7L, "request-123", "hello", false, null, false);
        recovery.record(ticket.emitter(), "token", "{}");
        var ordered = inOrder(redis);
        ordered.verify(redis).expire("chat:replay:1:7:request-123:events", Duration.ofHours(24));
        ordered.verify(redis).expire("chat:replay:1:7:request-123", Duration.ofHours(24));
    }
}
