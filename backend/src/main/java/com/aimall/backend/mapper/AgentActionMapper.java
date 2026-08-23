package com.aimall.backend.mapper;

import com.aimall.backend.entity.AgentAction;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.*;

import java.math.BigDecimal;
import java.time.Instant;

@Mapper
public interface AgentActionMapper extends BaseMapper<AgentAction> {
    @Select("SELECT * FROM agent_action WHERE action_id = #{actionId} FOR UPDATE")
    AgentAction selectForUpdate(@Param("actionId") String actionId);

    @Update("UPDATE agent_action SET status = 'CONFIRMED', order_id = #{orderId}, amount = #{amount}, " +
            "updated_at = NOW(3) WHERE action_id = #{actionId} AND status = 'PENDING'")
    int markConfirmed(@Param("actionId") String actionId, @Param("orderId") Long orderId,
                      @Param("amount") BigDecimal amount);

    @Update("UPDATE agent_action SET status = 'EXPIRED', updated_at = NOW(3) " +
            "WHERE status = 'PENDING' AND expires_at <= #{now}")
    int expirePending(@Param("now") Instant now);
}
