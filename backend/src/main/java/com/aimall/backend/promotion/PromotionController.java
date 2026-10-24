package com.aimall.backend.promotion;

import com.aimall.backend.common.ApiResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

/**
 * 买家端营销接口：/api/v1/promotions
 * 领券中心、我的优惠券、下单可用券预览、进行中秒杀。
 */
@RestController
@RequestMapping("/api/v1/promotions")
@RequiredArgsConstructor
public class PromotionController {

    private final PromotionService promotionService;

    /** 可领券列表（登录买家） */
    @GetMapping("/coupons")
    public ApiResponse<List<Map<String, Object>>> coupons(@AuthenticationPrincipal Long userId) {
        return ApiResponse.ok(promotionService.receivableCoupons(userId));
    }

    /** 领券（每人每券限领一张） */
    @PostMapping("/coupons/{id}/receive")
    public ApiResponse<Long> receive(@AuthenticationPrincipal Long userId, @PathVariable Long id) {
        return ApiResponse.ok(promotionService.receive(userId, id));
    }

    /** 我的优惠券 */
    @GetMapping("/my-coupons")
    public ApiResponse<List<Map<String, Object>>> myCoupons(@AuthenticationPrincipal Long userId) {
        return ApiResponse.ok(promotionService.myCoupons(userId));
    }

    /** 结算可用券预览（按订单金额判断门槛） */
    @GetMapping("/usable-coupons")
    public ApiResponse<List<Map<String, Object>>> usableCoupons(
            @AuthenticationPrincipal Long userId,
            @RequestParam BigDecimal amount) {
        return ApiResponse.ok(promotionService.usableCouponsFor(userId, amount));
    }

    /** 进行中/即将开始的秒杀 */
    @GetMapping("/seckills")
    public ApiResponse<List<Map<String, Object>>> seckills() {
        return ApiResponse.ok(promotionService.activeSeckills());
    }
}
