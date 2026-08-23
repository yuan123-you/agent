package com.aimall.backend.workbench;

import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.Conversation;
import com.aimall.backend.entity.Message;
import com.aimall.backend.entity.User;
import com.aimall.backend.mapper.ConversationMapper;
import com.aimall.backend.mapper.MessageMapper;
import com.aimall.backend.mapper.UserMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 客服工作台服务：待接入列表 / 抢占式接管 / 人工回复 / 结束服务
 */
@Service
@RequiredArgsConstructor
public class WorkbenchService {

    private final ConversationMapper conversationMapper;
    private final MessageMapper messageMapper;
    private final UserMapper userMapper;

    /** SLA 看板指标 */
    public Map<String, Object> sla() {
        LocalDate today = LocalDate.now();
        Map<String, Object> vo = new HashMap<>();
        vo.put("pendingCount", conversationMapper.countByStatus("PENDING_HUMAN"));
        vo.put("servicingCount", conversationMapper.countByStatus("SERVICING"));
        vo.put("todayNewCount", conversationMapper.countToday(today.atStartOfDay()));
        vo.put("todayHandledCount", conversationMapper.countHandled(today.atStartOfDay()));
        Long avgFirst = conversationMapper.avgFirstResponseSeconds();
        vo.put("avgFirstResponseSeconds", avgFirst == null ? 0L : avgFirst);
        return vo;
    }

    public List<Conversation> pending() {
        return conversationMapper.selectList(new LambdaQueryWrapper<Conversation>()
                .eq(Conversation::getStatus, "PENDING_HUMAN")
                .orderByAsc(Conversation::getUpdatedAt));
    }

    public List<Conversation> servicing(Long agentId) {
        return conversationMapper.selectList(new LambdaQueryWrapper<Conversation>()
                .eq(Conversation::getStatus, "SERVICING")
                .eq(Conversation::getAgentId, agentId)
                .orderByDesc(Conversation::getUpdatedAt));
    }

    /** 抢占式接管：仅 PENDING_HUMAN 可接（防双客服同接） */
    public void claim(Long agentId, Long conversationId) {
        if (conversationMapper.claim(conversationId, agentId) != 1) {
            throw new BizException(2004, "会话已被其他客服接入或状态已变更");
        }
    }

    public void sendMessage(Long agentId, Long conversationId, String content) {
        Conversation conv = requireServicing(agentId, conversationId);
        Message msg = new Message();
        msg.setConversationId(conv.getId());
        msg.setRole("AGENT");
        msg.setContent(content);
        msg.setStatus("SUCCESS");
        messageMapper.insert(msg);

        Conversation upd = new Conversation();
        upd.setId(conv.getId());
        upd.setMessageCount(conv.getMessageCount() + 1);
        conversationMapper.updateById(upd);
    }

    public void finish(Long agentId, Long conversationId) {
        Conversation conv = requireServicing(agentId, conversationId);
        Conversation upd = new Conversation();
        upd.setId(conv.getId());
        upd.setStatus("CLOSED");
        conversationMapper.updateById(upd);
    }

    public List<Message> history(Long conversationId) {
        return messageMapper.selectList(new LambdaQueryWrapper<Message>()
                .eq(Message::getConversationId, conversationId)
                .orderByAsc(Message::getId));
    }

    /** 会话状态（客服端轮询感知买家结束会话）；仅本人服务中或已结束的会话可见 */
    public Map<String, Object> statusVo(Long agentId, Long conversationId) {
        Conversation conv = conversationMapper.selectById(conversationId);
        if (conv == null) {
            throw new BizException(2002, "会话不存在");
        }
        if (!"CLOSED".equals(conv.getStatus()) && !agentId.equals(conv.getAgentId())) {
            throw new BizException(2004, "会话不在您的服务中");
        }
        Map<String, Object> vo = new HashMap<>();
        vo.put("conversationId", conv.getId());
        vo.put("status", conv.getStatus());
        return vo;
    }

    public String userNickname(Long userId) {
        User user = userMapper.selectById(userId);
        return user != null ? user.getNickname() : "-";
    }

    private Conversation requireServicing(Long agentId, Long conversationId) {
        Conversation conv = conversationMapper.selectById(conversationId);
        if (conv == null) {
            throw new BizException(2002, "会话不存在");
        }
        if (!"SERVICING".equals(conv.getStatus()) || !agentId.equals(conv.getAgentId())) {
            throw new BizException(2004, "会话不在您的服务中");
        }
        return conv;
    }
}
