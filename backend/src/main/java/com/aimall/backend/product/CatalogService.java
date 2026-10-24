package com.aimall.backend.product;

import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.MallBrand;
import com.aimall.backend.entity.MallCategory;
import com.aimall.backend.entity.MallSku;
import com.aimall.backend.entity.Product;
import com.aimall.backend.mapper.MallBrandMapper;
import com.aimall.backend.mapper.MallCategoryMapper;
import com.aimall.backend.mapper.MallSkuMapper;
import com.aimall.backend.mapper.ProductMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.*;
import java.util.stream.Collectors;

/**
 * 商城目录服务：分类树 / 品牌 / SKU（对标 mall 的 PMS 模块）。
 *
 * 兼容约束：product.category / product.brand 字符串列为冗余展示列，
 * 商品保存与 SKU 变更时由本服务同步维护，保证 AI 客服按字符串检索链路零改动。
 */
@Service
@Slf4j
@RequiredArgsConstructor
public class CatalogService {

    private final MallCategoryMapper categoryMapper;
    private final MallBrandMapper brandMapper;
    private final MallSkuMapper skuMapper;
    private final ProductMapper productMapper;

    private static final int MAX_CATEGORY_LEVEL = 2;

    // ==================== 买家端查询 ====================

    /** 分类树（仅显示状态），叶子节点带在售商品计数 */
    public List<MallCategory> buyerCategoryTree() {
        List<MallCategory> all = categoryMapper.selectList(new LambdaQueryWrapper<MallCategory>()
                .eq(MallCategory::getShowStatus, 1)
                .orderByAsc(MallCategory::getSort)
                .orderByAsc(MallCategory::getId));
        Map<Long, Long> counts = onSaleCounts();
        return buildTree(all, true, counts);
    }

    /** 在售品牌列表 */
    public List<MallBrand> buyerBrands() {
        return brandMapper.selectList(new LambdaQueryWrapper<MallBrand>()
                .eq(MallBrand::getShowStatus, 1)
                .orderByAsc(MallBrand::getSort)
                .orderByAsc(MallBrand::getId));
    }

    /** 在售 SKU 列表（买家端），要求商品在售 */
    public List<MallSku> buyerSkus(Long productId) {
        Product product = productMapper.selectById(productId);
        if (product == null || !"ON_SALE".equals(product.getStatus())) {
            throw new BizException(2002, "商品不存在或已下架");
        }
        return skuMapper.selectList(new LambdaQueryWrapper<MallSku>()
                .eq(MallSku::getProductId, productId)
                .eq(MallSku::getStatus, "ENABLE")
                .orderByAsc(MallSku::getId));
    }

    // ==================== 管理端 ====================

    /** 管理端分类树（含隐藏） */
    public List<MallCategory> adminCategoryTree() {
        List<MallCategory> all = categoryMapper.selectList(new LambdaQueryWrapper<MallCategory>()
                .orderByAsc(MallCategory::getSort)
                .orderByAsc(MallCategory::getId));
        return buildTree(all, false, onSaleCounts());
    }

    @Transactional
    public Long createCategory(CategorySaveRequest req) {
        String name = requireText(req.getName(), "分类名称不能为空");
        long parentId = req.getParentId() == null ? 0L : req.getParentId();
        int level = parentId == 0 ? 1 : 2;
        if (level > MAX_CATEGORY_LEVEL) {
            throw new BizException(2101, "分类最多支持两级");
        }
        if (parentId != 0 && categoryMapper.selectById(parentId) == null) {
            throw new BizException(2102, "上级分类不存在");
        }
        requireUniqueCategory(parentId, name, null);
        MallCategory c = new MallCategory();
        c.setParentId(parentId);
        c.setName(name);
        c.setLevel(level);
        c.setIcon(req.getIcon());
        c.setSort(req.getSort() == null ? 0 : req.getSort());
        c.setNavStatus(req.getNavStatus() == null ? 1 : req.getNavStatus());
        c.setShowStatus(req.getShowStatus() == null ? 1 : req.getShowStatus());
        c.setKeywords(req.getKeywords());
        c.setDescription(req.getDescription());
        categoryMapper.insert(c);
        return c.getId();
    }

