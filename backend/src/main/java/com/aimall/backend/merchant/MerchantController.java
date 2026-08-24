package com.aimall.backend.merchant;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.Merchant;
import com.aimall.backend.entity.Product;
import com.aimall.backend.entity.ProductReview;
import com.aimall.backend.mapper.MerchantMapper;
import com.aimall.backend.mapper.ProductMapper;
import com.aimall.backend.mapper.ProductReviewMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.math.BigDecimal;
import java.util.HashMap;
import java.util.Map;

/**
 * 商家端接口：/api/v1/merchant（仅 MERCHANT）
 * <p>商品上架模板：必填（商品名/品牌/类目/价格/库存/商品简介/商品图片）；
 * 必填（产地/发货地）；选填（材质/自定义商品信息/生产日期/详细介绍）。</p>
 */
@RestController
@RequestMapping("/api/v1/merchant")
@RequiredArgsConstructor
@Validated
public class MerchantController {

    private final MerchantMapper merchantMapper;
    private final ProductMapper productMapper;
    private final ProductReviewMapper reviewMapper;
    private final ProductImageService productImageService;

    /** 上架/编辑商品模板 */
    @Data
    public static class ProductTemplate {
        // ── 必填项 ──
        @NotBlank(message = "商品名为必填项")
        private String name;
        @NotBlank(message = "品牌为必填项")
        private String brand;
        @NotBlank(message = "类目为必填项")
        private String category;
        @NotNull(message = "价格为必填项")
        @Min(value = 1, message = "价格须大于0")
        private BigDecimal price;
        @NotNull(message = "库存为必填项")
        @Min(value = 0)
        private Integer stock;
        @NotBlank(message = "商品简介为必填项")
        private String sellingPoints;
        @NotBlank(message = "商品图片为必填项")
        private String imageUrl;
        @NotBlank(message = "产地为必填项")
        private String origin;
        @NotBlank(message = "发货地为必填项")
        private String shipFrom;
        // ── 选填项 ──
        private String specs;
        private String material;
        private String productionDate;
        private String description;
    }

    @Data
    public static class ReplyBody {
        @NotBlank
        private String content;
    }

    /** 商家信息（店铺卡片） */
    @GetMapping("/profile")
    public ApiResponse<Map<String, Object>> profile(@AuthenticationPrincipal Long userId) {
        Merchant merchant = requireMerchant(userId);
        Map<String, Object> vo = new HashMap<>();
        vo.put("merchantId", merchant.getId());
        vo.put("shopName", merchant.getShopName());
        vo.put("shopLogo", merchant.getShopLogo());
        vo.put("description", merchant.getDescription());
        vo.put("address", merchant.getAddress());
        // 在售/全部商品数
        Long onSale = productMapper.selectCount(new LambdaQueryWrapper<Product>()
                .eq(Product::getMerchantId, merchant.getId())
                .eq(Product::getStatus, "ON_SALE"));
        Long total = productMapper.selectCount(new LambdaQueryWrapper<Product>()
                .eq(Product::getMerchantId, merchant.getId()));
        vo.put("onSaleCount", onSale);
        vo.put("totalProducts", total);
        return ApiResponse.ok(vo);
    }

    /** 我的商品列表（懒加载分页，含下架） */
    @GetMapping("/products")
    public ApiResponse<Page<Product>> products(@AuthenticationPrincipal Long userId,
                                               @RequestParam(required = false) String status,
                                               @RequestParam(defaultValue = "1") long page,
                                               @RequestParam(defaultValue = "20") long size) {
        Merchant merchant = requireMerchant(userId);
        Page<Product> result = productMapper.selectPage(new Page<>(page, size),
                new LambdaQueryWrapper<Product>()
                        .eq(Product::getMerchantId, merchant.getId())
                        .eq(status != null && !status.isBlank(), Product::getStatus, status)
                        .orderByDesc(Product::getId));
        return ApiResponse.ok(result);
    }

    /** 上传商品图片 */
    @PostMapping(value = "/product-images", consumes = "multipart/form-data")
    public ApiResponse<Map<String, String>> uploadProductImage(@RequestParam("file") MultipartFile file) {
        return ApiResponse.ok(Map.of("url", productImageService.upload(file)));
    }

    /** 按模板上架商品（必填项由 Bean Validation 校验） */
    @PostMapping("/products")
    public ApiResponse<Long> create(@AuthenticationPrincipal Long userId,
                                    @Validated @RequestBody ProductTemplate tpl) {
        Merchant merchant = requireMerchant(userId);
        Product p = new Product();
        copyTemplate(tpl, p);
        p.setMerchantId(merchant.getId());
        p.setStatus("ON_SALE");
        p.setSales(0);
        productMapper.insert(p);
        return ApiResponse.ok(p.getId());
    }

