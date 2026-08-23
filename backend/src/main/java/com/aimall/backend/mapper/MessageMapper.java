package com.aimall.backend.mapper;

import com.aimall.backend.entity.Message;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Mapper
public interface MessageMapper extends BaseMapper<Message> {

    /** 最近 N 条消息（id 倒序取，业务层再反转） */
    @Select("SELECT * FROM message WHERE conversation_id = #{conversationId} ORDER BY id DESC LIMIT #{limit}")
    List<Message> selectRecent(@Param("conversationId") Long conversationId, @Param("limit") int limit);

    /** 增量拉取（前端轮询人工消息） */
    @Select("SELECT * FROM message WHERE conversation_id = #{conversationId} AND id > #{afterId} ORDER BY id ASC")
    List<Message> selectAfter(@Param("conversationId") Long conversationId, @Param("afterId") Long afterId);

    @Select("SELECT COUNT(*) FROM message WHERE role = 'AI' AND created_at >= #{since}")
    long countTodayAi(@Param("since") LocalDateTime since);

    /** 热门问题 TOP N（按用户消息前缀聚合） */
    @Select("SELECT LEFT(content, 16) AS keyword, COUNT(*) AS cnt FROM message " +
            "WHERE role = 'USER' AND created_at >= #{since} " +
            "GROUP BY keyword ORDER BY cnt DESC LIMIT 10")
    List<Map<String, Object>> topQuestions(@Param("since") LocalDateTime since);

    /** 今日含工具调用的 AI 消息（统计工具使用分布） */
    @Select("SELECT tool_calls FROM message WHERE role = 'AI' AND tool_calls IS NOT NULL " +
            "AND created_at >= #{since} LIMIT 500")
    List<String> selectTodayToolCalls(@Param("since") LocalDateTime since);

    /** 今日含工具调用的 AI 消息数（工具调用比率代理） */
    @Select("SELECT COUNT(*) FROM message WHERE role = 'AI' AND tool_calls IS NOT NULL " +
            "AND tool_calls <> '' AND created_at >= #{since}")
    long countTodayAiWithTool(@Param("since") LocalDateTime since);

    /** 今日 AI 消息按状态分组（回复质量代理指标） */
    @Select("SELECT status AS status, COUNT(*) AS cnt FROM message " +
            "WHERE role = 'AI' AND created_at >= #{since} GROUP BY status")
    List<Map<String, Object>> countTodayAiByStatus(@Param("since") LocalDateTime since);

    /** 近 N 天 AI 消息质量趋势：按天分组的 状态数 / 平均延迟 */
    @Select("SELECT DATE(created_at) AS day, status AS status, COUNT(*) AS cnt, " +
            "ROUND(AVG(CASE WHEN latency_ms IS NOT NULL THEN latency_ms END)) AS avg_latency " +
            "FROM message WHERE role = 'AI' AND created_at >= #{since} " +
            "GROUP BY DATE(created_at), status ORDER BY day")
    List<Map<String, Object>> aiQualityTrend(@Param("since") LocalDateTime since);

    /** 今日 token 用量明细（prompt/completion 计入回复成本） */
    @Select("SELECT token_usage FROM message WHERE role = 'AI' AND token_usage IS NOT NULL " +
            "AND created_at >= #{since} LIMIT 2000")
    List<String> selectTodayTokenUsage(@Param("since") LocalDateTime since);

    @Select("SELECT LEFT(content, 16) AS keyword, COUNT(*) AS cnt FROM message " +
            "WHERE role = 'USER' AND created_at >= #{start} AND created_at < #{end} " +
            "GROUP BY keyword ORDER BY cnt DESC, keyword LIMIT 10")
    List<Map<String, Object>> topQuestionsBetween(@Param("start") LocalDateTime start, @Param("end") LocalDateTime end);

    @Select("SELECT tool_calls FROM message WHERE role = 'AI' AND tool_calls IS NOT NULL " +
            "AND created_at >= #{start} AND created_at < #{end} LIMIT 500")
    List<String> selectToolCallsBetween(@Param("start") LocalDateTime start, @Param("end") LocalDateTime end);

    @Select("SELECT COUNT(*) FROM message WHERE role = 'AI' AND tool_calls IS NOT NULL " +
            "AND tool_calls <> '' AND created_at >= #{start} AND created_at < #{end}")
    long countAiWithToolBetween(@Param("start") LocalDateTime start, @Param("end") LocalDateTime end);

    @Select("SELECT status AS status, COUNT(*) AS cnt FROM message WHERE role = 'AI' " +
            "AND created_at >= #{start} AND created_at < #{end} GROUP BY status")
    List<Map<String, Object>> countAiByStatusBetween(@Param("start") LocalDateTime start, @Param("end") LocalDateTime end);

    @Select("SELECT COALESCE(ROUND(AVG(latency_ms)), 0) FROM message WHERE role = 'AI' " +
            "AND latency_ms IS NOT NULL AND created_at >= #{start} AND created_at < #{end}")
    Long avgAiLatencyBetween(@Param("start") LocalDateTime start, @Param("end") LocalDateTime end);

    @Select("SELECT token_usage FROM message WHERE role = 'AI' AND token_usage IS NOT NULL " +
            "AND created_at >= #{start} AND created_at < #{end} LIMIT 2000")
    List<String> selectTokenUsageBetween(@Param("start") LocalDateTime start, @Param("end") LocalDateTime end);
}
