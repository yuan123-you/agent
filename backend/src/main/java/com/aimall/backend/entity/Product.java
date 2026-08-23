package com.aimall.backend.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("product")
public class Product {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String name;

    private String category;

    private String brand;

    private BigDecimal price;

    private Integer stock;

    private String imageUrl;

    private String description;

    private String sellingPoints;

    /** 参数 JSON 字符串 */
    private String specs;

    /** 产地 */
    private String origin;

    /** 发货地 */
    private String shipFrom;

    /** 生产日期 */
    private String productionDate;

    /** 材质 */
    private String material;

    /** 商家ID（NULL=自营） */
    private Long merchantId;

    /** 销量 */
    private Integer sales;

    /** ON_SALE / OFF_SHELF */
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
