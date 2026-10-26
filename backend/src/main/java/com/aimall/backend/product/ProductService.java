package com.aimall.backend.product;

import com.aimall.backend.entity.Product;
import com.aimall.backend.common.BizException;
import com.aimall.backend.common.PageResult;
import com.aimall.backend.mapper.ProductMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.ObjectReader;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.List;

/**
 * 商品服务：买家端检索 + 管理端创建与状态维护
 */
@Service
@RequiredArgsConstructor
public class ProductService {

    private static final ObjectReader SPECS_JSON = new ObjectMapper().reader()
            .with(DeserializationFeature.FAIL_ON_TRAILING_TOKENS);

    private final ProductMapper productMapper;
    private final CatalogService catalogService;

    public PageResult<Product> list(String keyword, String category, BigDecimal minPrice,
                                    BigDecimal maxPrice, String sort, long page, long size) {
        return list(keyword, category, null, null, minPrice, maxPrice, sort, page, size);
    }

    /** 支持按分类/品牌 ID 过滤（旧 category 字符串参数保持兼容） */
    public PageResult<Product> list(String keyword, String category, Long categoryId, Long brandId,
                                    BigDecimal minPrice, BigDecimal maxPrice, String sort, long page, long size) {
        // Fulltext queries use explicit LIMIT rather than the pagination interceptor.
        if (page < 1 || size < 1 || size > 500 || page - 1 > Long.MAX_VALUE / size) {
            throw new BizException(2001, "分页参数不合法，page须为正整数，size范围1~500");
        }
        // 有关键词优先走 ngram 全文检索（相关度排序）；索引/语法异常时降级 LIKE
        boolean explicitSort = "price_asc".equals(sort) || "price_desc".equals(sort) || "sales_desc".equals(sort);
        // The relevance-only fulltext query cannot provide a global explicit sort before LIMIT.
        if (keyword != null && !keyword.isBlank() && !explicitSort) {
            try {
                long total = productMapper.countByKeyword(keyword.trim(), category, categoryId, brandId,
                        minPrice, maxPrice);
                List<Product> records = total > 0
                        ? productMapper.searchByKeyword(keyword.trim(), category, categoryId, brandId,
                                minPrice, maxPrice, (page - 1) * size, size)
                        : List.of();
                Page<Product> pageObj = new Page<>(page, size, total);
                pageObj.setRecords(records);
                return PageResult.of(pageObj);
            } catch (org.springframework.dao.DataAccessException fulltextUnavailable) {
                // FULLTEXT 索引不可用时回退原 LIKE 检索
            }
        }
        LambdaQueryWrapper<Product> wrapper = new LambdaQueryWrapper<Product>()
                .eq(Product::getStatus, "ON_SALE")
                .gt(Product::getStock, 0)
                .eq(category != null && !category.isBlank(), Product::getCategory, category)
                .eq(categoryId != null, Product::getCategoryId, categoryId)
                .eq(brandId != null, Product::getBrandId, brandId)
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
        } else if ("sales_desc".equals(sort)) {
            wrapper.orderByDesc(Product::getSales).orderByDesc(Product::getId);
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
        // 按分类/品牌 ID 同步冗余名称列；ID 缺省时回落到字符串（旧行为）
        catalogService.syncCatalogNames(product, req.getCategoryId(), req.getBrandId(),
                req.getCategory(), req.getBrand());
        product.setPrice(req.getPrice());
        product.setStock(req.getStock());
        product.setImageUrl(req.getImageUrl());
        product.setDescription(req.getDescription());
        product.setSellingPoints(req.getSellingPoints());
        String specs = req.getSpecs();
        if (specs != null && !specs.isBlank()) {
            try {
                SPECS_JSON.readTree(specs);
            } catch (JsonProcessingException e) {
                throw new BizException(2001, "商品规格须为合法JSON");
            }
            product.setSpecs(specs);
        } else {
            product.setSpecs(null);
        }
    }

    @Data
    public static class ProductSaveRequest {
        private String name;
        private String category;
        private Long categoryId;
        private String brand;
        private Long brandId;
        private BigDecimal price;
        private Integer stock;
        private String imageUrl;
        private String description;
        private String sellingPoints;
        private String specs;
    }
}
