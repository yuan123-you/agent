package com.aimall.backend.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 商品分类（对标 mall pms_product_category）。
 * parent_id=0 为一级分类；展示与导航状态由 show_status / nav_status 控制。
 */
@Data
@TableName("mall_category")
public class MallCategory {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 上级分类ID(0=一级分类) */
    private Long parentId;

    private String name;

    /** 1->一级; 2->二级 */
    private Integer level;

    private String icon;

    /** 排序(越小越靠前) */
    private Integer sort;

    /** 是否显示在导航栏:0->否;1->是 */
    private Integer navStatus;

    /** 显示状态:0->隐藏;1->显示 */
    private Integer showStatus;

    private String keywords;

    private String description;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;

    @TableLogic
    private Integer deleted;

    /** 子分类（查询时组装，不入库） */
    @TableField(exist = false)
    private java.util.List<MallCategory> children;

    /** 在售商品数（查询时实时聚合，不入库） */
    @TableField(exist = false)
    private Long productCount;
}
