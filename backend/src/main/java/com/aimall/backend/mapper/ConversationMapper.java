package com.aimall.backend.mapper;

import com.aimall.backend.entity.Conversation;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface ConversationMapper extends BaseMapper<Conversation> {

    @Select("SELECT COUNT(*) FROM conversation WHERE created_at >= #{since}")
    long countToday(@Param("since") java.time.LocalDateTime since);

    /** 待接入 / 服务中数量（SLA 看板） */
    @Select("SELECT COUNT(*) FROM conversation WHERE status = #{status} AND deleted = 0")
    long countByStatus(@Param("status") String status);

    /** 今日已结束会话数（以更新时间近似关闭时刻） */
    @Select("SELECT COUNT(*) FROM conversation WHERE status = 'CLOSED' AND deleted = 0 AND updated_at >= #{since}")
    long countHandled(@Param("since") java.time.LocalDateTime since);

    /** 平均首次人工响应时长（秒）：会话创建到首条 AGENT 消息的耗时平均 */
    @Select("SELECT COALESCE(AVG(TIMESTAMPDIFF(SECOND, c.created_at, m.created_at)), 0) " +
            "FROM conversation c JOIN message m ON m.conversation_id = c.id AND m.role = 'AGENT' " +
            "AND m.id = (SELECT MIN(id) FROM message WHERE conversation_id = c.id AND role = 'AGENT') " +
            "WHERE c.deleted = 0")
    Long avgFirstResponseSeconds();

    /** 抢占式接管：仅 PENDING_HUMAN 可被接入（防双客服同接） */
    @Update("UPDATE conversation SET agent_id = #{agentId}, status = 'SERVICING', updated_at = NOW(3) " +
            "WHERE id = #{id} AND status = 'PENDING_HUMAN' AND deleted = 0")
    int claim(@Param("id") Long id, @Param("agentId") Long agentId);
}
