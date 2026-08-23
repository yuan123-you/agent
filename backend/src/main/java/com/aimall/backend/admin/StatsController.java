package com.aimall.backend.admin;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.common.JsonUtil;
import com.aimall.backend.mapper.ConversationMapper;
import com.aimall.backend.mapper.MessageMapper;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 使用统计（极简看板）：/api/v1/admin/stats（仅 ADMIN）
 */
@RestController
@RequestMapping("/api/v1/admin/stats")
@RequiredArgsConstructor
public class StatsController {

    private final ConversationMapper conversationMapper;
    private final MessageMapper messageMapper;

    @GetMapping("/overview")
    public ApiResponse<Map<String, Object>> overview() {
        LocalDateTime since = LocalDateTime.now().toLocalDate().atStartOfDay();
        Map<String, Object> data = new HashMap<>();
        data.put("todayConversationCount", conversationMapper.countToday(since));
        data.put("todayAiMessageCount", messageMapper.countTodayAi(since));

        // 热门问题 TOP10（用户消息前缀聚合）
        List<Map<String, Object>> topQuestions = messageMapper.topQuestions(since);
        List<Map<String, Object>> questions = new ArrayList<>();
        for (Map<String, Object> q : topQuestions) {
            Map<String, Object> item = new HashMap<>();
            item.put("keyword", String.valueOf(q.get("keyword")));
            item.put("count", ((Number) q.get("cnt")).intValue());
            questions.add(item);
        }
        data.put("topQuestions", questions);

        // 工具调用分布（按 callId 去重）
        data.put("aiToolCalls", aggregateToolCalls(messageMapper.selectTodayToolCalls(since)));
        return ApiResponse.ok(data);
    }

    /**
     * 质量维度（在线代理指标 + 趋势）：准确率/命中率的可观测代理，不止业务量。
     * 数据全部来自线上 message 表的运行指标：
     *   replySuccessRate  = AI 消息 SUCCESS 占比（回复质量代理）
     *   aiToolCallRatio   = 含工具调用的 AI 消息占比（工具调用正确率代理）
     *   tokenUsage        = 今日 prompt/completion/total 消耗
     *   trend             = 近 7 天按天分组的 成功/失败数 + 平均延迟
     */
    @GetMapping("/quality")
    public ApiResponse<Map<String, Object>> quality() {
        LocalDateTime since = LocalDateTime.now().toLocalDate().atStartOfDay();
        LocalDateTime trendSince = since.toLocalDate().atStartOfDay().minusDays(6);

        Map<String, Object> data = new HashMap<>();

        // 回复质量：AI 消息状态分布 + 成功率
        Map<String, Integer> statusCounts = aggregateStatusCounts(messageMapper.countTodayAiByStatus(since));
        long aiTotal = statusCounts.values().stream().mapToInt(Integer::intValue).sum();
        long success = statusCounts.getOrDefault("SUCCESS", 0);
        data.put("aiMessageCount", aiTotal);
        data.put("replySuccessRate", aiTotal == 0 ? 0.0 : round2(100.0 * success / aiTotal));
        data.put("statusCounts", statusCounts);

        // 工具调用率（在线可用 ratio；正确率离线由 eval 校准）
        data.put("aiToolCallRatio", round2(100.0 * messageMapper.countTodayAiWithTool(since)
                / Math.max(aiTotal, 1)));

        // Token 成本（回复质量/成本的直接代理）
        Map<String, Object> tokens = aggregateTokens(messageMapper.selectTodayTokenUsage(since));
        data.put("tokenUsage", tokens);

        // 近 7 天质量趋势：按天聚合 SUCCESS/失败数 + 平均延迟
        List<Map<String, Object>> trend = buildTrend(messageMapper.aiQualityTrend(trendSince));
        data.put("trend", trend);

        return ApiResponse.ok(data);
    }

    // ------------------------------------------------------------ 纯函数（便于单测）

    /** 将工具调用 JSON 记录聚合为 {tool: 计数}，按 callId 去重。 */
    static Map<String, Integer> aggregateToolCalls(List<String> rows) {
        Map<String, Integer> toolCalls = new HashMap<>();
        Set<String> seenCallIds = new HashSet<>();
        for (String json : rows) {
            JsonNode node = JsonUtil.parse(json);
            if (node == null || !node.isArray()) {
                continue;
            }
            for (JsonNode t : node) {
                String callId = t.path("callId").asText("");
                if (callId.isEmpty() || !seenCallIds.add(callId)) {
                    continue;
                }
                String tool = t.path("tool").asText("");
                if (!tool.isBlank()) {
                    toolCalls.merge(tool, 1, Integer::sum);
                }
            }
        }
        return toolCalls;
    }

    /** 将 AI 消息状态行聚合为 {status: 计数}。 */
    static Map<String, Integer> aggregateStatusCounts(List<Map<String, Object>> rows) {
        Map<String, Integer> counts = new HashMap<>();
        for (Map<String, Object> row : rows) {
            String status = String.valueOf(row.get("status"));
            int cnt = row.get("cnt") instanceof Number
                    ? ((Number) row.get("cnt")).intValue() : 0;
            counts.merge(status, cnt, Integer::sum);
        }
        return counts;
    }

    /** 汇总 token_usage JSON，返回 {prompt_tokens, completion_tokens, total_tokens}。 */
    static Map<String, Object> aggregateTokens(List<String> rows) {
        long prompt = 0, completion = 0;
        for (String json : rows) {
            JsonNode node = JsonUtil.parse(json);
            if (node == null || !node.isObject()) {
                continue;
            }
            prompt += node.path("prompt_tokens").asLong(0);
            completion += node.path("completion_tokens").asLong(0);
        }
        Map<String, Object> out = new HashMap<>();
        out.put("prompt_tokens", prompt);
        out.put("completion_tokens", completion);
        out.put("total_tokens", prompt + completion);
        return out;
    }

    /** 将近 7 天原始行转为按天分组的 {day, success, failed, degraded, avgLatencyMs}。 */
    static List<Map<String, Object>> buildTrend(List<Map<String, Object>> rows) {
        Map<String, Map<String, Object>> byDay = new java.util.LinkedHashMap<>();
        for (Map<String, Object> row : rows) {
            String day = String.valueOf(row.get("day"));
            String status = String.valueOf(row.get("status"));
            int cnt = row.get("cnt") instanceof Number ? ((Number) row.get("cnt")).intValue() : 0;
            Map<String, Object> item = byDay.computeIfAbsent(day, k -> {
                Map<String, Object> m = new java.util.LinkedHashMap<>();
                m.put("day", day);
                m.put("success", 0);
                m.put("failed", 0);
                m.put("degraded", 0);
                m.put("avgLatencyMs", 0);
                return m;
            });
            if ("SUCCESS".equalsIgnoreCase(status)) {
                item.merge("success", cnt, (a, b) -> ((Integer) a) + (Integer) b);
                // 日级典型延迟取 SUCCESS 行数值（更稳定，避免被 FAILED 的慢延迟污染）
                Object lat = row.get("avg_latency");
                if (lat instanceof Number && ((Number) lat).longValue() > 0) {
                    item.put("avgLatencyMs", ((Number) lat).intValue());
                }
            } else if ("FAILED".equalsIgnoreCase(status)) {
                item.merge("failed", cnt, (a, b) -> ((Integer) a) + (Integer) b);
            } else {
                item.merge("degraded", cnt, (a, b) -> ((Integer) a) + (Integer) b);
            }
        }
        return new ArrayList<>(byDay.values());
    }

    static double round2(double v) {
        return Math.round(v * 100.0) / 100.0;
    }
}
