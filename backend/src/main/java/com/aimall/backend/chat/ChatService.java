package com.aimall.backend.chat;

import com.aimall.backend.common.BizException;
import com.aimall.backend.common.JsonUtil;
import com.aimall.backend.config.AppProperties;
import com.aimall.backend.entity.Conversation;
import com.aimall.backend.entity.Message;
import com.aimall.backend.entity.User;
import com.aimall.backend.mapper.ConversationMapper;
import com.aimall.backend.mapper.MessageMapper;
import com.aimall.backend.mapper.UserMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * 对话服务：消息持久化 + WebClient SSE 流代理（后端只透传事件，落库在本侧完成）
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ChatService {

    private final ConversationMapper conversationMapper;
    private final MessageMapper messageMapper;
    private final HumanHandoffService humanHandoffService;
    private final UserMapper userMapper;
    private final AiClient aiClient;
    private final SseEmitterManager sseEmitterManager;
    private final StringRedisTemplate redisTemplate;
    private final AppProperties props;
    private final FaqService faqService;

    private static final DateTimeFormatter NO_FMT = DateTimeFormatter.ofPattern("yyyyMMddHHmmss");

    /** 摘要压缩游标 Redis key 前缀：值 = 已并入摘要的最后一条消息 id */
    private static final String SUMMARY_CURSOR_KEY = "chat:sum:cu:";

    /** ⭐ 发送消息（SSE 流式）：鉴权/限流/落库 → WebClient 订阅 AI 流 → 逐事件透传 */
    public SseEmitter sendMessage(Long userId, ChatDtos.SendMessageRequest req) {
        Conversation conv = conversationMapper.selectById(req.getConversationId());
        if (conv == null || !conv.getUserId().equals(userId)) {
            throw new BizException(2003, "无权访问该会话");
        }
        if (!"ACTIVE".equals(conv.getStatus())) {
            throw new BizException(2004, "当前会话已转人工或已关闭，无法使用AI对话");
        }
        checkRateLimit(userId);

        // 1. 组装上下文（先取历史，再落库用户消息，避免当前消息重复进入 history）
        List<Message> recent = messageMapper.selectRecent(conv.getId(), 10);
        Collections.reverse(recent);
        List<Map<String, Object>> history = recent.stream()
                .filter(m -> List.of("USER", "AI", "AGENT").contains(m.getRole()))
                .map(m -> Map.<String, Object>of("role", "USER".equals(m.getRole()) ? "USER" : "AI",
                        "content", m.getContent() == null ? "" : m.getContent()))
                .toList();

        Message um = new Message();
        um.setConversationId(conv.getId());
        um.setRole("USER");
        um.setContent(req.getContent());
        um.setStatus("SUCCESS");
        messageMapper.insert(um);

        Conversation upd = new Conversation();
        upd.setId(conv.getId());
        upd.setMessageCount(conv.getMessageCount() + 1);
        if (conv.getTitle() == null || conv.getTitle().isBlank()) {
            String title = req.getContent().length() > 30 ? req.getContent().substring(0, 30) : req.getContent();
            upd.setTitle(title);
        }
        conversationMapper.updateById(upd);

        // 2. 会话摘要压缩（P1：消息数超 20 时后台刷新）
        maybeCompressSummary(conv);

        // ⚡ FAQ 关键词命中：直接返回固定答案，不调用 AI 服务
        String faqAnswer = faqService.match(req.getContent());
        if (faqAnswer != null) {
            SseEmitter emitter = new SseEmitter(60_000L);
            sseEmitterManager.register(userId, conv.getId(), emitter);
            try {
                sendEvent(emitter, "token", "{\"content\":\"" + escapeJson(faqAnswer) + "\"}");
                Message ai = saveAiMessage(conv, faqAnswer, Collections.emptyList(), null,
                        System.currentTimeMillis(), "SUCCESS");
                sendEvent(emitter, "done", "{\"content\":\"" + escapeJson(faqAnswer)
                        + "\",\"messageId\":" + ai.getId() + ",\"faq\":true}");
            } finally {
                completeQuietly(emitter);
                sseEmitterManager.remove(userId, conv.getId());
            }
            return emitter;
        }

        User user = userMapper.selectById(userId);
        Map<String, Object> body = new HashMap<>();
        body.put("conversation_id", conv.getId());
        body.put("user_id", userId);
        body.put("message", req.getContent());
        body.put("history", history);
        body.put("summary", conv.getSummary());
        body.put("web_search_enabled", Boolean.TRUE.equals(req.getWebSearchEnabled()));
        body.put("user_profile", Map.of("nickname", user != null ? user.getNickname() : ""));

        // 3. SSE 代理
        SseEmitter emitter = new SseEmitter(300_000L);
        sseEmitterManager.register(userId, conv.getId(), emitter);

        StringBuilder contentBuf = new StringBuilder();
        List<Map<String, Object>> toolCalls = Collections.synchronizedList(new ArrayList<>());
        AtomicBoolean finished = new AtomicBoolean(false);
        long start = System.currentTimeMillis();

        aiClient.streamChat(body)
                .doOnNext(evt -> {
                    String name = evt.event() == null ? "message" : evt.event();
                    String data = evt.data() == null ? "" : evt.data();
                    handleEvent(name, data, conv, emitter, contentBuf, toolCalls, finished, start);
                })
                .doOnComplete(() -> {
                    if (!finished.get()) {
                        // 异常：流结束但未收到 done/error
                        saveAiMessage(conv, contentBuf.toString(), toolCalls, null, start, "SUCCESS");
                        sendEvent(emitter, "error",
                                "{\"code\":5001,\"message\":\"AI 响应异常中断\"}");
                        completeQuietly(emitter);
                    }
                })
                .doOnError(e -> {
                    log.warn("ai stream error: {}", e.getMessage());
                    if (!finished.get()) {
                        String msg = "{\"code\":5001,\"message\":\"AI 服务调用失败，请稍后重试\"}";
                        sendEvent(emitter, "error", msg);
                        saveAiMessage(conv, contentBuf.toString(), toolCalls, null, start, "FAILED");
                        completeQuietly(emitter);
                    }
                })
                .doFinally(sig -> sseEmitterManager.remove(userId, conv.getId()))
                .subscribe();
        return emitter;
    }

    private void handleEvent(String name, String data, Conversation conv, SseEmitter emitter,
                             StringBuilder contentBuf, List<Map<String, Object>> toolCalls,
                             AtomicBoolean finished, long start) {
        try {
            switch (name) {
                case "token" -> {
                    JsonNode node = JsonUtil.parse(data);
                    if (node != null && node.hasNonNull("content")) {
                        contentBuf.append(node.get("content").asText());
                    }
                    sendEvent(emitter, name, data);
                }
                case "tool_call", "tool_result", "action" -> {
                    toolCalls.add(JsonUtil.toMap(data));
                    sendEvent(emitter, name, data);
                }
                case "done" -> {
                    JsonNode node = JsonUtil.parse(data);
                    // 优先使用 done.content（link_guard 后验后的文本）
                    String content = node != null && node.hasNonNull("content")
                            ? node.get("content").asText() : contentBuf.toString();
                    boolean degraded = node != null && node.path("degraded").asBoolean(false);
                    Message ai = saveAiMessage(conv, content, toolCalls, node, start,
                            degraded ? "DEGRADED" : "SUCCESS");
                    // 转人工工具检测 → 会话进入人工队列
                    boolean escalated = toolCalls.stream()
                            .anyMatch(t -> String.valueOf(t.get("tool")).contains("escalate"));
                    if (escalated) {
                        Conversation c = new Conversation();
                        c.setId(conv.getId());
                        c.setStatus("PENDING_HUMAN");
                        conversationMapper.updateById(c);
                    }
                    sendEvent(emitter, "done", JsonUtil.putField(data, "messageId", ai.getId()));
                    finished.set(true);
                    completeQuietly(emitter);
                }
                case "error" -> {
                    saveAiMessage(conv, contentBuf.toString(), toolCalls, null, start, "FAILED");
                    sendEvent(emitter, "error", data);
                    finished.set(true);
                    completeQuietly(emitter);
                }
                default -> { /* 其他事件忽略 */ }
            }
        } catch (Exception e) {
            log.warn("handle sse event failed: {}", e.getMessage());
        }
    }

    private Message saveAiMessage(Conversation conv, String content, List<Map<String, Object>> toolCalls,
                                  JsonNode doneNode, long start, String status) {
        Message ai = new Message();
        ai.setConversationId(conv.getId());
        ai.setRole("AI");
        ai.setContent(content == null || content.isBlank() ? "(无内容)" : content);
        if (!toolCalls.isEmpty()) {
            ai.setToolCalls(JsonUtil.write(toolCalls));
        }
        if (doneNode != null && doneNode.has("tokenUsage")) {
            ai.setTokenUsage(doneNode.get("tokenUsage").toString());
        }
        ai.setLatencyMs((int) (System.currentTimeMillis() - start));
        ai.setStatus(status);
        messageMapper.insert(ai);

        Conversation upd = new Conversation();
        upd.setId(conv.getId());
        upd.setMessageCount(conv.getMessageCount() + 2);
        conversationMapper.updateById(upd);
        return ai;
    }

    /** JSON 字符串转义（FAQ 固定答案含引号/换行时保证 SSE data 合法） */
    private String escapeJson(String s) {
        return JsonUtil.write(s == null ? "" : s).replaceAll("^\"|\"$", "");
    }

    private void sendEvent(SseEmitter emitter, String name, String data) {
        try {
            // 与心跳线程串行化，避免并发写损坏 chunked 流（ERR_INCOMPLETE_CHUNKED_ENCODING 根因）
            synchronized (emitter) {
                emitter.send(SseEmitter.event().name(name).data(data));
            }
        } catch (Exception e) {
            // 客户端断开等：忽略（emitter 清理由回调负责）
        }
    }

    private void completeQuietly(SseEmitter emitter) {
        try {
            synchronized (emitter) {
                emitter.complete();
            }
        } catch (Exception ignore) {
        }
    }

    private void checkRateLimit(Long userId) {
        try {
            String key = "chat:rl:" + userId;
            Long n = redisTemplate.opsForValue().increment(key);
            if (n != null && n == 1) {
                redisTemplate.expire(key, 60, TimeUnit.SECONDS);
            }
            if (n != null && n > props.getChat().getRateLimit()) {
                throw new BizException(1005, "发送过于频繁，请稍后再试");
            }
        } catch (BizException e) {
            throw e;
        } catch (Exception ignore) {
            // Redis 不可用时 fail-open
        }
    }

    private void maybeCompressSummary(Conversation conv) {
        // 旧实现固定取最老 20 条：窗口永不前进、每条消息重复调 LLM、摘要漂移。
        // 改为游标（已压缩的最后一条消息 id，存 Redis）→ 只压缩游标之后的新消息，
        // 攒够一窗（10 条）才调一次 LLM，游标随成功回调推进，窗口持续前进。
        if (conv.getMessageCount() == null || conv.getMessageCount() <= 20) {
            return; // 前 20 条由实时 history 窗口承担，无需压缩
        }
        long cursor = getSummaryCursor(conv.getId());
        if (cursor < 0) {
            return; // Redis 不可用：跳过压缩（fail-open，不影响主流程）
        }
        try {
            List<Message> pending = messageMapper.selectList(new LambdaQueryWrapper<Message>()
                    .eq(Message::getConversationId, conv.getId())
                    .gt(Message::getId, cursor)
                    .in(Message::getRole, List.of("USER", "AI", "AGENT"))
                    .orderByAsc(Message::getId)
                    .last("LIMIT 20"));
            if (pending.size() < 10) {
                return; // 新消息不足一窗，不重复调 LLM
            }
            List<Map<String, Object>> msgs = pending.stream()
                    .map(m -> Map.<String, Object>of("role", m.getRole(),
                            "content", m.getContent() == null ? "" : m.getContent()))
                    .toList();
            Map<String, Object> body = Map.of(
                    "old_summary", conv.getSummary() == null ? "" : conv.getSummary(),
                    "messages", msgs);
            long lastId = pending.get(pending.size() - 1).getId();
            aiClient.summarize(body).subscribe(s -> {
                if (s != null && !s.isBlank()) {
                    Conversation upd = new Conversation();
                    upd.setId(conv.getId());
                    upd.setSummary(s);
                    conversationMapper.updateById(upd);
                    saveSummaryCursor(conv.getId(), lastId); // 摘要成功后游标前进
                }
            });
        } catch (Exception ignore) {
            // 摘要压缩失败不影响主流程
        }
    }

    private long getSummaryCursor(Long conversationId) {
        try {
            String v = redisTemplate.opsForValue().get(SUMMARY_CURSOR_KEY + conversationId);
            return v == null ? 0L : Long.parseLong(v);
        } catch (Exception e) {
            return -1L;
        }
    }

    private void saveSummaryCursor(Long conversationId, long msgId) {
        try {
            redisTemplate.opsForValue().set(SUMMARY_CURSOR_KEY + conversationId, String.valueOf(msgId));
        } catch (Exception ignore) {
        }
    }

    // ---------- 会话管理 ----------

    public Conversation createConversation(Long userId) {
        Conversation conv = new Conversation();
        conv.setConvNo("C" + LocalDateTime.now().format(NO_FMT)
                + String.format("%03d", new Random().nextInt(1000)));
        conv.setUserId(userId);
        conv.setStatus("ACTIVE");
        conv.setMessageCount(0);
        conversationMapper.insert(conv);
        return conv;
    }

    public Page<Conversation> myConversations(Long userId, long page, long size) {
        humanHandoffService.expireAll();
        return conversationMapper.selectPage(new Page<>(page, size),
                new LambdaQueryWrapper<Conversation>()
                        .eq(Conversation::getUserId, userId)
                        .orderByDesc(Conversation::getUpdatedAt));
    }

    public Conversation requireOwned(Long userId, Long conversationId) {
        humanHandoffService.expire(conversationId);
        Conversation conv = conversationMapper.selectById(conversationId);
        if (conv == null || !conv.getUserId().equals(userId)) {
            throw new BizException(2003, "无权访问该会话");
        }
        return conv;
    }

    public void close(Long userId, Long conversationId) {
        Conversation conv = requireOwned(userId, conversationId);
        if ("CLOSED".equals(conv.getStatus())) {
            return;
        }
        Conversation upd = new Conversation();
        upd.setId(conv.getId());
        upd.setStatus("CLOSED");
        conversationMapper.updateById(upd);
    }

    public void cancelHuman(Long userId, Long conversationId) {
        humanHandoffService.cancel(userId, conversationId);
    }

    public java.time.LocalDateTime humanWaitExpiresAt(Conversation conversation) {
        return humanHandoffService.expiresAt(conversation);
    }
    public void satisfaction(Long userId, Long conversationId, Integer score) {
        Conversation conv = requireOwned(userId, conversationId);
        if (!"CLOSED".equals(conv.getStatus())) {
            throw new BizException(2004, "会话结束后才能评价");
        }
        Conversation upd = new Conversation();
        upd.setId(conv.getId());
        upd.setSatisfaction(score);
        conversationMapper.updateById(upd);
    }

    public Page<Message> messages(Long userId, Long conversationId, long page, long size) {
        requireOwned(userId, conversationId);
        return messageMapper.selectPage(new Page<>(page, size),
                new LambdaQueryWrapper<Message>()
                        .eq(Message::getConversationId, conversationId)
                        .orderByDesc(Message::getId));
    }

    public List<Message> messagesAfter(Long userId, Long conversationId, Long afterId) {
        requireOwned(userId, conversationId);
        return messageMapper.selectAfter(conversationId, afterId);
    }

    /** 人工服务中（SERVICING）买家发消息：仅落库 USER 消息，AI 完全旁路 */
    public void humanMessage(Long userId, Long conversationId, String content) {
        Conversation conv = requireOwned(userId, conversationId);
        if (!"SERVICING".equals(conv.getStatus())) {
            throw new BizException(2004, "当前无人工客服服务中，无法发送消息");
        }
        Message msg = new Message();
        msg.setConversationId(conv.getId());
        msg.setRole("USER");
        msg.setContent(content);
        msg.setStatus("SUCCESS");
        messageMapper.insert(msg);
        Conversation upd = new Conversation();
        upd.setId(conv.getId());
        upd.setMessageCount(conv.getMessageCount() + 1);
        conversationMapper.updateById(upd);
    }

    /** 会话状态 VO：转人工后前端轮询（感知客服接入/服务结束） */
    public Map<String, Object> statusVo(Long userId, Long conversationId) {
        Conversation conv = requireOwned(userId, conversationId);
        Map<String, Object> vo = new HashMap<>();
        vo.put("conversationId", conv.getId());
        vo.put("status", conv.getStatus());
        vo.put("updatedAt", conv.getUpdatedAt() == null ? "" : conv.getUpdatedAt().toString());
        vo.put("humanWaitExpiresAt", humanHandoffService.expiresAt(conv));
        return vo;
    }
}
