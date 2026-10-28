package com.aimall.backend.chat;
import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.Conversation;
import com.aimall.backend.entity.Message;
import com.aimall.backend.mapper.ConversationMapper;
import com.aimall.backend.mapper.MessageMapper;
import com.aimall.backend.mapper.UserMapper;
import org.junit.jupiter.api.Test;
import org.springframework.http.codec.ServerSentEvent;
import reactor.core.publisher.Flux;
import java.util.*;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
class ChatServiceRecoveryTest {
    ConversationMapper conversations = mock(ConversationMapper.class);
    MessageMapper messages = mock(MessageMapper.class);
    AiClient client = mock(AiClient.class);
    ChatService service = new ChatService(conversations, messages, null, mock(UserMapper.class), client,
            mock(SseEmitterManager.class), null, null, mock(FaqService.class), null, null);
    void setup() {
        var conv = new Conversation(); conv.setId(7L); conv.setUserId(1L);
        conv.setStatus("ACTIVE"); conv.setMessageCount(2);
        when(conversations.selectById(7L)).thenReturn(conv);
    }
    Message message(long id, String role, String status, String content) {
        var m = new Message(); m.setId(id); m.setConversationId(7L);
        m.setRole(role); m.setStatus(status); m.setContent(content); return m;
    }
    ChatDtos.SendMessageRequest request(Long retry) {
        var req = new ChatDtos.SendMessageRequest(); req.setConversationId(7L);
        req.setContent("hello"); req.setRetryMessageId(retry); return req;
    }
    @Test void abnormalEofPersistsFailedRatherThanSuccessfulReply() {
        setup(); when(messages.selectRecent(7L, 10)).thenReturn(new ArrayList<>());
        when(client.streamChat(anyMap())).thenReturn(Flux.empty());
        service.sendMessage(1L, request(null));
        verify(messages).insert(argThat((Message m) -> "AI".equals(m.getRole()) && "FAILED".equals(m.getStatus()) && "".equals(m.getContent())));
    }
    @Test void retryReusesTheOriginalUserMessageAndOmitsTheFailedTurnFromHistory() {
        setup(); when(messages.selectRecent(7L, 10)).thenReturn(new ArrayList<>(List.of(
                message(42, "AI", "FAILED", "partial"), message(41, "USER", "SUCCESS", "hello"))));
        when(client.streamChat(anyMap())).thenReturn(Flux.just(ServerSentEvent.<String>builder("{\"content\":\"ok\"}").event("done").build()));
        service.sendMessage(1L, request(42L));
        verify(messages, never()).insert(argThat((Message m) -> "USER".equals(m.getRole())));
        verify(client).streamChat(argThat(body -> ((List<?>) body.get("history")).isEmpty()
                && Boolean.TRUE.equals(((Map<?, ?>) body.get("options")).get("regenerate"))));
    }
    @Test void onlyTheLatestFailedReplyCanBeRegenerated() {
        setup(); when(messages.selectRecent(7L, 10)).thenReturn(new ArrayList<>(List.of(
                message(42, "AI", "SUCCESS", "ok"), message(41, "USER", "SUCCESS", "hello"))));
        assertThatThrownBy(() -> service.sendMessage(1L, request(42L))).isInstanceOf(BizException.class);
        verifyNoInteractions(client);
    }
    @Test void retryCannotChangeTheOriginalQuestion() {
        setup(); when(messages.selectRecent(7L, 10)).thenReturn(new ArrayList<>(List.of(
                message(42, "AI", "FAILED", ""), message(41, "USER", "SUCCESS", "cancel order"))));
        assertThatThrownBy(() -> service.sendMessage(1L, request(42L))).isInstanceOf(BizException.class);
        verifyNoInteractions(client);
    }

    @Test void aFailedBusinessToolTurnCannotBeAutomaticallyRegenerated() {
        setup(); var failed = message(42, "AI", "FAILED", "");
        failed.setToolCalls("[{\"callId\":\"one\",\"tool\":\"order_create\"}]");
        when(messages.selectRecent(7L, 10)).thenReturn(new ArrayList<>(List.of(failed, message(41, "USER", "SUCCESS", "hello"))));
        assertThatThrownBy(() -> service.sendMessage(1L, request(42L))).isInstanceOf(BizException.class);
        verifyNoInteractions(client);
    }