    /** 编辑商品 */
    @PutMapping("/products/{id}")
    public ApiResponse<Void> update(@AuthenticationPrincipal Long userId, @PathVariable Long id,
                                    @Validated @RequestBody ProductTemplate tpl) {
        Product p = requireOwned(userId, id);
        copyTemplate(tpl, p);
        productMapper.updateById(p);
        return ApiResponse.ok();
    }

    /** 上架/下架 */
    @PostMapping("/products/{id}/status")
    public ApiResponse<Void> toggleStatus(@AuthenticationPrincipal Long userId, @PathVariable Long id,
                                          @RequestBody Map<String, String> body) {
        Product p = requireOwned(userId, id);
        String target = body.get("status");
        if (!"ON_SALE".equals(target) && !"OFF_SHELF".equals(target)) {
            throw new BizException(2001, "非法状态");
        }
        Product upd = new Product();
        upd.setId(p.getId());
        upd.setStatus(target);
        productMapper.updateById(upd);
        return ApiResponse.ok();
    }

    @DeleteMapping("/products/{id}")
    public ApiResponse<Void> remove(@AuthenticationPrincipal Long userId, @PathVariable Long id) {
        requireOwned(userId, id);
        productMapper.deleteById(id);
        return ApiResponse.ok();
    }

    /** 本店商品评论列表（懒加载） */
    @GetMapping("/reviews")
    public ApiResponse<Page<ProductReview>> reviews(@AuthenticationPrincipal Long userId,
                                                    @RequestParam(defaultValue = "1") long page,
                                                    @RequestParam(defaultValue = "20") long size) {
        Merchant merchant = requireMerchant(userId);
        Page<ProductReview> result = reviewMapper.selectPage(new Page<>(page, size),
                new LambdaQueryWrapper<ProductReview>()
                        .inSql(ProductReview::getProductId,
                                "SELECT id FROM product WHERE merchant_id = " + merchant.getId())
                        .orderByDesc(ProductReview::getId));
        return ApiResponse.ok(result);
    }

    /** 回复评论 */
    @PostMapping("/reviews/{id}/reply")
    public ApiResponse<Void> reply(@AuthenticationPrincipal Long userId, @PathVariable Long id,
                                   @RequestBody ReplyBody body) {
        Merchant merchant = requireMerchant(userId);
        ProductReview review = reviewMapper.selectById(id);
        if (review == null) {
            throw new BizException(2002, "评论不存在");
        }
        Product product = productMapper.selectById(review.getProductId());
        if (product == null || !merchant.getId().equals(product.getMerchantId())) {
            throw new BizException(2003, "无权回复该评论");
        }
        ProductReview upd = new ProductReview();
        upd.setId(review.getId());
        upd.setMerchantReply(body.getContent());
        reviewMapper.updateById(upd);
        return ApiResponse.ok();
    }

    private void copyTemplate(ProductTemplate tpl, Product p) {
        p.setName(tpl.getName());
        p.setBrand(tpl.getBrand());
        p.setCategory(tpl.getCategory());
        p.setPrice(tpl.getPrice());
        p.setStock(tpl.getStock());
        p.setSellingPoints(tpl.getSellingPoints());
        p.setImageUrl(tpl.getImageUrl());
        p.setSpecs(tpl.getSpecs());
        p.setMaterial(tpl.getMaterial());
        p.setOrigin(tpl.getOrigin());
        p.setShipFrom(tpl.getShipFrom());
        p.setProductionDate(tpl.getProductionDate());
        p.setDescription(tpl.getDescription());
    }

    private Merchant requireMerchant(Long userId) {
        Merchant merchant = merchantMapper.selectOne(new LambdaQueryWrapper<Merchant>()
                .eq(Merchant::getUserId, userId));
        if (merchant == null || !"ACTIVE".equals(merchant.getStatus())) {
            throw new BizException(2003, "商家账号未开通或已停用");
        }
        return merchant;
    }

    private Product requireOwned(Long userId, Long productId) {
        Merchant merchant = requireMerchant(userId);
        Product p = productMapper.selectById(productId);
        if (p == null || !merchant.getId().equals(p.getMerchantId())) {
            throw new BizException(2003, "无权操作该商品");
        }
        return p;
    }
}
