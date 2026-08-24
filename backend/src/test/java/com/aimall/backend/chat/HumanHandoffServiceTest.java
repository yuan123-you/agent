package com.aimall.backend.chat;

import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.Conversation;
import com.aimall.backend.mapper.ConversationMapper;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class HumanHandoffServiceTest {

    private final ConversationMapper conversationMapper = mock(ConversationMapper.class);
    private final HumanHandoffService service = new HumanHandoffService(conversationMapper, 60);

    @Test
    void cancelReturnsConversationToAiWhileItIsStillPending() {
        when(conversationMapper.cancelPending(7L, 3L)).thenReturn(1);

        assertThat(service.cancel(3L, 7L)).isTrue();
    }

    @Test
    void cancelCannotOverrideAnAgentWhoAlreadyClaimedTheConversation() {
        Conversation servicing = conversation(7L, 3L, "SERVICING", LocalDateTime.now());
        when(conversationMapper.cancelPending(7L, 3L)).thenReturn(0);
        when(conversationMapper.selectById(7L)).thenReturn(servicing);

        assertThatThrownBy(() -> service.cancel(3L, 7L))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("客服已接入");
    }

    @Test
    void claimRejectsAConversationThatReachedItsDeadline() {
        when(conversationMapper.claim(any(), any(), any())).thenReturn(0);

        assertThatThrownBy(() -> service.claim(9L, 7L))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("已取消、超时或被其他客服接入");
    }

    @Test
    void pendingDeadlineIsOneMinuteAfterTheRequestStarted() {
        LocalDateTime requestedAt = LocalDateTime.of(2026, 8, 24, 10, 0, 0);
        Conversation pending = conversation(7L, 3L, "PENDING_HUMAN", requestedAt);

        assertThat(service.expiresAt(pending)).isEqualTo(requestedAt.plusMinutes(1));
        assertThat(service.expiresAt(conversation(7L, 3L, "ACTIVE", requestedAt))).isNull();
    }

    private static Conversation conversation(Long id, Long userId, String status, LocalDateTime updatedAt) {
        Conversation conversation = new Conversation();
        conversation.setId(id);
        conversation.setUserId(userId);
        conversation.setStatus(status);
        conversation.setUpdatedAt(updatedAt);
        return conversation;
    }
}
