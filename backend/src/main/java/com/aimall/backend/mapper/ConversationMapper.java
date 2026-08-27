package com.aimall.backend.mapper;

import com.aimall.backend.entity.Conversation;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.time.LocalDateTime;

@Mapper
public interface ConversationMapper extends BaseMapper<Conversation> {

    @Select("SELECT COUNT(*) FROM conversation WHERE created_at >= #{since}")
    long countToday(@Param("since") LocalDateTime since);

    @Select("SELECT COUNT(*) FROM conversation WHERE deleted = 0 AND created_at >= #{start} AND created_at < #{end}")
    long countCreatedBetween(@Param("start") LocalDateTime start,
                             @Param("end") LocalDateTime end);

    @Select("SELECT COUNT(*) FROM conversation WHERE status = #{status} AND deleted = 0")
    long countByStatus(@Param("status") String status);

    @Select("SELECT COUNT(*) FROM conversation WHERE status = 'CLOSED' AND deleted = 0 AND updated_at >= #{since}")
    long countHandled(@Param("since") LocalDateTime since);

    @Select("SELECT COALESCE(AVG(TIMESTAMPDIFF(SECOND, c.created_at, m.created_at)), 0) " +
            "FROM conversation c JOIN message m ON m.conversation_id = c.id AND m.role = 'AGENT' " +
            "AND m.id = (SELECT MIN(id) FROM message WHERE conversation_id = c.id AND role = 'AGENT') " +
            "WHERE c.deleted = 0")
    Long avgFirstResponseSeconds();

    @Update("UPDATE conversation SET agent_id = #{agentId}, status = 'SERVICING', updated_at = NOW(3) " +
            "WHERE id = #{id} AND status = 'PENDING_HUMAN' AND updated_at > #{deadline} AND deleted = 0")
    int claim(@Param("id") Long id, @Param("agentId") Long agentId,
              @Param("deadline") LocalDateTime deadline);

    @Update("UPDATE conversation SET agent_id = NULL, status = 'ACTIVE', updated_at = NOW(3) " +
            "WHERE id = #{id} AND user_id = #{userId} AND status = 'PENDING_HUMAN' AND deleted = 0")
    int cancelPending(@Param("id") Long id, @Param("userId") Long userId);

    @Update("UPDATE conversation SET agent_id = NULL, status = 'ACTIVE', updated_at = NOW(3) " +
            "WHERE status = 'PENDING_HUMAN' AND updated_at <= #{deadline} AND deleted = 0")
    int expirePendingBefore(@Param("deadline") LocalDateTime deadline);

    @Update("UPDATE conversation SET agent_id = NULL, status = 'ACTIVE', updated_at = NOW(3) " +
            "WHERE id = #{id} AND status = 'PENDING_HUMAN' AND updated_at <= #{deadline} AND deleted = 0")
    int expirePending(@Param("id") Long id, @Param("deadline") LocalDateTime deadline);
}
