package com.aimall.backend.chat;

import com.aimall.backend.entity.Conversation;
import com.aimall.backend.mapper.ConversationMapper;
import com.aimall.backend.mapper.MessageMapper;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class ChatServiceHandoffTest {
    @ParameterizedTest
    @ValueSource(strings = {"ACTIVE", "PENDING_HUMAN", "SERVICING", "CLOSED"})
    void streamCompletionDoesNotOverwriteTheStateOwnedByTheEscalationEndpoint(String status) {
        ConversationMapper conversations = mock(ConversationMapper.class);
        MessageMapper messages = mock(MessageMapper.class);
        ChatService service = new ChatService(conversations, messages, null, null, null, null, null, null, null, null);
        Conversation conversation = new Conversation();
        conversation.setId(7L);
        conversation.setStatus(status);
        conversation.setMessageCount(0);
        AtomicBoolean finished = new AtomicBoolean();

        ReflectionTestUtils.invokeMethod(service, "handleEvent", "done", "{\"content\":\"已转接人工\"}",
                conversation, new SseEmitter(), new StringBuilder(),
                List.of(Map.<String, Object>of("tool", "escalate_to_human")), finished, System.currentTimeMillis());

        assertThat(finished).isTrue();
        verify(messages).insert(any(com.aimall.backend.entity.Message.class));
        verify(conversations, atLeastOnce()).updateById(any(Conversation.class));
        verify(conversations, never()).updateById(org.mockito.ArgumentMatchers.<Conversation>argThat(update -> update.getStatus() != null));
    }
}
