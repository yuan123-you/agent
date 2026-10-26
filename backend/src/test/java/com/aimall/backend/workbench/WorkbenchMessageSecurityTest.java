package com.aimall.backend.workbench;

import com.aimall.backend.chat.HumanHandoffService;
import com.aimall.backend.common.GlobalExceptionHandler;
import com.aimall.backend.config.JwtService;
import com.aimall.backend.config.SecurityFilterTestConfig;
import com.aimall.backend.entity.Conversation;
import com.aimall.backend.entity.Message;
import com.aimall.backend.entity.User;
import com.aimall.backend.mapper.ConversationMapper;
import com.aimall.backend.mapper.MessageMapper;
import com.aimall.backend.mapper.UserMapper;
import jakarta.servlet.Filter;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.test.context.junit.jupiter.SpringJUnitConfig;
import org.springframework.test.context.web.WebAppConfiguration;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringJUnitConfig(WorkbenchMessageSecurityTest.Config.class)
@WebAppConfiguration
class WorkbenchMessageSecurityTest {
    private static final String MESSAGES_URL = "/api/v1/workbench/conversations/7/messages";

    @Configuration
    @Import({SecurityFilterTestConfig.class, WorkbenchController.class, WorkbenchService.class,
            GlobalExceptionHandler.class})
    static class Config {
        @Bean ConversationMapper conversationMapper() { return mock(ConversationMapper.class); }
        @Bean MessageMapper messageMapper() { return mock(MessageMapper.class); }
        @Bean HumanHandoffService humanHandoffService() { return mock(HumanHandoffService.class); }
    }

    @Autowired WebApplicationContext context;
    @Autowired @Qualifier("springSecurityFilterChain") Filter securityFilterChain;
    @Autowired JwtService jwtService;
    @Autowired UserMapper userMapper;
    @Autowired ConversationMapper conversations;
    @Autowired MessageMapper messages;
    @Autowired StringRedisTemplate redis;
    private MockMvc mvc;
    private Conversation conversation;

    @BeforeEach
    void setUp() {
        reset(userMapper, conversations, messages, redis);
        User viewer = new User();
        viewer.setId(42L);
        viewer.setStatus("ACTIVE");
        viewer.setDeleted(0);
        when(userMapper.selectById(42L)).thenReturn(viewer);
        conversation = new Conversation();
        conversation.setId(7L);
        conversation.setUserId(100L);
        conversation.setAgentId(42L);
        conversation.setStatus("SERVICING");
        when(conversations.selectById(7L)).thenReturn(conversation);
        Message message = new Message();
        message.setId(99L);
        message.setConversationId(7L);
        message.setRole("USER");
        message.setContent("private buyer message");
        when(messages.selectList(any())).thenReturn(List.of(message));
        mvc = MockMvcBuilders.webAppContextSetup(context).addFilters(securityFilterChain).build();
    }

    @ParameterizedTest
    @ValueSource(strings = {"AGENT", "ADMIN"})
    void assignedOperatorCanReadServicingConversation(String role) throws Exception {
        mvc.perform(get(MESSAGES_URL).header("Authorization", bearer(role)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data[0].conversationId").value(7))
                .andExpect(jsonPath("$.data[0].content").value("private buyer message"));
    }

    @ParameterizedTest
    @ValueSource(strings = {"AGENT", "ADMIN"})
    void otherOperatorCannotReadServicingConversation(String role) throws Exception {
        conversation.setAgentId(43L);
        expectDeniedWithoutReadingMessages(role);
    }

    @ParameterizedTest
    @ValueSource(strings = {"ACTIVE", "PENDING_HUMAN"})
    void unclaimedBuyerConversationCannotBeRead(String state) throws Exception {
        conversation.setStatus(state);
        conversation.setAgentId(null);
        expectDeniedWithoutReadingMessages("AGENT");
    }

    @Test
    void activeConversationCannotBeReadEvenWithStaleAgentAssignment() throws Exception {
        conversation.setStatus("ACTIVE");
        expectDeniedWithoutReadingMessages("AGENT");
    }

    @ParameterizedTest
    @ValueSource(strings = {"AGENT", "ADMIN"})
    void assignedOperatorCanStillPollMessagesAfterBuyerClosesConversation(String role) throws Exception {
        conversation.setStatus("CLOSED");
        mvc.perform(get(MESSAGES_URL).header("Authorization", bearer(role)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data[0].content").value("private buyer message"));
    }

    @ParameterizedTest
    @ValueSource(strings = {"AGENT", "ADMIN"})
    void otherOperatorCannotReadClosedConversation(String role) throws Exception {
        conversation.setStatus("CLOSED");
        conversation.setAgentId(43L);
        expectDeniedWithoutReadingMessages(role);
    }

    @Test
    void missingConversationReturnsNotFoundWithoutReadingMessages() throws Exception {
        when(conversations.selectById(7L)).thenReturn(null);
        mvc.perform(get(MESSAGES_URL).header("Authorization", bearer("AGENT")))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value(2002))
                .andExpect(jsonPath("$.data").isEmpty());
        verify(messages, never()).selectList(any());
    }

    @Test
    void anonymousRequestIsRejectedBySecurityFilterChain() throws Exception {
        mvc.perform(get(MESSAGES_URL)).andExpect(status().isUnauthorized());
        verifyNoInteractions(conversations);
    }

    @Test
    void customerCannotReadWorkbenchEvenWhenAgentIdMatches() throws Exception {
        mvc.perform(get(MESSAGES_URL).header("Authorization", bearer("CUSTOMER")))
                .andExpect(status().isForbidden());
        verifyNoInteractions(conversations);
    }

    private void expectDeniedWithoutReadingMessages(String role) throws Exception {
        mvc.perform(get(MESSAGES_URL).header("Authorization", bearer(role)))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value(2004))
                .andExpect(jsonPath("$.data").isEmpty());
        verify(messages, never()).selectList(any());
    }

    private String bearer(String role) {
        return "Bearer " + jwtService.createAccessToken(42L, role);
    }
}
