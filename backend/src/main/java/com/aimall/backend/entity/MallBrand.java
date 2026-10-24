package com.aimall.backend.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 品牌（对标 mall pms_brand）。
 */
@Data
@TableName("mall_brand")
public class MallBrand {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String name;

    /** 首字母(检索用) */
    private String firstLetter;

    private String logo;

    /** 专区大图 */
    private String bigPic;

    /** 品牌故事 */
    private String brandStory;

    private Integer sort;

    /** 显示状态:0->隐藏;1->显示 */
    private Integer showStatus;

    /** 品牌下商品数量(冗余) */
    private Integer productCount;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;

    @TableLogic
    private Integer deleted;
}
