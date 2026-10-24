package com.aimall.backend.mapper;

import com.aimall.backend.entity.Product;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.math.BigDecimal;
import java.util.List;

@Mapper
public interface ProductMapper extends BaseMapper<Product> {

    @Select("SELECT COUNT(*) FROM product WHERE deleted=0 AND status='ON_SALE'")
    long countOnSale();

    /**
     * 关键词全文检索（ngram FULLTEXT，名称/品牌/卖点），按相关度排序。
     * 仅买家端搜索使用；AI 客服的 /internal/tools/product/search 保持原 LIKE 链路不变。
     */
    @Select("""
            <script>
            SELECT p.* FROM product p
            WHERE p.deleted = 0 AND p.status = 'ON_SALE' AND p.stock &gt; 0
              AND MATCH(p.name, p.brand, p.selling_points) AGAINST(#{kw} IN NATURAL LANGUAGE MODE)
              <if test='categoryId != null'>AND p.category_id = #{categoryId}</if>
              <if test='brandId != null'>AND p.brand_id = #{brandId}</if>
              <if test='category != null and category != ""'>AND p.category = #{category}</if>
              <if test='minPrice != null'>AND p.price &gt;= #{minPrice}</if>
              <if test='maxPrice != null'>AND p.price &lt;= #{maxPrice}</if>
            ORDER BY MATCH(p.name, p.brand, p.selling_points) AGAINST(#{kw} IN NATURAL LANGUAGE MODE) DESC, p.id DESC
            LIMIT #{offset}, #{size}
            </script>
            """)
    List<Product> searchByKeyword(@Param("kw") String kw,
                                  @Param("category") String category,
                                  @Param("categoryId") Long categoryId,
                                  @Param("brandId") Long brandId,
                                  @Param("minPrice") BigDecimal minPrice,
                                  @Param("maxPrice") BigDecimal maxPrice,
                                  @Param("offset") long offset,
                                  @Param("size") long size);

    /** 全文检索命中总数（与 searchByKeyword 同条件） */
    @Select("""
            <script>
            SELECT COUNT(*) FROM product p
            WHERE p.deleted = 0 AND p.status = 'ON_SALE' AND p.stock &gt; 0
              AND MATCH(p.name, p.brand, p.selling_points) AGAINST(#{kw} IN NATURAL LANGUAGE MODE)
              <if test='categoryId != null'>AND p.category_id = #{categoryId}</if>
              <if test='brandId != null'>AND p.brand_id = #{brandId}</if>
              <if test='category != null and category != ""'>AND p.category = #{category}</if>
              <if test='minPrice != null'>AND p.price &gt;= #{minPrice}</if>
              <if test='maxPrice != null'>AND p.price &lt;= #{maxPrice}</if>
            </script>
            """)
    long countByKeyword(@Param("kw") String kw,
                        @Param("category") String category,
                        @Param("categoryId") Long categoryId,
                        @Param("brandId") Long brandId,
                        @Param("minPrice") BigDecimal minPrice,
                        @Param("maxPrice") BigDecimal maxPrice);
}
