package com.aimall.backend.chat;

import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.Conversation;
import com.aimall.backend.mapper.ConversationMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.Objects;

/** Owns the atomic state transitions for the one-minute human-agent waiting window. */
@Service
public class HumanHandoffService {

    private final ConversationMapper conversationMapper;
    private final long timeoutSeconds;

    public HumanHandoffService(ConversationMapper conversationMapper,
                               @Value("${app.chat.human-wait-timeout-seconds:60}") long timeoutSeconds) {
        this.conversationMapper = conversationMapper;
        this.timeoutSeconds = timeoutSeconds;
    }

    public void expireAll() {
        conversationMapper.expirePendingBefore(deadline());
    }

    public void expire(Long conversationId) {
        conversationMapper.expirePending(conversationId, deadline());
    }

    public boolean cancel(Long userId, Long conversationId) {
        if (conversationMapper.cancelPending(conversationId, userId) == 1) {
            return true;
        }
        Conversation conversation = conversationMapper.selectById(conversationId);
        if (conversation == null || !Objects.equals(userId, conversation.getUserId())) {
            throw new BizException(2003, "无权访问该会话");
        }
        if ("SERVICING".equals(conversation.getStatus())) {
            throw new BizException(2004, "客服已接入，无法取消转人工");
        }
        return false;
    }

    public void claim(Long agentId, Long conversationId) {
        LocalDateTime deadline = deadline();
        if (conversationMapper.claim(conversationId, agentId, deadline) != 1) {
            conversationMapper.expirePending(conversationId, deadline);
            throw new BizException(2004, "会话已取消、超时或被其他客服接入");
        }
    }

    public LocalDateTime expiresAt(Conversation conversation) {
        if (conversation == null || !"PENDING_HUMAN".equals(conversation.getStatus())
                || conversation.getUpdatedAt() == null) {
            return null;
        }
        return conversation.getUpdatedAt().plusSeconds(timeoutSeconds);
    }

    private LocalDateTime deadline() {
        return LocalDateTime.now().minusSeconds(timeoutSeconds);
    }
}
