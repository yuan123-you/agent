package com.aimall.backend.product;

import com.aimall.backend.entity.Product;
import com.aimall.backend.mapper.ProductMapper;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.metadata.TableInfoHelper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import org.apache.ibatis.builder.MapperBuilderAssistant;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.mockito.ArgumentCaptor;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class ProductSearchSortingTest {
    @BeforeAll static void metadata() {
        TableInfoHelper.initTableInfo(new MapperBuilderAssistant(new MybatisConfiguration(),""),Product.class);
    }
    @ParameterizedTest @ValueSource(strings={"price_asc","price_desc","sales_desc"})
    @SuppressWarnings({"rawtypes","unchecked"})
    void explicitKeywordSortIsAppliedByTheDatabaseBeforePagination(String sort) {
        ProductMapper mapper=mock(ProductMapper.class);
        doAnswer(call -> call.getArgument(0)).when(mapper).selectPage(any(),any());
        var service=new ProductService(mapper,mock(CatalogService.class));
        service.list("蓝牙",null,null,null,sort,1,24);
        ArgumentCaptor<LambdaQueryWrapper<Product>> wrapper=ArgumentCaptor.forClass(LambdaQueryWrapper.class);
        verify(mapper).selectPage(any(),wrapper.capture());
        String sql=wrapper.getValue().getSqlSegment();
        String expected=switch(sort){case "price_asc" -> "ORDER BY price ASC";case "price_desc" -> "ORDER BY price DESC";default -> "ORDER BY sales DESC";};
        assertTrue(sql.contains(expected),sql);
        assertTrue(sql.contains("selling_points LIKE"),sql);
        verify(mapper,never()).searchByKeyword(anyString(),any(),any(),any(),any(),any(),anyLong(),anyLong());
    }
}
