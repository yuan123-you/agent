package com.aimall.backend.product;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.BrowseHistory;
import com.aimall.backend.entity.Favorite;
import com.aimall.backend.entity.Product;
import com.aimall.backend.entity.User;
import com.aimall.backend.mapper.BrowseHistoryMapper;
import com.aimall.backend.mapper.FavoriteMapper;
import com.aimall.backend.mapper.ProductMapper;
import com.aimall.backend.mapper.UserMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 收藏 + 浏览历史接口：/api/v1（买家登录即可）
 */
@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class FavoriteHistoryController {

    private final FavoriteMapper favoriteMapper;
    private final BrowseHistoryMapper historyMapper;
    private final ProductMapper productMapper;
    private final UserMapper userMapper;

    // ==================== 收藏 ====================

    /** 收藏/取消收藏（切换） */
    @PostMapping("/favorites/{productId}/toggle")
    public ApiResponse<Map<String, Object>> toggle(@AuthenticationPrincipal Long userId,
                                                   @PathVariable Long productId) {
        Favorite exist = favoriteMapper.selectOne(new LambdaQueryWrapper<Favorite>()
                .eq(Favorite::getUserId, userId)
                .eq(Favorite::getProductId, productId));
        if (exist != null) {
            favoriteMapper.deleteById(exist.getId());
            return ApiResponse.ok(Map.of("favorited", false));
        }
        Favorite fav = new Favorite();
        fav.setUserId(userId);
        fav.setProductId(productId);
        fav.setCreatedAt(LocalDateTime.now());
        favoriteMapper.insert(fav);
        return ApiResponse.ok(Map.of("favorited", true));
    }

    /** 是否已收藏（详情页按钮态） */
    @GetMapping("/favorites/{productId}/status")
    public ApiResponse<Map<String, Object>> status(@AuthenticationPrincipal Long userId,
                                                   @PathVariable Long productId) {
        Long n = favoriteMapper.selectCount(new LambdaQueryWrapper<Favorite>()
                .eq(Favorite::getUserId, userId)
                .eq(Favorite::getProductId, productId));
        return ApiResponse.ok(Map.of("favorited", n != null && n > 0));
    }

    /** 收藏列表（懒加载分页） */
    @GetMapping("/favorites")
    public ApiResponse<Map<String, Object>> list(@AuthenticationPrincipal Long userId,
                                                 @RequestParam(defaultValue = "1") long page,
                                                 @RequestParam(defaultValue = "20") long size) {
        List<Favorite> favors = favoriteMapper.selectList(new LambdaQueryWrapper<Favorite>()
                .eq(Favorite::getUserId, userId)
                .orderByDesc(Favorite::getId)
                .last("LIMIT " + ((page - 1) * size) + "," + size));
        Long total = favoriteMapper.selectCount(new LambdaQueryWrapper<Favorite>()
                .eq(Favorite::getUserId, userId));
        List<Map<String, Object>> rows = new ArrayList<>();
        for (Favorite f : favors) {
            Product p = productMapper.selectById(f.getProductId());
            if (p == null) {
                continue;
            }
            rows.add(productBrief(p, f.getCreatedAt()));
        }
        return pageData(rows, total);
    }

    // ==================== 浏览历史 ====================

    /** 记录浏览（详情页调用；重复浏览刷新时间） */
    @PostMapping("/history/{productId}")
    public ApiResponse<Void> record(@AuthenticationPrincipal Long userId, @PathVariable Long productId) {
        BrowseHistory exist = historyMapper.selectOne(new LambdaQueryWrapper<BrowseHistory>()
                .eq(BrowseHistory::getUserId, userId)
                .eq(BrowseHistory::getProductId, productId));
        if (exist != null) {
            BrowseHistory upd = new BrowseHistory();
            upd.setId(exist.getId());
            upd.setViewedAt(LocalDateTime.now());
            historyMapper.updateById(upd);
        } else {
            BrowseHistory h = new BrowseHistory();
            h.setUserId(userId);
            h.setProductId(productId);
            h.setViewedAt(LocalDateTime.now());
            historyMapper.insert(h);
        }
        return ApiResponse.ok();
    }

    /** 浏览历史（懒加载分页，按时间倒序） */
    @GetMapping("/history")
    public ApiResponse<Map<String, Object>> history(@AuthenticationPrincipal Long userId,
                                                    @RequestParam(defaultValue = "1") long page,
                                                    @RequestParam(defaultValue = "20") long size) {
        List<BrowseHistory> list = historyMapper.selectList(new LambdaQueryWrapper<BrowseHistory>()
                .eq(BrowseHistory::getUserId, userId)
                .orderByDesc(BrowseHistory::getViewedAt)
                .last("LIMIT " + ((page - 1) * size) + "," + size));
        Long total = historyMapper.selectCount(new LambdaQueryWrapper<BrowseHistory>()
                .eq(BrowseHistory::getUserId, userId));
        List<Map<String, Object>> rows = new ArrayList<>();
        for (BrowseHistory h : list) {
            Product p = productMapper.selectById(h.getProductId());
            if (p == null) {
                continue;
            }
            rows.add(productBrief(p, h.getViewedAt()));
        }
        return pageData(rows, total);
    }

    @DeleteMapping("/history")
    public ApiResponse<Void> clearHistory(@AuthenticationPrincipal Long userId) {
        historyMapper.delete(new LambdaQueryWrapper<BrowseHistory>()
                .eq(BrowseHistory::getUserId, userId));
        return ApiResponse.ok();
    }

    // ==================== 通用 ====================

    private Map<String, Object> productBrief(Product p, Object time) {
        Map<String, Object> row = new HashMap<>();
        row.put("productId", p.getId());
        row.put("name", p.getName());
        row.put("imageUrl", p.getImageUrl());
        row.put("price", p.getPrice());
        row.put("sellingPoints", p.getSellingPoints());
        row.put("status", p.getStatus());
        row.put("time", time);
        return row;
    }

    private ApiResponse<Map<String, Object>> pageData(List<Map<String, Object>> rows, Long total) {
        Map<String, Object> data = new HashMap<>();
        data.put("records", rows);
        data.put("total", total);
        return ApiResponse.ok(data);
    }
}
