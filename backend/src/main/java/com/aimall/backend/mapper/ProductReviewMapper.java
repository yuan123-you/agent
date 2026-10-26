package com.aimall.backend.mapper;

import com.aimall.backend.entity.ProductReview;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import lombok.Data;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface ProductReviewMapper extends BaseMapper<ProductReview> {

    @Select("SELECT id FROM sys_user WHERE id=#{userId} AND deleted=0 FOR UPDATE")
    Long lockReviewUser(@Param("userId") Long userId);

    @Select({"<script>",
            "SELECT oi.id FROM order_item oi JOIN order_info o ON o.id=oi.order_id",
            "WHERE o.user_id=#{userId} AND oi.product_id=#{productId} AND o.status='DELIVERED'",
            "<if test='orderItemId != null'>AND oi.id=#{orderItemId}</if>",
            "ORDER BY oi.id LIMIT 1",
            "</script>"})
    Long findDeliveredOrderItem(@Param("userId") Long userId, @Param("productId") Long productId,
                               @Param("orderItemId") Long orderItemId);

    @Select("""
            SELECT COUNT(*) AS total, COALESCE(AVG(rating),5.0) AS average,
                   COALESCE(SUM(CASE WHEN rating=1 THEN 1 ELSE 0 END),0) AS one_star,
                   COALESCE(SUM(CASE WHEN rating=2 THEN 1 ELSE 0 END),0) AS two_star,
                   COALESCE(SUM(CASE WHEN rating=3 THEN 1 ELSE 0 END),0) AS three_star,
                   COALESCE(SUM(CASE WHEN rating=4 THEN 1 ELSE 0 END),0) AS four_star,
                   COALESCE(SUM(CASE WHEN rating=5 THEN 1 ELSE 0 END),0) AS five_star
            FROM product_review WHERE product_id=#{productId} AND deleted=0
            """)
    RatingSummary summarizeRatings(@Param("productId") Long productId);

    @Data
    class RatingSummary {
        private long total;
        private double average;
        private long oneStar;
        private long twoStar;
        private long threeStar;
        private long fourStar;
        private long fiveStar;
    }
}