    @Transactional
    public void updateCategory(Long id, CategorySaveRequest req) {
        MallCategory exists = requireCategory(id);
        if (req.getName() != null && !req.getName().isBlank()) {
            requireUniqueCategory(exists.getParentId(), req.getName().trim(), id);
        }
        MallCategory upd = new MallCategory();
        upd.setId(id);
        if (req.getName() != null) upd.setName(req.getName().trim());
        upd.setIcon(req.getIcon());
        upd.setSort(req.getSort());
        upd.setNavStatus(req.getNavStatus());
        upd.setShowStatus(req.getShowStatus());
        upd.setKeywords(req.getKeywords());
        upd.setDescription(req.getDescription());
        categoryMapper.updateById(upd);
    }

    @Transactional
    public void deleteCategory(Long id) {
        requireCategory(id);
        long children = categoryMapper.selectCount(new LambdaQueryWrapper<MallCategory>()
                .eq(MallCategory::getParentId, id));
        if (children > 0) {
            throw new BizException(2103, "存在子分类，无法删除");
        }
        long products = productMapper.selectCount(new LambdaQueryWrapper<Product>()
                .eq(Product::getCategoryId, id));
        if (products > 0) {
            throw new BizException(2104, "分类下仍有商品，无法删除");
        }
        categoryMapper.deleteById(id);
    }

    @Transactional
    public Long createBrand(BrandSaveRequest req) {
        String name = requireText(req.getName(), "品牌名称不能为空");
        requireUniqueBrand(name, null);
        MallBrand b = new MallBrand();
        copyBrand(req, b);
        b.setShowStatus(req.getShowStatus() == null ? 1 : req.getShowStatus());
        brandMapper.insert(b);
        return b.getId();
    }

    @Transactional
    public void updateBrand(Long id, BrandSaveRequest req) {
        requireBrand(id);
        if (req.getName() != null && !req.getName().isBlank()) {
            requireUniqueBrand(req.getName().trim(), id);
        }
        MallBrand upd = new MallBrand();
        upd.setId(id);
        copyBrand(req, upd);
        brandMapper.updateById(upd);
        if (upd.getName() != null) {
            syncProductName(upd.getId(), upd.getName());
        }
    }

    @Transactional
    public void deleteBrand(Long id) {
        requireBrand(id);
        long products = productMapper.selectCount(new LambdaQueryWrapper<Product>()
                .eq(Product::getBrandId, id));
        if (products > 0) {
            throw new BizException(2105, "品牌下仍有商品，无法删除");
        }
        brandMapper.deleteById(id);
    }

    public List<MallBrand> adminBrands() {
        return brandMapper.selectList(new LambdaQueryWrapper<MallBrand>()
                .orderByAsc(MallBrand::getSort)
                .orderByAsc(MallBrand::getId));
    }

    // ---------- SKU ----------

    public List<MallSku> adminSkus(Long productId) {
        requireProduct(productId);
        return skuMapper.selectList(new LambdaQueryWrapper<MallSku>()
                .eq(MallSku::getProductId, productId)
                .orderByAsc(MallSku::getId));
    }

    @Transactional
    public Long createSku(Long productId, SkuSaveRequest req) {
        requireProduct(productId);
        MallSku sku = new MallSku();
        copySku(productId, req, sku);
        validateSku(sku);
        skuMapper.insert(sku);
        syncProductAggregates(productId);
        return sku.getId();
    }

    @Transactional
    public void updateSku(Long productId, Long skuId, SkuSaveRequest req) {
        MallSku exists = skuMapper.selectById(skuId);
        if (exists == null || !exists.getProductId().equals(productId)) {
            throw new BizException(2106, "SKU不存在或不属于该商品");
        }
        MallSku upd = new MallSku();
        upd.setId(skuId);
        copySku(productId, req, upd);
        if (req.getPrice() != null) {
            validateSku(upd);
        }
        skuMapper.updateById(upd);
        syncProductAggregates(productId);
    }

