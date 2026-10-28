package com.aimall.backend.mapper;

import com.aimall.backend.entity.OrderItem;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface OrderItemMapper extends BaseMapper<OrderItem> {
    @org.apache.ibatis.annotations.Select({"<script>",
            "SELECT order_item_id,cancelled_fulfillment_quantity FROM after_sale",
            "WHERE order_id=#{orderId} AND cancelled_fulfillment_quantity > 0",
            "<if test='locking'>FOR UPDATE</if>", "</script>"})
    java.util.List<com.aimall.backend.entity.AfterSale> fulfillmentReductions(
            @org.apache.ibatis.annotations.Param("orderId") Long orderId,
            @org.apache.ibatis.annotations.Param("locking") boolean locking);
}
