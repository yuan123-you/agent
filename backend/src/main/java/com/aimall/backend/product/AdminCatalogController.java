package com.aimall.backend.product;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.entity.MallBrand;
import com.aimall.backend.entity.MallCategory;
import com.aimall.backend.entity.MallSku;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 管理端商城目录接口：/api/v1/admin/catalog（仅 ADMIN）
 */
@RestController
@RequestMapping("/api/v1/admin/catalog")
@RequiredArgsConstructor
public class AdminCatalogController {

    private final CatalogService catalogService;

    // ---------- 分类 ----------

    @GetMapping("/categories")
    public ApiResponse<List<MallCategory>> categories() {
        return ApiResponse.ok(catalogService.adminCategoryTree());
    }

    @PostMapping("/categories")
    public ApiResponse<Long> createCategory(@RequestBody CatalogService.CategorySaveRequest req) {
        return ApiResponse.ok(catalogService.createCategory(req));
    }

    @PutMapping("/categories/{id}")
    public ApiResponse<Void> updateCategory(@PathVariable Long id,
                                            @RequestBody CatalogService.CategorySaveRequest req) {
        catalogService.updateCategory(id, req);
        return ApiResponse.ok();
    }

    @DeleteMapping("/categories/{id}")
    public ApiResponse<Void> deleteCategory(@PathVariable Long id) {
        catalogService.deleteCategory(id);
        return ApiResponse.ok();
    }

    // ---------- 品牌 ----------

    @GetMapping("/brands")
    public ApiResponse<List<MallBrand>> brands() {
        return ApiResponse.ok(catalogService.adminBrands());
    }

    @PostMapping("/brands")
    public ApiResponse<Long> createBrand(@RequestBody CatalogService.BrandSaveRequest req) {
        return ApiResponse.ok(catalogService.createBrand(req));
    }

    @PutMapping("/brands/{id}")
    public ApiResponse<Void> updateBrand(@PathVariable Long id,
                                         @RequestBody CatalogService.BrandSaveRequest req) {
        catalogService.updateBrand(id, req);
        return ApiResponse.ok();
    }

    @DeleteMapping("/brands/{id}")
    public ApiResponse<Void> deleteBrand(@PathVariable Long id) {
        catalogService.deleteBrand(id);
        return ApiResponse.ok();
    }

    // ---------- SKU ----------

    @GetMapping("/products/{id}/skus")
    public ApiResponse<List<MallSku>> skus(@PathVariable Long id) {
        return ApiResponse.ok(catalogService.adminSkus(id));
    }

    @PostMapping("/products/{id}/skus")
    public ApiResponse<Long> createSku(@PathVariable Long id,
                                       @RequestBody CatalogService.SkuSaveRequest req) {
        return ApiResponse.ok(catalogService.createSku(id, req));
    }

    @PutMapping("/products/{id}/skus/{skuId}")
    public ApiResponse<Void> updateSku(@PathVariable Long id, @PathVariable Long skuId,
                                       @RequestBody CatalogService.SkuSaveRequest req) {
        catalogService.updateSku(id, skuId, req);
        return ApiResponse.ok();
    }

    @DeleteMapping("/products/{id}/skus/{skuId}")
    public ApiResponse<Void> deleteSku(@PathVariable Long id, @PathVariable Long skuId) {
        catalogService.deleteSku(id, skuId);
        return ApiResponse.ok();
    }

    /** SKU 变更后手动触发商品聚合刷新（库存/起价） */
    @PostMapping("/products/{id}/sync-aggregates")
    public ApiResponse<Void> syncAggregates(@PathVariable Long id) {
        catalogService.syncProductAggregates(id);
        return ApiResponse.ok();
    }
}