    @Transactional
    public void deleteSku(Long productId, Long skuId) {
        MallSku exists = skuMapper.selectById(skuId);
        if (exists == null || !exists.getProductId().equals(productId)) {
            throw new BizException(2106, "SKU不存在或不属于该商品");
        }
        skuMapper.deleteById(skuId);
        syncProductAggregates(productId);
    }

    // ==================== 商品集成 ====================

    /**
     * 商品保存时按 categoryId/brandId 同步冗余名称列。
     * 分类/品牌 ID 为空时保留请求里的字符串（保持旧行为）。
     */
    public void syncCatalogNames(Product product, Long categoryId, Long brandId,
                                 String fallbackCategory, String fallbackBrand) {
        if (categoryId != null) {
            MallCategory c = categoryMapper.selectById(categoryId);
            if (c == null) {
                throw new BizException(2102, "分类不存在");
            }
            product.setCategoryId(categoryId);
            product.setCategory(c.getName());
        } else if (fallbackCategory != null && !fallbackCategory.isBlank()) {
            product.setCategory(fallbackCategory.trim());
        }
        if (brandId != null) {
            MallBrand b = brandMapper.selectById(brandId);
            if (b == null) {
                throw new BizException(2102, "品牌不存在");
            }
            product.setBrandId(brandId);
            product.setBrand(b.getName());
        } else if (fallbackBrand != null && !fallbackBrand.isBlank()) {
            product.setBrand(fallbackBrand.trim());
        }
    }

    /**
     * SKU 变更后同步商品聚合字段：
     * stock = Σ SKU 库存（保证列表过滤 stock>0 与 AI 检索语义一致）；
     * price = min SKU 价（起价语义）。
     */
    void syncProductAggregates(Long productId) {
        List<MallSku> skus = skuMapper.selectList(new LambdaQueryWrapper<MallSku>()
                .eq(MallSku::getProductId, productId)
                .eq(MallSku::getStatus, "ENABLE"));
        Product product = productMapper.selectById(productId);
        if (product == null) {
            return;
        }
        Product upd = new Product();
        upd.setId(productId);
        upd.setVersion(product.getVersion());
        if (skus.isEmpty()) {
            // SKU 全部移除：商品回落到自身库存（现值保持），价格不动
            productMapper.updateById(upd);
            return;
        }
        int totalStock = skus.stream().mapToInt(MallSku::getStock).sum();
        BigDecimal minPrice = skus.stream().map(MallSku::getPrice)
                .filter(Objects::nonNull).min(BigDecimal::compareTo).orElse(null);
        upd.setStock(totalStock);
        if (minPrice != null) {
            upd.setPrice(minPrice);
        }
        productMapper.updateById(upd);
    }

    // ==================== 内部工具 ====================

    /** 品牌改名后同步该品牌下商品的冗余品牌名列（AI 检索兼容） */
    private void syncProductName(Long brandId, String name) {
        List<Product> products = productMapper.selectList(new LambdaQueryWrapper<Product>()
                .select(Product::getId, Product::getVersion)
                .eq(Product::getBrandId, brandId));
        for (Product p : products) {
            Product upd = new Product();
            upd.setId(p.getId());
            upd.setVersion(p.getVersion());
            upd.setBrand(name);
            productMapper.updateById(upd);
        }
    }

    private Map<Long, Long> onSaleCounts() {
        List<Product> rows = productMapper.selectList(new LambdaQueryWrapper<Product>()
                .select(Product::getCategoryId)
                .eq(Product::getStatus, "ON_SALE")
                .isNotNull(Product::getCategoryId));
        return rows.stream().collect(Collectors.groupingBy(Product::getCategoryId, Collectors.counting()));
    }

