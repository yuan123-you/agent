package com.aimall.backend.mapper;

import com.aimall.backend.entity.MallSeckill;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface MallSeckillMapper extends BaseMapper<MallSeckill> {
    /** Serialize buyer entitlement checks even when that buyer has no previous campaign orders. */
    @org.apache.ibatis.annotations.Select("SELECT id FROM sys_user WHERE id = #{userId} AND deleted = 0 FOR UPDATE")
    Long lockBuyer(@org.apache.ibatis.annotations.Param("userId") Long userId);

    // Locking row reads are current reads under MySQL REPEATABLE READ; do not replace with snapshot SUM.
    @org.apache.ibatis.annotations.Select({"<script>",
            "SELECT i.quantity FROM order_item i JOIN order_info o ON o.id=i.order_id",
            "WHERE o.user_id=#{userId} AND i.seckill_id=#{campaignId} AND o.status &lt;&gt; 'CANCELLED'",
            "<if test='locking'>FOR UPDATE</if>", "</script>"})
    java.util.List<Integer> entitlementQuantities(@org.apache.ibatis.annotations.Param("userId") Long userId,
            @org.apache.ibatis.annotations.Param("campaignId") Long campaignId,
            @org.apache.ibatis.annotations.Param("locking") boolean locking);
}
