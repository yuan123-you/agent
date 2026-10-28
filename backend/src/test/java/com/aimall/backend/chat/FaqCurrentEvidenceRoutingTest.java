package com.aimall.backend.chat;

import com.aimall.backend.config.AppProperties;
import com.aimall.backend.entity.Conversation;
import com.aimall.backend.entity.Message;
import com.aimall.backend.mapper.ConversationMapper;
import com.aimall.backend.mapper.MessageMapper;
import com.aimall.backend.mapper.UserMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import reactor.core.publisher.Flux;

import java.util.ArrayList;
import java.util.concurrent.atomic.AtomicLong;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/** Exercises the real FAQ decision and chat consumer without live KB/model infrastructure. */
class FaqCurrentEvidenceRoutingTest {
    private final ConversationMapper conversations = mock(ConversationMapper.class);
    private final MessageMapper messages = mock(MessageMapper.class);
    private final AiClient client = mock(AiClient.class);
    private final ChatStreamRecovery recovery = mock(ChatStreamRecovery.class);
    private final SseEmitter emitter = mock(SseEmitter.class);
    private ChatService chat;

    @BeforeEach
    void setup() {
        Conversation conversation = new Conversation();
        conversation.setId(7L);
        conversation.setUserId(1L);
        conversation.setStatus("ACTIVE");
        conversation.setMessageCount(0);
        when(conversations.selectById(7L)).thenReturn(conversation);
        when(messages.selectRecent(7L, 10)).thenReturn(new ArrayList<>());
        AtomicLong ids = new AtomicLong(10);
        doAnswer(invocation -> {
            ((Message) invocation.getArgument(0)).setId(ids.incrementAndGet());
            return 1;
        }).when(messages).insert(any(Message.class));
        when(recovery.open(eq(1L), eq(7L), anyString(), anyString(), eq(false), isNull(), eq(false)))
                .thenReturn(new ChatStreamRecovery.Ticket(emitter, false));
        StringRedisTemplate redis = mock(StringRedisTemplate.class);
        @SuppressWarnings("unchecked")
        ValueOperations<String, String> values = mock(ValueOperations.class);
        when(redis.opsForValue()).thenReturn(values);
        when(values.increment(anyString())).thenReturn(1L);
        chat = new ChatService(conversations, messages, null, mock(UserMapper.class), client,
                mock(SseEmitterManager.class), redis, new AppProperties(), new FaqService(), null, recovery);
    }

    private void askRefundFaq() {
        ChatDtos.SendMessageRequest request = new ChatDtos.SendMessageRequest();
        request.setConversationId(7L);
        request.setRequestId("faq-current-evidence");
        request.setContent("退款多久能到账？");
        chat.sendMessage(1L, request);
    }

    private void done(String payload) {
        when(client.streamChat(anyMap())).thenReturn(Flux.just(
                ServerSentEvent.<String>builder(payload).event("done").build()));
    }

    @Test
    void exactBundledFaqUsesCurrentValidatedAnswerAndForwardsItsCitations() {
        done("{\"content\":\"当前有效规则。[S1]\",\"citations\":[{\"id\":\"S1\",\"chunk_id\":77,\"title\":\"当前版本\"}]}");

        askRefundFaq();

        verify(client).streamChat(argThat(body -> "退款多久能到账？".equals(body.get("message"))));
        verify(messages).insert(argThat((Message m) -> "AI".equals(m.getRole())
                && "SUCCESS".equals(m.getStatus()) && "当前有效规则。[S1]".equals(m.getContent())));
        verify(recovery).record(eq(emitter), eq("done"), contains("\"chunk_id\":77"));
        verify(recovery, never()).record(eq(emitter), eq("done"), contains("\"faq\":true"));
    }

    @Test
    void disabledOrMissingPolicyDoesNotFallBackToBundledFaq() {
        done("{\"content\":\"当前知识库证据不足，暂时无法可靠回答该问题。\",\"citations\":[]}");

        askRefundFaq();

        verify(client).streamChat(anyMap());
        verify(messages).insert(argThat((Message m) -> "AI".equals(m.getRole())
                && "当前知识库证据不足，暂时无法可靠回答该问题。".equals(m.getContent())));
        verify(recovery).record(eq(emitter), eq("done"), contains("\"citations\":[]"));
    }

    @Test
    void unavailableRetrievalRemainsDegradedInsteadOfBecomingBundledSuccess() {
        done("{\"content\":\"知识库暂时不可用，请稍后再试。\",\"citations\":[],\"degraded\":true}");

        askRefundFaq();

        verify(client).streamChat(anyMap());
        verify(messages).insert(argThat((Message m) -> "AI".equals(m.getRole())
                && "DEGRADED".equals(m.getStatus()) && "知识库暂时不可用，请稍后再试。".equals(m.getContent())));
        verify(messages, never()).insert(argThat((Message m) -> "AI".equals(m.getRole())
                && "SUCCESS".equals(m.getStatus())));
    }

    @Test
    void failedUpstreamRemainsFailedInsteadOfServingBundledPolicy() {
        when(client.streamChat(anyMap())).thenReturn(Flux.error(new IllegalStateException("offline fixture")));

        askRefundFaq();

        verify(client).streamChat(anyMap());
        verify(messages).insert(argThat((Message m) -> "AI".equals(m.getRole()) && "FAILED".equals(m.getStatus())));
        verify(recovery).record(eq(emitter), eq("error"), anyString());
        verify(messages, never()).insert(argThat((Message m) -> "AI".equals(m.getRole())
                && "SUCCESS".equals(m.getStatus())));
    }
}
