package com.aimall.backend.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;

@Data
@TableName("order_item")
public class OrderItem {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long orderId;

    private Long productId;

    /** 商品名快照 */
    private String productName;

    private String productImage;

    /** 单价快照 */
    private BigDecimal price;

    private Integer quantity;

    private BigDecimal subtotal;
}
