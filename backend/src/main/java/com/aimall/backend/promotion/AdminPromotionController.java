package com.aimall.backend.promotion;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.entity.MallCoupon;
import com.aimall.backend.entity.MallSeckill;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 管理端营销接口：/api/v1/admin/promotions（仅 ADMIN）
 */
@RestController
@RequestMapping("/api/v1/admin/promotions")
@RequiredArgsConstructor
public class AdminPromotionController {

    private final PromotionService promotionService;

    // ---------- 优惠券 ----------

    @GetMapping("/coupons")
    public ApiResponse<List<MallCoupon>> coupons() {
        return ApiResponse.ok(promotionService.adminCoupons());
    }

    @PostMapping("/coupons")
    public ApiResponse<Long> createCoupon(@RequestBody PromotionService.CouponSaveRequest req) {
        return ApiResponse.ok(promotionService.createCoupon(req));
    }

    @PutMapping("/coupons/{id}")
    public ApiResponse<Void> updateCoupon(@PathVariable Long id,
                                          @RequestBody PromotionService.CouponSaveRequest req) {
        promotionService.updateCoupon(id, req);
        return ApiResponse.ok();
    }

    @DeleteMapping("/coupons/{id}")
    public ApiResponse<Void> deleteCoupon(@PathVariable Long id) {
        promotionService.deleteCoupon(id);
        return ApiResponse.ok();
    }

    // ---------- 秒杀 ----------

    @GetMapping("/seckills")
    public ApiResponse<List<MallSeckill>> seckills() {
        return ApiResponse.ok(promotionService.adminSeckills());
    }

    @PostMapping("/seckills")
    public ApiResponse<Long> createSeckill(@RequestBody PromotionService.SeckillSaveRequest req) {
        return ApiResponse.ok(promotionService.createSeckill(req));
    }

    @PutMapping("/seckills/{id}")
    public ApiResponse<Void> updateSeckill(@PathVariable Long id,
                                           @RequestBody PromotionService.SeckillSaveRequest req) {
        promotionService.updateSeckill(id, req);
        return ApiResponse.ok();
    }

    @DeleteMapping("/seckills/{id}")
    public ApiResponse<Void> deleteSeckill(@PathVariable Long id) {
        promotionService.deleteSeckill(id);
        return ApiResponse.ok();
    }
}