    private List<MallCategory> buildTree(List<MallCategory> all, boolean onlyShow,
                                         Map<Long, Long> counts) {
        Map<Long, List<MallCategory>> byParent = all.stream()
                .filter(c -> !onlyShow || c.getShowStatus() == 1)
                .collect(Collectors.groupingBy(MallCategory::getParentId));
        List<MallCategory> roots = byParent.getOrDefault(0L, new ArrayList<>());
        for (MallCategory root : roots) {
            List<MallCategory> children = byParent.getOrDefault(root.getId(), new ArrayList<>());
            children.forEach(c -> c.setProductCount(counts.getOrDefault(c.getId(), 0L)));
            root.setChildren(children);
            root.setProductCount(children.stream().mapToLong(c -> c.getProductCount() == null ? 0 : c.getProductCount()).sum());
        }
        roots.sort(Comparator.comparing(MallCategory::getSort, Comparator.nullsLast(Integer::compareTo))
                .thenComparing(MallCategory::getId));
        return roots;
    }

    private void requireUniqueCategory(long parentId, String name, Long excludeId) {
        long dup = categoryMapper.selectCount(new LambdaQueryWrapper<MallCategory>()
                .eq(MallCategory::getParentId, parentId)
                .eq(MallCategory::getName, name)
                .ne(excludeId != null, MallCategory::getId, excludeId));
        if (dup > 0) {
            throw new BizException(2107, "同级下已存在同名分类");
        }
    }

    private void requireUniqueBrand(String name, Long excludeId) {
        long dup = brandMapper.selectCount(new LambdaQueryWrapper<MallBrand>()
                .eq(MallBrand::getName, name)
                .ne(excludeId != null, MallBrand::getId, excludeId));
        if (dup > 0) {
            throw new BizException(2107, "品牌名称已存在");
        }
    }

    private MallCategory requireCategory(Long id) {
        MallCategory c = categoryMapper.selectById(id);
        if (c == null) {
            throw new BizException(2102, "分类不存在");
        }
        return c;
    }

    private MallBrand requireBrand(Long id) {
        MallBrand b = brandMapper.selectById(id);
        if (b == null) {
            throw new BizException(2102, "品牌不存在");
        }
        return b;
    }

    private Product requireProduct(Long id) {
        Product p = productMapper.selectById(id);
        if (p == null) {
            throw new BizException(2002, "商品不存在");
        }
        return p;
    }

    private void copyBrand(BrandSaveRequest req, MallBrand b) {
        if (req.getName() != null) b.setName(req.getName().trim());
        b.setFirstLetter(req.getFirstLetter());
        b.setLogo(req.getLogo());
        b.setBigPic(req.getBigPic());
        b.setBrandStory(req.getBrandStory());
        if (req.getSort() != null) b.setSort(req.getSort());
        if (req.getShowStatus() != null) b.setShowStatus(req.getShowStatus());
    }

    private void copySku(Long productId, SkuSaveRequest req, MallSku sku) {
        sku.setProductId(productId);
        sku.setSkuCode(req.getSkuCode());
        sku.setSpData(req.getSpData());
        sku.setPrice(req.getPrice());
        sku.setStock(req.getStock() == null ? 0 : req.getStock());
        sku.setLowStock(req.getLowStock());
        sku.setPic(req.getPic());
        if (req.getStatus() != null) sku.setStatus(req.getStatus());
    }

    private void validateSku(MallSku sku) {
        if (sku.getPrice() == null || sku.getPrice().signum() < 0) {
            throw new BizException(2001, "SKU价格无效");
        }
        if (sku.getStock() == null || sku.getStock() < 0) {
            throw new BizException(2001, "SKU库存无效");
        }
    }

    private String requireText(String v, String msg) {
        if (v == null || v.isBlank()) {
            throw new BizException(2001, msg);
        }
        return v.trim();
    }

    // ==================== 请求体 ====================

    @lombok.Data
    public static class CategorySaveRequest {
        private Long parentId;
        private String name;
        private String icon;
        private Integer sort;
        private Integer navStatus;
        private Integer showStatus;
        private String keywords;
        private String description;
    }

    @lombok.Data
    public static class BrandSaveRequest {
        private String name;
        private String firstLetter;
        private String logo;
        private String bigPic;
        private String brandStory;
        private Integer sort;
        private Integer showStatus;
    }

    @lombok.Data
    public static class SkuSaveRequest {
        private String skuCode;
        private String spData;
        private BigDecimal price;
        private Integer stock;
        private Integer lowStock;
        private String pic;
        private String status;
    }
}
