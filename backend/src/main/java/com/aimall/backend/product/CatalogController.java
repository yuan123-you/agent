package com.aimall.backend.product;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.entity.MallBrand;
import com.aimall.backend.entity.MallCategory;
import com.aimall.backend.entity.MallSku;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 买家端商城目录接口：/api/v1/catalog
 * 分类树、品牌、商品 SKU（对标 mall 的 portal 端 PMS 接口）。
 * 既有的 /api/v1/products/categories 字符串列表接口保持不变（AI 客服兼容）。
 */
@RestController
@RequestMapping("/api/v1/catalog")
@RequiredArgsConstructor
public class CatalogController {

    private final CatalogService catalogService;

    /** 分类树（仅显示状态，含在售商品计数） */
    @GetMapping("/categories")
    public ApiResponse<List<MallCategory>> categories() {
        return ApiResponse.ok(catalogService.buyerCategoryTree());
    }

    /** 在售品牌列表 */
    @GetMapping("/brands")
    public ApiResponse<List<MallBrand>> brands() {
        return ApiResponse.ok(catalogService.buyerBrands());
    }

    /** 商品在售 SKU 列表 */
    @GetMapping("/products/{id}/skus")
    public ApiResponse<List<MallSku>> skus(@PathVariable Long id) {
        return ApiResponse.ok(catalogService.buyerSkus(id));
    }
}
