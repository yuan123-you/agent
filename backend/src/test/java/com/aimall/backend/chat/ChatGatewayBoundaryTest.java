package com.aimall.backend.chat;

import com.aimall.backend.entity.Conversation;
import com.aimall.backend.entity.User;
import com.aimall.backend.mapper.ConversationMapper;
import com.aimall.backend.mapper.MessageMapper;
import com.aimall.backend.mapper.UserMapper;
import org.junit.jupiter.api.Test;
import reactor.core.publisher.Flux;

import java.util.ArrayList;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class ChatGatewayBoundaryTest {
    ConversationMapper conversations = mock(ConversationMapper.class);
    MessageMapper messages = mock(MessageMapper.class);
    UserMapper users = mock(UserMapper.class);
    UserMemoryService memories = mock(UserMemoryService.class);
    AiClient client = mock(AiClient.class);
    ChatService service = new ChatService(conversations, messages, null, users, client,
            mock(SseEmitterManager.class), null, null, memories, null, null);

    void send(Map<String, String> memory) {
        Conversation conv = new Conversation();
        conv.setId(7L); conv.setUserId(1L); conv.setStatus("ACTIVE"); conv.setMessageCount(0);
        User user = new User(); user.setNickname("账号昵称");
        when(conversations.selectById(7L)).thenReturn(conv);
        when(users.selectById(1L)).thenReturn(user);
        when(memories.getMemoriesDto(1L)).thenReturn(memory.entrySet().stream()
                .map(entry -> Map.of("category", "IDENTITY", "key", entry.getKey(), "value", entry.getValue()))
                .toList());
        when(messages.selectRecent(7L, 10)).thenReturn(new ArrayList<>());
        when(client.streamChat(anyMap())).thenReturn(Flux.empty());
        ChatDtos.SendMessageRequest request = new ChatDtos.SendMessageRequest();
        request.setConversationId(7L); request.setContent("退款多久能到账？");
        service.sendMessage(1L, request);
    }

    @Test void accountNicknameIsNotFabricatedAsAnExplicitConversationalName() {
        send(Map.of());
        verify(client).streamChat(argThat(body -> {
            Map<?, ?> profile = (Map<?, ?>) body.get("user_profile");
            assertThat(profile.get("nickname")).isEqualTo("账号昵称");
            assertThat(profile.containsKey("user_name")).isFalse();
            return true;
        }));
    }

    @Test void chatLoadsLongTermMemoryOnlyOnceForBothProfileAndContext() {
        send(Map.of("user_name", "旅行者"));
        verify(memories, times(1)).getMemoriesDto(1L);
        verify(memories, never()).getMemoryMap(anyLong());
    }

    @Test void gatewayTransportsExplicitNamesWithoutDuplicatingPythonNameRules() {
        send(Map.of("assistant_name", "专属购物助手", "user_name", "朋友"));
        verify(client).streamChat(argThat(body -> {
            Map<?, ?> profile = (Map<?, ?>) body.get("user_profile");
            assertThat(profile.get("assistant_name")).isEqualTo("专属购物助手");
            assertThat(profile.get("user_name")).isEqualTo("朋友");
            return true;
        }));
    }
    @Test void diagnosticEventIsPersistedButNeverForwardedToCustomer() {
        var trace=mock(AiTraceService.class); var recovery=mock(ChatStreamRecovery.class);
        var emitter=mock(org.springframework.web.servlet.mvc.method.annotation.SseEmitter.class);
        when(trace.begin(anyLong(),anyLong(),anyString())).thenReturn("bound-run");
        when(recovery.open(anyLong(),anyLong(),any(),anyString(),anyBoolean(),any(),anyBoolean()))
                .thenReturn(new ChatStreamRecovery.Ticket(emitter,false));
        service=new ChatService(conversations,messages,null,users,client,mock(SseEmitterManager.class),null,null,memories,recovery,trace);
        send(Map.of()); // Initialize a first offline attempt and shared conversation fixtures.
        clearInvocations(recovery,trace);
        when(client.streamChat(anyMap())).thenReturn(Flux.just(
            org.springframework.http.codec.ServerSentEvent.<String>builder("{\"traceId\":\"bound-run\",\"stages\":[]}").event("trace").build(),
            org.springframework.http.codec.ServerSentEvent.<String>builder("{\"content\":\"ok\"}").event("done").build()));
        var request=new ChatDtos.SendMessageRequest();request.setConversationId(7L);request.setContent("hello");service.sendMessage(1L,request);
        verify(trace).record(eq("bound-run"),contains("stages"));
        verify(recovery,never()).record(any(),eq("trace"),anyString());
        verify(client,atLeastOnce()).streamChat(argThat(body->"bound-run".equals(((Map<?,?>)body.get("options")).get("trace_id"))));
    }

}
