package com.aimall.backend.admin;

import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * StatsController 纯函数单元测试（无需数据库/Spring 上下文）。
 */
class StatsControllerTest {

    @Test
    void aggregateToolCalls_dedupsByCallId() {
        List<String> rows = List.of(
                "[{\"callId\":\"c1\",\"tool\":\"product_search\"},"
                        + "{\"callId\":\"c2\",\"tool\":\"order_query\"}]",
                "[{\"callId\":\"c1\",\"tool\":\"product_search\"}]",
                "not-json",
                "null"
        );
        Map<String, Integer> out = StatsController.aggregateToolCalls(rows);
        assertEquals(1, out.get("product_search"));
        assertEquals(1, out.get("order_query"));
    }

    @Test
    void aggregateToolCalls_blankToolSkipped() {
        List<String> rows = List.of(
                "[{\"callId\":\"c1\",\"tool\":\"kb_search\"}]",
                "[{\"callId\":\"c2\",\"tool\":\"  \"}]",
                "[{\"callId\":\"c3\"}]"
        );
        Map<String, Integer> out = StatsController.aggregateToolCalls(rows);
        assertEquals(1, out.get("kb_search"));
        assertEquals(1, out.size());
    }

    @Test
    void aggregateStatusCounts_sumsRows() {
        List<Map<String, Object>> rows = List.of(
                row("SUCCESS", 5),
                row("SUCCESS", 3),
                row("FAILED", 2)
        );
        Map<String, Integer> out = StatsController.aggregateStatusCounts(rows);
        assertEquals(8, out.get("SUCCESS"));
        assertEquals(2, out.get("FAILED"));
    }

    @Test
    void aggregateTokens_sumsPromptAndCompletion() {
        List<String> rows = List.of(
                "{\"prompt_tokens\":100,\"completion_tokens\":50}",
                "{\"prompt_tokens\":200}",
                "bad"
        );
        Map<String, Object> out = StatsController.aggregateTokens(rows);
        assertEquals(300L, out.get("prompt_tokens"));
        assertEquals(50L, out.get("completion_tokens"));
        assertEquals(350L, out.get("total_tokens"));
    }

    @Test
    void buildTrend_groupsByDayWithLatency() {
        List<Map<String, Object>> rows = List.of(
                trendRow("2026-08-20", "SUCCESS", 4, 500),
                trendRow("2026-08-20", "FAILED", 1, 900),
                trendRow("2026-08-21", "SUCCESS", 10, 300)
        );
        List<Map<String, Object>> out = StatsController.buildTrend(rows);
        out = new java.util.ArrayList<>(out.stream().map(m -> new LinkedHashMap<>(m)).toList());
        assertEquals(2, out.size());

        Map<String, Object> d20 = out.get(0);
        assertEquals("2026-08-20", d20.get("day"));
        assertEquals(4, d20.get("success"));
        assertEquals(1, d20.get("failed"));
        assertEquals(500, d20.get("avgLatencyMs"));

        Map<String, Object> d21 = out.get(1);
        assertEquals(10, d21.get("success"));
        assertEquals(0, d21.get("failed"));
        assertEquals(300, d21.get("avgLatencyMs"));
    }

    private static Map<String, Object> row(String status, int cnt) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("status", status);
        m.put("cnt", cnt);
        return m;
    }

    private static Map<String, Object> trendRow(String day, String status, int cnt, int latency) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("day", day);
        m.put("status", status);
        m.put("cnt", cnt);
        m.put("avg_latency", latency);
        return m;
    }
}