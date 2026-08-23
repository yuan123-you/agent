package com.aimall.backend.admin;

import com.aimall.backend.mapper.ConversationMapper;
import com.aimall.backend.mapper.MessageMapper;
import com.aimall.backend.mapper.OrderInfoMapper;
import com.aimall.backend.mapper.ProductMapper;
import com.aimall.backend.mapper.UserMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Objects;

@Service
@RequiredArgsConstructor
public class AdminDashboardService {

    private static final ZoneId SHANGHAI = ZoneId.of("Asia/Shanghai");

    private final UserMapper userMapper;
    private final ProductMapper productMapper;
    private final OrderInfoMapper orderInfoMapper;
    private final ConversationMapper conversationMapper;
    private final MessageMapper messageMapper;
    private final Clock clock;

    public DashboardVO dashboard() {
        LocalDate today = LocalDate.now(clock.withZone(SHANGHAI));
        LocalDateTime start = today.atStartOfDay();
        LocalDateTime end = start.plusDays(1);
        LocalDate trendStart = today.minusDays(6);

        Map<String, Integer> statusCounts = StatsController.aggregateStatusCounts(
                nullSafe(messageMapper.countAiByStatusBetween(start, end)));
        long aiMessageCount = statusCounts.values().stream().mapToLong(Integer::longValue).sum();
        long successCount = statusCounts.getOrDefault("SUCCESS", 0);
        Map<String, Object> tokenUsage = StatsController.aggregateTokens(
                nullSafe(messageMapper.selectTokenUsageBetween(start, end)));

        SummaryVO summary = new SummaryVO(
                userMapper.countPlatformUsers(),
                userMapper.countMerchants(),
                productMapper.countOnSale(),
                orderInfoMapper.countCreatedBetween(start, end),
                zero(orderInfoMapper.sumPaidGmvBetween(start, end)),
                conversationMapper.countCreatedBetween(start, end));

        return new DashboardVO(
                summary,
                fillOrderTrend(trendStart, nullSafe(orderInfoMapper.selectDailyTrend(trendStart.atStartOfDay(), end))),
                statusDistribution(nullSafe(orderInfoMapper.countByStatus())),
                new OperationsVO(conversationMapper.countByStatus("PENDING_HUMAN")),
                new AiQualityVO(
                        percent(successCount, aiMessageCount),
                        percent(messageMapper.countAiWithToolBetween(start, end), aiMessageCount),
                        zero(messageMapper.avgAiLatencyBetween(start, end)),
                        tokenUsageLong(tokenUsage, "total_tokens")),
                rankItems(nullSafe(messageMapper.topQuestionsBetween(start, end))),
                toolRanks(nullSafe(messageMapper.selectToolCallsBetween(start, end))));
    }

    private static List<OrderTrendPoint> fillOrderTrend(LocalDate start, List<Map<String, Object>> rows) {
        Map<LocalDate, Map<String, Object>> byDate = new java.util.HashMap<>();
        for (Map<String, Object> row : rows) {
            LocalDate day = localDate(row.get("day"));
            if (day != null) byDate.put(day, row);
        }
        List<OrderTrendPoint> result = new ArrayList<>(7);
        for (int i = 0; i < 7; i++) {
            LocalDate day = start.plusDays(i);
            Map<String, Object> row = byDate.get(day);
            result.add(new OrderTrendPoint(day,
                    number(row == null ? null : row.get("order_count")),
                    decimal(row == null ? null : row.get("gmv"))));
        }
        return result;
    }

    private static List<StatusCount> statusDistribution(List<Map<String, Object>> rows) {
        return rows.stream()
                .filter(Objects::nonNull)
                .map(row -> new StatusCount(String.valueOf(row.get("status")), number(row.get("cnt"))))
                .sorted(Comparator.comparing(StatusCount::status))
                .toList();
    }

    private static List<RankItem> toolRanks(List<String> rows) {
        return StatsController.aggregateToolCalls(rows).entrySet().stream()
                .map(entry -> new RankItem(entry.getKey(), entry.getValue().longValue()))
                .sorted(Comparator.comparingLong(RankItem::count).reversed().thenComparing(RankItem::name))
                .toList();
    }

    private static List<RankItem> rankItems(List<Map<String, Object>> rows) {
        return rows.stream()
                .filter(Objects::nonNull)
                .map(row -> new RankItem(String.valueOf(row.get("keyword")), number(row.get("cnt"))))
                .sorted(Comparator.comparingLong(RankItem::count).reversed().thenComparing(RankItem::name))
                .toList();
    }

    private static double percent(long numerator, long denominator) {
        return denominator == 0 ? 0.0 : StatsController.round2(100.0 * numerator / denominator);
    }


    private static long tokenUsageLong(Map<String, Object> values, String key) {
        return number(values.get(key));
    }

    private static long number(Object value) {
        return value instanceof Number number ? number.longValue() : 0L;
    }

    private static BigDecimal decimal(Object value) {
        if (value instanceof BigDecimal decimal) return decimal;
        if (value instanceof Number number) return new BigDecimal(number.toString());
        return BigDecimal.ZERO;
    }

    private static BigDecimal zero(BigDecimal value) {
        return value == null ? BigDecimal.ZERO : value;
    }

    private static long zero(Long value) {
        return value == null ? 0L : value;
    }

    private static LocalDate localDate(Object value) {
        if (value instanceof LocalDate date) return date;
        if (value instanceof java.sql.Date date) return date.toLocalDate();
        if (value instanceof java.sql.Timestamp timestamp) return timestamp.toLocalDateTime().toLocalDate();
        if (value instanceof String text && !text.isBlank()) return LocalDate.parse(text);
        return null;
    }

    private static <T> List<T> nullSafe(List<T> values) {
        return values == null ? List.of() : values;
    }

    public record SummaryVO(long userCount, long merchantCount, long onSaleProductCount,
                            long todayOrderCount, BigDecimal todayGmv, long todayConversationCount) {}
    public record OrderTrendPoint(LocalDate date, long orderCount, BigDecimal gmv) {}
    public record StatusCount(String status, long count) {}
    public record OperationsVO(long waitingHumanConversationCount) {}
    public record AiQualityVO(double replySuccessRate, double toolCallRatio, long avgLatencyMs, long totalTokens) {}
    public record RankItem(String name, long count) {}
    public record DashboardVO(SummaryVO summary, List<OrderTrendPoint> orderTrend,
                              List<StatusCount> orderStatusDistribution, OperationsVO operations,
                              AiQualityVO aiQuality, List<RankItem> topQuestions, List<RankItem> toolCalls) {}
}
