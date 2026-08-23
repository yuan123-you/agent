package com.aimall.backend.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("product_review")
public class ProductReview {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long productId;

    private Long userId;

    /** 关联订单明细（验证购买，可空） */
    private Long orderItemId;

    /** 评分 1~5 */
    private Integer rating;

    private String content;

    /** 购买规格快照 */
    private String specInfo;

    /** 商家回复 */
    private String merchantReply;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableLogic
    private Integer deleted;
}
