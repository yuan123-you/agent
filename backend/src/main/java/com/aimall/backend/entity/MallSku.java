package com.aimall.backend.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * SKU 规格库存（对标 mall pms_sku_stock）。
 * 无 SKU 的商品沿用 product.stock / product.price；有 SKU 时下单按 SKU 价格与库存。
 */
@Data
@TableName("mall_sku")
public class MallSku {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long productId;

    private String skuCode;

    /** 销售属性JSON:[{"key":"颜色","value":"黑色"}] */
    private String spData;

    private BigDecimal price;

    private Integer stock;

    private Integer lockStock;

    private Integer lowStock;

    private String pic;

    private Integer sale;

    /** ENABLE / DISABLE */
    private String status;

    /** 乐观锁版本 */
    @Version
    private Integer version;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;

    @TableLogic
    private Integer deleted;
}
