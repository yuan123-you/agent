package com.aimall.backend.product;

import com.aimall.backend.common.BizException;
import com.aimall.backend.mapper.ProductMapper;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class ProductSearchPaginationTest {
    @Test
    void fulltextSearchRejectsInvalidOrUnboundedPaginationBeforeQuerying() {
        long[][] invalid = {{0,20}, {1,-1}, {1,0}, {1,501}, {Long.MAX_VALUE,20}};
        for (long[] input : invalid) {
            ProductMapper mapper = mock(ProductMapper.class);
            ProductService service = new ProductService(mapper, mock(CatalogService.class));
            BizException error = assertThrows(BizException.class,
                    () -> service.list("商品", null, null, null, null, input[0], input[1]));
            assertEquals(2001, error.getCode());
            verifyNoInteractions(mapper);
        }
    }
}
