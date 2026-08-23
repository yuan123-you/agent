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
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 商品评论接口：/api/v1/products/{id}/reviews（买家登录即可评论）
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
        private String specInfo;
    }

    /** 评论列表（懒加载分页，时间倒序）+ 评分统计 */
    @GetMapping
    public ApiResponse<Map<String, Object>> list(@PathVariable Long productId,
                                                 @RequestParam(defaultValue = "1") long page,
                                                 @RequestParam(defaultValue = "20") long size) {
        List<ProductReview> reviews = reviewMapper.selectList(new LambdaQueryWrapper<ProductReview>()
                .eq(ProductReview::getProductId, productId)
                .orderByDesc(ProductReview::getId)
                .last("LIMIT " + ((page - 1) * size) + "," + size));
        Long total = reviewMapper.selectCount(new LambdaQueryWrapper<ProductReview>()
                .eq(ProductReview::getProductId, productId));

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

        // 评分统计
        List<ProductReview> all = reviewMapper.selectList(new LambdaQueryWrapper<ProductReview>()
                .eq(ProductReview::getProductId, productId));
        double avg = all.stream().mapToInt(ProductReview::getRating).average().orElse(5.0);
        Map<String, Long> dist = new HashMap<>();
        for (int i = 1; i <= 5; i++) {
            final int star = i;
            dist.put(String.valueOf(i), all.stream().filter(r -> r.getRating() == star).count());
        }

        Map<String, Object> data = new HashMap<>();
        data.put("records", rows);
        data.put("total", total);
        data.put("avgRating", Math.round(avg * 10) / 10.0);
        data.put("ratingDistribution", dist);
        return ApiResponse.ok(data);
    }

    /** 发表评论 */
    @PostMapping
    public ApiResponse<Void> create(@AuthenticationPrincipal Long userId,
                                    @PathVariable Long productId,
                                    @Validated @RequestBody CreateBody body) {
        if (productMapper.selectById(productId) == null) {
            throw new BizException(2002, "商品不存在");
        }
        // 一人一商品限一条（简化）
        Long exists = reviewMapper.selectCount(new LambdaQueryWrapper<ProductReview>()
                .eq(ProductReview::getUserId, userId)
                .eq(ProductReview::getProductId, productId));
        if (exists != null && exists > 0) {
            throw new BizException(2004, "您已评价过该商品");
        }
        ProductReview review = new ProductReview();
        review.setProductId(productId);
        review.setUserId(userId);
        review.setRating(body.getRating());
        review.setContent(body.getContent());
        review.setSpecInfo(body.getSpecInfo());
        reviewMapper.insert(review);
        return ApiResponse.ok();
    }
}