    @Test void terminalFailureCarriesItsPersistedMessageIdToTheClient() {
        setup(); var recovery = mock(ChatStreamRecovery.class);
        var emitter = mock(org.springframework.web.servlet.mvc.method.annotation.SseEmitter.class);
        service = new ChatService(conversations, messages, null, mock(UserMapper.class), client,
                mock(SseEmitterManager.class), null, null, mock(FaqService.class), null, recovery);
        when(recovery.open(anyLong(), anyLong(), anyString(), anyString(), anyBoolean(), isNull(), anyBoolean()))
                .thenReturn(new ChatStreamRecovery.Ticket(emitter, false));
        when(messages.selectRecent(7L, 10)).thenReturn(new ArrayList<>());
        doAnswer(i -> { ((Message) i.getArgument(0)).setId(42L); return 1; }).when(messages).insert(any(Message.class));
        when(client.streamChat(anyMap())).thenReturn(Flux.error(new RuntimeException("unavailable")));
        var req = request(null); req.setRequestId("request-123");
        var dropped = new java.util.concurrent.atomic.AtomicReference<Throwable>();
        reactor.core.publisher.Hooks.onErrorDropped(dropped::set);
        try { service.sendMessage(1L, req); }
        finally { reactor.core.publisher.Hooks.resetOnErrorDropped(); }
        assertThat(dropped.get()).isNull();
        verify(recovery).record(eq(emitter), eq("error"), contains("\"messageId\":42"));
        verify(messages).insert(argThat((Message m) -> "AI".equals(m.getRole()) && "FAILED".equals(m.getStatus())));
    }

    @Test void initializationFailureAfterUserInsertionPersistsAFailedReply() {
        setup(); var faq = mock(FaqService.class);
        when(faq.match("hello")).thenThrow(new IllegalStateException("lookup failed"));
        service = new ChatService(conversations, messages, null, mock(UserMapper.class), client,
                mock(SseEmitterManager.class), null, null, faq, null, null);
        when(messages.selectRecent(7L, 10)).thenReturn(new ArrayList<>());
        assertThatCode(() -> service.sendMessage(1L, request(null))).doesNotThrowAnyException();
        verify(messages).insert(argThat((Message m) -> "AI".equals(m.getRole()) && "FAILED".equals(m.getStatus())));
    }
    @Test void durableEventRecordingFailureStopsTheStreamInsteadOfSavingSuccess() {
        setup(); var recovery = mock(ChatStreamRecovery.class);
        var emitter = mock(org.springframework.web.servlet.mvc.method.annotation.SseEmitter.class);
        service = new ChatService(conversations, messages, null, mock(UserMapper.class), client,
                mock(SseEmitterManager.class), null, null, mock(FaqService.class), null, recovery);
        when(recovery.open(anyLong(), anyLong(), anyString(), anyString(), anyBoolean(), isNull(), anyBoolean()))
                .thenReturn(new ChatStreamRecovery.Ticket(emitter, false));
        doThrow(new IllegalStateException("replay write failed")).when(recovery).record(eq(emitter), eq("tool_call"), anyString());
        when(messages.selectRecent(7L, 10)).thenReturn(new ArrayList<>());
        when(client.streamChat(anyMap())).thenReturn(Flux.just(
                ServerSentEvent.<String>builder("{\"callId\":\"one\",\"tool\":\"order_create\"}").event("tool_call").build(),
                ServerSentEvent.<String>builder("{\"content\":\"ok\"}").event("done").build()));
        var req = request(null); req.setRequestId("request-123"); service.sendMessage(1L, req);
        verify(messages, never()).insert(argThat((Message m) -> "AI".equals(m.getRole()) && "SUCCESS".equals(m.getStatus())));
        verify(messages).insert(argThat((Message m) -> "AI".equals(m.getRole()) && "FAILED".equals(m.getStatus())));
    }
}
