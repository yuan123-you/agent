package com.aimall.backend.mapper;

import com.aimall.backend.entity.OrderInfo;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Mapper
public interface OrderInfoMapper extends BaseMapper<OrderInfo> {

    @Select("SELECT COUNT(*) FROM order_info WHERE created_at >= #{start} AND created_at < #{end}")
    long countCreatedBetween(@Param("start") LocalDateTime start, @Param("end") LocalDateTime end);

    @Select("SELECT COALESCE(SUM(total_amount), 0) FROM order_info " +
            "WHERE created_at >= #{start} AND created_at < #{end} " +
            "AND status IN ('PAID', 'SHIPPED', 'DELIVERED', 'COMPLETED')")
    BigDecimal sumPaidGmvBetween(@Param("start") LocalDateTime start, @Param("end") LocalDateTime end);

    @Select("SELECT DATE(created_at) AS day, COUNT(*) AS order_count, " +
            "COALESCE(SUM(CASE WHEN status IN ('PAID', 'SHIPPED', 'DELIVERED', 'COMPLETED') " +
            "THEN total_amount ELSE 0 END), 0) AS gmv " +
            "FROM order_info WHERE created_at >= #{start} AND created_at < #{end} " +
            "GROUP BY DATE(created_at) ORDER BY day")
    List<Map<String, Object>> selectDailyTrend(@Param("start") LocalDateTime start, @Param("end") LocalDateTime end);

    @Select("SELECT status AS status, COUNT(*) AS cnt FROM order_info GROUP BY status ORDER BY status")
    List<Map<String, Object>> countByStatus();
}
