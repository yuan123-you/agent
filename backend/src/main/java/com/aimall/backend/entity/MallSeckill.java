package com.aimall.backend.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 商品秒杀活动（对标 mall sms_seckill 精简版：时间窗 + 专属价 + 专属库存）。
 */
@Data
@TableName("mall_seckill")
public class MallSeckill {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long productId;

    /** 秒杀价 */
    private BigDecimal seckillPrice;

    /** 秒杀专属库存 */
    private Integer seckillStock;

    /** 每人限购件数 */
    private Integer seckillLimit;

    private LocalDateTime startTime;

    private LocalDateTime endTime;

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
