package com.aimall.backend.product;

import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.Product;
import com.aimall.backend.mapper.ProductMapper;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.mockito.ArgumentCaptor;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class ProductSpecsValidationTest {
    @ParameterizedTest
    @ValueSource(strings={"QA", "{", "{} trailing", "{} []"})
    void invalidJsonIsRejectedBeforeInsert(String specs) {
        var mapper=mock(ProductMapper.class);
        var request=new ProductService.ProductSaveRequest(); request.setSpecs(specs);
        var service=new ProductService(mapper,mock(CatalogService.class));
        assertEquals(2001,assertThrows(BizException.class,() -> service.create(request)).getCode());
        verifyNoInteractions(mapper);
    }
    @ParameterizedTest
    @ValueSource(strings={"{}", "[]", "null", "{\"屏幕\":\"6.7英寸\"}"})
    void validJsonIsPreserved(String specs) {
        var mapper=mock(ProductMapper.class); when(mapper.insert(any(Product.class))).thenReturn(1);
        var request=new ProductService.ProductSaveRequest(); request.setSpecs(specs);
        new ProductService(mapper,mock(CatalogService.class)).create(request);
        var capture=ArgumentCaptor.forClass(Product.class); verify(mapper).insert(capture.capture());
        assertEquals(specs,capture.getValue().getSpecs());
    }
    @ParameterizedTest
    @ValueSource(strings={"", "  "})
    void blankOptionalSpecsAreStoredAsSqlNull(String specs) {
        var mapper=mock(ProductMapper.class); when(mapper.insert(any(Product.class))).thenReturn(1);
        var request=new ProductService.ProductSaveRequest(); request.setSpecs(specs);
        new ProductService(mapper,mock(CatalogService.class)).create(request);
        var capture=ArgumentCaptor.forClass(Product.class); verify(mapper).insert(capture.capture());
        assertNull(capture.getValue().getSpecs());
    }
}
