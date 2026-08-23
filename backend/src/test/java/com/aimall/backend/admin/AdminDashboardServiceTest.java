package com.aimall.backend.admin;

import com.aimall.backend.mapper.ConversationMapper;
import com.aimall.backend.mapper.MessageMapper;
import com.aimall.backend.mapper.OrderInfoMapper;
import com.aimall.backend.mapper.ProductMapper;
import com.aimall.backend.mapper.UserMapper;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AdminDashboardServiceTest {

    private static final ZoneId SHANGHAI = ZoneId.of("Asia/Shanghai");
    private final UserMapper userMapper = mock(UserMapper.class);
    private final ProductMapper productMapper = mock(ProductMapper.class);
    private final OrderInfoMapper orderInfoMapper = mock(OrderInfoMapper.class);
    private final ConversationMapper conversationMapper = mock(ConversationMapper.class);
    private final MessageMapper messageMapper = mock(MessageMapper.class);
    private final Clock clock = Clock.fixed(Instant.parse("2026-08-23T04:00:00Z"), SHANGHAI);
    private final AdminDashboardService service = new AdminDashboardService(
            userMapper, productMapper, orderInfoMapper, conversationMapper, messageMapper, clock);

    @Test
    void assemblesTodayAndSevenDayDashboardUsingShanghaiBoundaries() {
        when(userMapper.countPlatformUsers()).thenReturn(10L);
        when(userMapper.countMerchants()).thenReturn(3L);
        when(productMapper.countOnSale()).thenReturn(8L);
        when(orderInfoMapper.countCreatedBetween(any(), any())).thenReturn(2L);
        when(orderInfoMapper.sumPaidGmvBetween(any(), any())).thenReturn(new BigDecimal("2999.00"));
        when(orderInfoMapper.selectDailyTrend(any(), any())).thenReturn(List.of(
                Map.of("day", LocalDate.of(2026, 8, 17), "order_count", 4L, "gmv", new BigDecimal("199.90")),
                Map.of("day", LocalDate.of(2026, 8, 23), "order_count", 2L, "gmv", new BigDecimal("2999.00"))));
        when(orderInfoMapper.countByStatus()).thenReturn(List.of(Map.of("status", "PAID", "cnt", 2L)));
        when(conversationMapper.countCreatedBetween(any(), any())).thenReturn(7L);
        when(conversationMapper.countByStatus("PENDING_HUMAN")).thenReturn(2L);
        when(messageMapper.countAiByStatusBetween(any(), any())).thenReturn(List.of(
                Map.of("status", "SUCCESS", "cnt", 3L), Map.of("status", "FAILED", "cnt", 1L)));
        when(messageMapper.countAiWithToolBetween(any(), any())).thenReturn(2L);
        when(messageMapper.avgAiLatencyBetween(any(), any())).thenReturn(123L);
        when(messageMapper.selectTokenUsageBetween(any(), any())).thenReturn(List.of("{\"prompt_tokens\":1000,\"completion_tokens\":234}"));
        when(messageMapper.topQuestionsBetween(any(), any())).thenReturn(List.of(Map.of("keyword", "怎么退款", "cnt", 5L)));
        when(messageMapper.selectToolCallsBetween(any(), any())).thenReturn(List.of("[{\"callId\":\"c1\",\"tool\":\"order_query\"}]"));

        AdminDashboardService.DashboardVO result = service.dashboard();

        assertThat(result.summary().todayGmv()).isEqualByComparingTo("2999.00");
        assertThat(result.orderTrend()).hasSize(7);
        assertThat(result.orderTrend().get(0).date()).isEqualTo(LocalDate.of(2026, 8, 17));
        assertThat(result.orderTrend().get(1).orderCount()).isZero();
        assertThat(result.aiQuality().totalTokens()).isEqualTo(1234L);
        assertThat(result.aiQuality().replySuccessRate()).isEqualTo(75.0);
        assertThat(result.aiQuality().toolCallRatio()).isEqualTo(50.0);
        assertThat(result.aiQuality().avgLatencyMs()).isEqualTo(123L);
        assertThat(result.topQuestions()).containsExactly(new AdminDashboardService.RankItem("怎么退款", 5L));
        assertThat(result.toolCalls()).containsExactly(new AdminDashboardService.RankItem("order_query", 1L));
        verify(orderInfoMapper).countCreatedBetween(
                LocalDateTime.of(2026, 8, 23, 0, 0), LocalDateTime.of(2026, 8, 24, 0, 0));
        verify(orderInfoMapper).selectDailyTrend(
                LocalDateTime.of(2026, 8, 17, 0, 0), LocalDateTime.of(2026, 8, 24, 0, 0));
    }

    @Test
    void returnsCompleteZeroSafeResponseWhenNoDataExists() {
        when(orderInfoMapper.sumPaidGmvBetween(any(), any())).thenReturn(null);
        when(orderInfoMapper.selectDailyTrend(any(), any())).thenReturn(List.of());
        when(orderInfoMapper.countByStatus()).thenReturn(List.of());
        when(messageMapper.countAiByStatusBetween(any(), any())).thenReturn(List.of());
        when(messageMapper.selectTokenUsageBetween(any(), any())).thenReturn(List.of());
        when(messageMapper.topQuestionsBetween(any(), any())).thenReturn(List.of());
        when(messageMapper.selectToolCallsBetween(any(), any())).thenReturn(List.of());

        AdminDashboardService.DashboardVO result = service.dashboard();

        assertThat(result.summary().todayGmv()).isEqualByComparingTo(BigDecimal.ZERO);
        assertThat(result.summary().todayOrderCount()).isZero();
        assertThat(result.orderTrend()).hasSize(7).allSatisfy(point -> {
            assertThat(point.orderCount()).isZero();
            assertThat(point.gmv()).isEqualByComparingTo(BigDecimal.ZERO);
        });
        assertThat(result.orderStatusDistribution()).isEmpty();
        assertThat(result.operations().waitingHumanConversationCount()).isZero();
        assertThat(result.aiQuality().replySuccessRate()).isZero();
        assertThat(result.aiQuality().toolCallRatio()).isZero();
        assertThat(result.aiQuality().avgLatencyMs()).isZero();
        assertThat(result.aiQuality().totalTokens()).isZero();
        assertThat(result.topQuestions()).isEmpty();
        assertThat(result.toolCalls()).isEmpty();
    }
    @Test
    void aggregatesMoreRowsThanTheFormerMapperLimits() {
        List<String> tokenRows = java.util.stream.IntStream.range(0, 2001)
                .mapToObj(i -> "{\"prompt_tokens\":1,\"completion_tokens\":1}")
                .toList();
        List<String> toolRows = java.util.stream.IntStream.range(0, 501)
                .mapToObj(i -> "[{\"callId\":\"call-" + i + "\",\"tool\":\"order_query\"}]")
                .toList();
        when(messageMapper.selectTokenUsageBetween(any(), any())).thenReturn(tokenRows);
        when(messageMapper.selectToolCallsBetween(any(), any())).thenReturn(toolRows);

        AdminDashboardService.DashboardVO result = service.dashboard();

        assertThat(result.aiQuality().totalTokens()).isEqualTo(4002L);
        assertThat(result.toolCalls()).containsExactly(
                new AdminDashboardService.RankItem("order_query", 501L));
    }
}
