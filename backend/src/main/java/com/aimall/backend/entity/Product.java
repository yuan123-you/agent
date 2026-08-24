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

    /** 价格币种 */
    private String currency;

    /** 来源名称 */
    private String sourceName;

    /** 来源商品URL */
    private String sourceUrl;

    /** 来源商品标识 */
    private String sourceProductId;

    /** 来源更新时间 */
    private LocalDateTime sourceUpdatedAt;

    /** 采集时间 */
    private LocalDateTime collectedAt;

    /** 原始图片URL */
    private String originalImageUrl;

    /** 图片 SHA-256 */
    private String imageSha256;

    /** 库存、销量等商业字段是否为模拟值 */
    private Boolean simulatedCommerceFields;

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
