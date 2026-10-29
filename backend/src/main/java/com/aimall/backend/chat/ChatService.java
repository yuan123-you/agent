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
    private final UserMemoryService userMemoryService;
    private final ChatStreamRecovery recovery;
    private final AiTraceService traceService;

    private static final DateTimeFormatter NO_FMT = DateTimeFormatter.ofPattern("yyyyMMddHHmmss");

    /** 摘要压缩游标 Redis key 前缀：值 = 已并入摘要的最后一条消息 id */
    private static final String SUMMARY_CURSOR_KEY = "chat:sum:cu:";

    /** ⭐ 发送消息（SSE 流式）：鉴权/限流/落库 → WebClient 订阅 AI 流 → 逐事件透传 */
    public SseEmitter sendMessage(Long userId, ChatDtos.SendMessageRequest req) {
        Conversation conv = conversationMapper.selectById(req.getConversationId());
        if (conv == null || !conv.getUserId().equals(userId)) {
            throw new BizException(2003, "无权访问该会话");
        }
        ChatStreamRecovery.Ticket ticket = recovery != null
                ? recovery.open(userId, conv.getId(), req.getRequestId(), req.getContent(),
                    Boolean.TRUE.equals(req.getWebSearchEnabled()), req.getRetryMessageId(), Boolean.TRUE.equals(req.getResumeOnly()))
                : new ChatStreamRecovery.Ticket(new SseEmitter(300_000L), false);
        if (ticket.replay()) return ticket.emitter();
        String traceId = traceService != null ? traceService.begin(userId,conv.getId(),req.getContent()) : null;
        AtomicBoolean accepted = new AtomicBoolean(false);
        try {
            return startMessage(userId, req, conv, ticket.emitter(), accepted, traceId);
        } catch (RuntimeException e) {
            int code = e instanceof BizException biz ? biz.getCode()
                    : e instanceof ChatStreamRecovery.RecordingException ? 5003 : 5001;
            if (accepted.get()) {
                failStream(conv, ticket.emitter(), new StringBuilder(), Collections.emptyList(),
                        System.currentTimeMillis(), code, "暂时无法完成回复", traceId);
            } else {
                finishTrace(traceId,null,"FAILED");
                signalFailure(ticket.emitter(), code, null, "暂时无法完成回复");
                if (req.getRequestId() == null) throw e;
            }
            return ticket.emitter();
        }
    }

    private SseEmitter startMessage(Long userId, ChatDtos.SendMessageRequest req, Conversation conv,
                                    SseEmitter emitter, AtomicBoolean accepted, String traceId) {
        if (!"ACTIVE".equals(conv.getStatus())) {
            throw new BizException(2004, "当前会话已转人工或已关闭，无法使用AI对话");
        }
        checkRateLimit(userId);

        // 1. 组装上下文（先取历史，再落库用户消息，避免当前消息重复进入 history）
        List<Message> recent = messageMapper.selectRecent(conv.getId(), 10);
        Collections.reverse(recent);
        if (req.getRetryMessageId() != null) {
            Message failed = recent.isEmpty() ? null : recent.get(recent.size() - 1);
            if (failed == null || !req.getRetryMessageId().equals(failed.getId())
                    || !"AI".equals(failed.getRole()) || !"FAILED".equals(failed.getStatus())) {
                throw new BizException(2005, "只能重新生成最新一条未完成的回复");
            }
            JsonNode savedTools = JsonUtil.parse(failed.getToolCalls());
            if (savedTools != null && savedTools.findValuesAsText("tool").stream().anyMatch(
                    Set.of("order_create", "order_cancel_prepare", "after_sale_prepare", "escalate_to_human")::contains)) {
                throw new BizException(2005, "请先核对已有操作卡片或订单状态，避免重复提交");
            }
            int userIndex = recent.size() - 2;
            while (userIndex >= 0 && !"USER".equals(recent.get(userIndex).getRole())) userIndex--;
            if (userIndex < 0 || !req.getContent().equals(recent.get(userIndex).getContent())) {
                throw new BizException(2005, "原问题不匹配，请重新提问");
            }
            recent = new ArrayList<>(recent.subList(0, userIndex));
            accepted.set(true);
        }
        List<Map<String, Object>> history = recent.stream()
                .filter(m -> List.of("USER", "AI", "AGENT").contains(m.getRole()))
                .map(m -> Map.<String, Object>of("role", "USER".equals(m.getRole()) ? "USER" : "AI",
                        "content", m.getContent() == null ? "" : m.getContent()))
                .toList();

        if (req.getRetryMessageId() == null) {
            Message um = new Message();
            um.setConversationId(conv.getId());
            um.setRole("USER");
            um.setContent(req.getContent());
            um.setStatus("SUCCESS");
            messageMapper.insert(um);
            accepted.set(true);
            conv.setMessageCount(conv.getMessageCount() + 1);

            Conversation upd = new Conversation();
            upd.setId(conv.getId());
            upd.setMessageCount(conv.getMessageCount());
            if (conv.getTitle() == null || conv.getTitle().isBlank()) {
                String title = req.getContent().length() > 30 ? req.getContent().substring(0, 30) : req.getContent();
                upd.setTitle(title);
            }
            conversationMapper.updateById(upd);
        }

        // 2. 会话摘要压缩（P1：消息数超 20 时后台刷新）
        maybeCompressSummary(conv);

        User user = userMapper.selectById(userId);
        // One memory snapshot serves both profile and evidence; do not query the same rows twice.
        List<Map<String, String>> longTermMemory = userMemoryService != null
                ? userMemoryService.getMemoriesDto(userId) : Collections.emptyList();
        Map<String, Object> userProfile = new HashMap<>();
        String nickname = user != null && user.getNickname() != null ? user.getNickname().trim() : "";
        userProfile.put("nickname", nickname);
        for (Map<String, String> memory : longTermMemory) {
            String key = memory.get("key");
            String value = memory.get("value");
            if (key != null && value != null) userProfile.put(key, value);
        }

        Map<String, Object> body = new HashMap<>();
        body.put("conversation_id", conv.getId());
        body.put("user_id", userId);
        body.put("message", req.getContent());
        body.put("history", history);
        Map<String,Object> options=new HashMap<>();
        options.put("regenerate",req.getRetryMessageId()!=null);
        if (traceId!=null) options.put("trace_id",traceId);
        body.put("options",options);
        body.put("summary", conv.getSummary());
        body.put("web_search_enabled", Boolean.TRUE.equals(req.getWebSearchEnabled()));
        body.put("user_profile", userProfile);
        body.put("long_term_memory", longTermMemory);

        // 3. SSE 代理
        sseEmitterManager.register(userId, conv.getId(), emitter);

        StringBuilder contentBuf = new StringBuilder();
        List<Map<String, Object>> toolCalls = Collections.synchronizedList(new ArrayList<>());
        AtomicBoolean finished = new AtomicBoolean(false);
        long start = System.currentTimeMillis();

        aiClient.streamChat(body)
                .take(java.time.Duration.ofSeconds(240))
                .doOnNext(evt -> {
                    String name = evt.event() == null ? "message" : evt.event();
                    String data = evt.data() == null ? "" : evt.data();
                    handleEvent(name, data, conv, emitter, contentBuf, toolCalls, finished, start, traceId);
                })
                .doOnComplete(() -> {
                    if (finished.compareAndSet(false, true)) {
                        failStream(conv, emitter, contentBuf, toolCalls, start, 5002, "回复未能完成", traceId);
                    }
                })
                .doOnError(e -> {
                    log.warn("ai stream error: {}", e.getClass().getSimpleName());
                    if (finished.compareAndSet(false, true)) {
                        int code = e instanceof ChatStreamRecovery.RecordingException ? 5003 : 5001;
                        failStream(conv, emitter, contentBuf, toolCalls, start, code, "AI 服务暂时不可用", traceId);
                    }
                })
                .onErrorResume(e -> reactor.core.publisher.Flux.empty())
                .doFinally(sig -> {
                    if (!finished.get()) finishTrace(traceId,null,"FAILED");
                    sseEmitterManager.remove(userId, conv.getId(), emitter);
                })
                .subscribe();
        return emitter;
    }

    private void handleEvent(String name, String data, Conversation conv, SseEmitter emitter,
                             StringBuilder contentBuf, List<Map<String, Object>> toolCalls,
                             AtomicBoolean finished, long start, String traceId) {
        if (finished.get()) return;
        try {
            switch (name) {
                case "trace" -> {
                    // Diagnostics never enter customer SSE, message content or recovery replay.
                    if (traceService != null) traceService.record(traceId,data);
                }
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
                    if (node != null && node.path("timedOut").asBoolean(false)) {
                        finished.set(true);
                        failStream(conv, emitter, new StringBuilder(content), toolCalls, start, 5002, "回复等待超时", traceId);
                        return;
                    }
                    boolean degraded = node != null && node.path("degraded").asBoolean(false);
                    Message ai = saveAiMessage(conv, content, toolCalls, node, start,
                            degraded ? "DEGRADED" : "SUCCESS");
                    finishTrace(traceId,ai.getId(),degraded ? "DEGRADED" : "SUCCESS");
                    // 转人工状态由 /internal/tools/escalate 更新；流结束不得覆盖取消、接入或关闭状态。
                    sendEvent(emitter, "done", JsonUtil.putField(data, "messageId", ai.getId()));
                    finished.set(true);
                    completeQuietly(emitter);
                }
                case "error" -> {
                    Message failed = saveAiMessage(conv, contentBuf.toString(), toolCalls, null, start, "FAILED");
                    finishTrace(traceId,failed.getId(),"FAILED");
                    sendEvent(emitter, "error", JsonUtil.putField(data, "messageId", failed.getId()));
                    finished.set(true);
                    completeQuietly(emitter);
                }
                default -> { /* 其他事件忽略 */ }
            }
        } catch (Exception e) {
            // Persistence failures cancel the upstream subscription; only socket disconnects are ignorable.
            throw e instanceof RuntimeException runtime ? runtime : new IllegalStateException(e);
        }
    }

    private void failStream(Conversation conv, SseEmitter emitter, StringBuilder content,
                            List<Map<String, Object>> tools, long start, int code, String message, String traceId) {
        Message failed = null;
        try {
            failed = saveAiMessage(conv, content.toString(), tools, null, start, "FAILED");
        } catch (RuntimeException e) {
            log.warn("failed to persist interrupted reply: {}", e.getClass().getSimpleName());
            code = 5003;
        }
        finishTrace(traceId,failed == null ? null : failed.getId(),"FAILED");
        signalFailure(emitter, code, failed == null ? null : failed.getId(), message);
    }

    private void finishTrace(String traceId, Long messageId, String status) {
        if (traceService != null) traceService.finish(traceId,messageId,status);
    }

    private void signalFailure(SseEmitter emitter, int code, Long messageId, String message) {
        String data = JsonUtil.write(Map.of("code", code, "message", message,
                "messageId", messageId == null ? 0L : messageId));
        try {
            sendEvent(emitter, "error", data);
        } catch (RuntimeException e) {
            // Durable recovery is unavailable; still terminate the socket with actionable feedback.
            sendSocketEvent(emitter, "error", JsonUtil.write(Map.of("code", 5003,
                    "message", "暂时无法恢复连接", "messageId", messageId == null ? 0L : messageId)));
        } finally {
            completeQuietly(emitter);
        }
    }

    private Message saveAiMessage(Conversation conv, String content, List<Map<String, Object>> toolCalls,
                                  JsonNode doneNode, long start, String status) {
        Message ai = new Message();
        ai.setConversationId(conv.getId());
        ai.setRole("AI");
        ai.setContent(content == null ? "" : content);
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
        upd.setMessageCount(conv.getMessageCount() + 1);
        conversationMapper.updateById(upd);
        return ai;
    }

    /** JSON 字符串转义（FAQ 固定答案含引号/换行时保证 SSE data 合法） */
    private String escapeJson(String s) {
        return JsonUtil.write(s == null ? "" : s).replaceAll("^\"|\"$", "");
    }

    private void sendEvent(SseEmitter emitter, String name, String data) {
        if (recovery != null) recovery.record(emitter, name, data);
        sendSocketEvent(emitter, name, data);
    }

    private void sendSocketEvent(SseEmitter emitter, String name, String data) {
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
