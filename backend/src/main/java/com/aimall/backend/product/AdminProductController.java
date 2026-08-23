package com.aimall.backend.product;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.common.PageResult;
import com.aimall.backend.entity.Product;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.aimall.backend.mapper.ProductMapper;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 管理端商品接口：/api/v1/admin/products（仅 ADMIN）
 */
@RestController
@RequestMapping("/api/v1/admin/products")
@RequiredArgsConstructor
public class AdminProductController {

    private final ProductMapper productMapper;
    private final ProductService productService;

    @GetMapping
    public ApiResponse<PageResult<Product>> list(
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long size) {
        Page<Product> result = productMapper.selectPage(new Page<>(page, size),
                new LambdaQueryWrapper<Product>()
                        .eq(status != null && !status.isBlank(), Product::getStatus, status)
                        .and(keyword != null && !keyword.isBlank(),
                                w -> w.like(Product::getName, keyword).or().like(Product::getBrand, keyword))
                        .orderByDesc(Product::getId));
        return ApiResponse.ok(PageResult.of(result));
    }

    @PostMapping
    public ApiResponse<Long> create(@Valid @RequestBody ProductService.ProductSaveRequest req) {
        return ApiResponse.ok(productService.create(req));
    }


    @PostMapping("/{id}/status")
    public ApiResponse<Void> toggleStatus(@PathVariable Long id, @RequestBody Map<String, String> body) {
        productService.toggleStatus(id, body.get("status"));
        return ApiResponse.ok();
    }
}
