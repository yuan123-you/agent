package com.aimall.backend.admin;

import com.aimall.backend.mapper.MessageMapper;
import org.apache.ibatis.annotations.Select;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.time.LocalDateTime;

import static org.assertj.core.api.Assertions.assertThat;

class AdminDashboardMapperContractTest {

    @Test
    void dashboardTokenQueryDoesNotTruncateRowsBeforeAggregation() throws Exception {
        assertThat(selectSql("selectTokenUsageBetween"))
                .as("dashboard totalTokens must aggregate every matching AI message")
                .doesNotContainIgnoringCase("LIMIT");
    }

    @Test
    void dashboardToolQueryDoesNotTruncateRowsBeforeRanking() throws Exception {
        assertThat(selectSql("selectToolCallsBetween"))
                .as("dashboard tool rankings must aggregate every matching tool call")
                .doesNotContainIgnoringCase("LIMIT");
    }

    private static String selectSql(String methodName) throws Exception {
        Method method = MessageMapper.class.getMethod(
                methodName, LocalDateTime.class, LocalDateTime.class);
        return String.join(" ", method.getAnnotation(Select.class).value());
    }
}
