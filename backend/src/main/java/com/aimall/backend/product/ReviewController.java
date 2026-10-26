package com.aimall.backend.product;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.ProductReview;
import com.aimall.backend.entity.User;
import com.aimall.backend.mapper.ProductMapper;
import com.aimall.backend.mapper.ProductReviewMapper;
import com.aimall.backend.mapper.UserMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 商品评论接口：/api/v1/products/{id}/reviews（已收货买家可评论）
 */
@RestController
@RequestMapping("/api/v1/products/{productId}/reviews")
@RequiredArgsConstructor
@Validated
public class ReviewController {

    private final ProductReviewMapper reviewMapper;
    private final ProductMapper productMapper;
    private final UserMapper userMapper;

    @Data
    public static class CreateBody {
        @NotNull
        @jakarta.validation.constraints.Min(1)
        @jakarta.validation.constraints.Max(5)
        private Integer rating;
        @NotBlank
        @Size(max = 1000)
        private String content;
        /** 购买规格快照（可选） */
        @Size(max = 255)
        private String specInfo;
        /** 指定已收货的购买明细（可选，省略时自动查找） */
        private Long orderItemId;
    }

    /** 评论列表（懒加载分页，时间倒序）+ 评分统计 */
    @GetMapping
    public ApiResponse<Map<String, Object>> list(@PathVariable Long productId,
                                                 @RequestParam(defaultValue = "1") long page,
                                                 @RequestParam(defaultValue = "20") long size) {
        if (page < 1 || size < 1 || size > 100 || page - 1 > Long.MAX_VALUE / size) {
            throw new BizException(2001, "分页参数不合法（page >= 1，size 为 1~100）");
        }
        List<ProductReview> reviews = reviewMapper.selectList(new LambdaQueryWrapper<ProductReview>()
                .eq(ProductReview::getProductId, productId)
                .orderByDesc(ProductReview::getId)
                .last("LIMIT " + ((page - 1) * size) + "," + size));

        List<Map<String, Object>> rows = new ArrayList<>();
        for (ProductReview r : reviews) {
            User u = userMapper.selectById(r.getUserId());
            Map<String, Object> row = new HashMap<>();
            row.put("reviewId", r.getId());
            row.put("nickname", u != null ? u.getNickname() : "匿名用户");
            row.put("rating", r.getRating());
            row.put("content", r.getContent());
            row.put("specInfo", r.getSpecInfo());
            row.put("merchantReply", r.getMerchantReply());
            row.put("createdAt", r.getCreatedAt());
            rows.add(row);
        }

        // 数据库聚合全部有效评价，不全量加载评价实体。
        ProductReviewMapper.RatingSummary summary = reviewMapper.summarizeRatings(productId);
        long[] counts = {summary.getOneStar(), summary.getTwoStar(), summary.getThreeStar(),
                summary.getFourStar(), summary.getFiveStar()};
        Map<String, Long> dist = new HashMap<>();
        for (int i = 1; i <= 5; i++) {
            dist.put(String.valueOf(i), counts[i - 1]);
        }

        Map<String, Object> data = new HashMap<>();
        data.put("records", rows);
        data.put("total", summary.getTotal());
        data.put("avgRating", Math.round(summary.getAverage() * 10) / 10.0);
        data.put("ratingDistribution", dist);
        return ApiResponse.ok(data);
    }

    /** 发表评论 */
    @PostMapping
    @Transactional
    public ApiResponse<Void> create(@AuthenticationPrincipal Long userId,
                                    @PathVariable Long productId,
                                    @Validated @RequestBody CreateBody body) {
        // This must be the first SQL in the transaction: a preceding consistent read could
        // establish a stale MySQL REPEATABLE READ snapshot before waiting for this lock.
        if (userId == null || reviewMapper.lockReviewUser(userId) == null) {
            throw new BizException(1001, "请登录后评价");
        }
        if (productMapper.selectById(productId) == null) {
            throw new BizException(2002, "商品不存在");
        }
        // 锁后检查：一用户一商品仅一条有效评价，兼容无订单明细的历史评价。
        Long exists = reviewMapper.selectCount(new LambdaQueryWrapper<ProductReview>()
                .eq(ProductReview::getUserId, userId)
                .eq(ProductReview::getProductId, productId));
        if (exists != null && exists > 0) {
            throw new BizException(2004, "您已评价过该商品");
        }
        Long orderItemId = reviewMapper.findDeliveredOrderItem(userId, productId, body.getOrderItemId());
        if (orderItemId == null) {
            throw new BizException(2004, "仅可评价本人已收货的该商品");
        }
        ProductReview review = new ProductReview();
        review.setOrderItemId(orderItemId);
        review.setProductId(productId);
        review.setUserId(userId);
        review.setRating(body.getRating());
        review.setContent(body.getContent());
        review.setSpecInfo(body.getSpecInfo());
        if (reviewMapper.insert(review) != 1) {
            throw new BizException(2004, "评价保存失败，请重试");
        }
        return ApiResponse.ok();
    }
}
