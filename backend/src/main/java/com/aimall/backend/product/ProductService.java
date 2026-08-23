package com.aimall.backend.product;

import com.aimall.backend.entity.Product;
import com.aimall.backend.common.BizException;
import com.aimall.backend.common.PageResult;
import com.aimall.backend.mapper.ProductMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;

/**
 * 商品服务：买家端检索 + 管理端创建与状态维护
 */
@Service
@RequiredArgsConstructor
public class ProductService {

    private final ProductMapper productMapper;

    public PageResult<Product> list(String keyword, String category, BigDecimal minPrice,
                                    BigDecimal maxPrice, String sort, long page, long size) {
        LambdaQueryWrapper<Product> wrapper = new LambdaQueryWrapper<Product>()
                .eq(Product::getStatus, "ON_SALE")
                .gt(Product::getStock, 0)
                .eq(category != null && !category.isBlank(), Product::getCategory, category)
                .ge(minPrice != null, Product::getPrice, minPrice)
                .le(maxPrice != null, Product::getPrice, maxPrice)
                .and(keyword != null && !keyword.isBlank(), w -> w
                        .like(Product::getName, keyword)
                        .or().like(Product::getBrand, keyword)
                        .or().like(Product::getSellingPoints, keyword));
        if ("price_asc".equals(sort)) {
            wrapper.orderByAsc(Product::getPrice);
        } else if ("price_desc".equals(sort)) {
            wrapper.orderByDesc(Product::getPrice);
        } else {
            wrapper.orderByDesc(Product::getId);
        }
        Page<Product> result = productMapper.selectPage(new Page<>(page, size), wrapper);
        return PageResult.of(result);
    }

    public Product detail(Long id) {
        Product product = productMapper.selectById(id);
        if (product == null || !"ON_SALE".equals(product.getStatus())) {
            throw new BizException(2002, "商品不存在或已下架");
        }
        return product;
    }

    /** 全部分类编码（有在售商品的），升序 */
    public java.util.List<String> categories() {
        return productMapper.selectObjs(new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<Product>()
                        .select(Product::getCategory)
                        .eq(Product::getStatus, "ON_SALE")
                        .groupBy(Product::getCategory)
                        .orderByAsc(Product::getCategory))
                .stream().map(String::valueOf).toList();
    }

    // ---------- 管理端 ----------

    public Long create(ProductSaveRequest req) {
        Product product = new Product();
        copy(req, product);
        product.setStatus("ON_SALE");
        productMapper.insert(product);
        return product.getId();
    }


    public void toggleStatus(Long id, String status) {
        if (!"ON_SALE".equals(status) && !"OFF_SHELF".equals(status)) {
            throw new BizException(2001, "非法的商品状态");
        }
        Product product = requireProduct(id);
        Product update = new Product();
        update.setId(product.getId());
        update.setStatus(status);
        productMapper.updateById(update);
    }

    private Product requireProduct(Long id) {
        Product product = productMapper.selectById(id);
        if (product == null) {
            throw new BizException(2002, "商品不存在");
        }
        return product;
    }

    private void copy(ProductSaveRequest req, Product product) {
        product.setName(req.getName());
        product.setCategory(req.getCategory());
        product.setBrand(req.getBrand());
        product.setPrice(req.getPrice());
        product.setStock(req.getStock());
        product.setImageUrl(req.getImageUrl());
        product.setDescription(req.getDescription());
        product.setSellingPoints(req.getSellingPoints());
        product.setSpecs(req.getSpecs());
    }

    @Data
    public static class ProductSaveRequest {
        private String name;
        private String category;
        private String brand;
        private BigDecimal price;
        private Integer stock;
        private String imageUrl;
        private String description;
        private String sellingPoints;
        private String specs;
    }
}
