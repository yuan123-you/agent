package com.aimall.backend.internal;

import com.aimall.backend.entity.Product;
import com.aimall.backend.mapper.ProductMapper;
import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class InternalProductFactsTest {
    private final ProductMapper mapper = mock(ProductMapper.class);
    private final InternalToolController controller = new InternalToolController(mapper, null, null, null, null);

    private Product product() {
        Product product = new Product();
        product.setId(1L); product.setStatus("ON_SALE"); product.setOrigin("法国");
        product.setShipFrom("上海"); product.setMaterial("纯棉"); product.setProductionDate("2026-10-01");
        product.setDescription("真实商品说明".repeat(200));
        return product;
    }
    private void assertFacts(Map<String, Object> data) {
        assertEquals("法国", data.get("origin"));
        assertEquals("上海", data.get("shipFrom"));
        assertEquals("纯棉", data.get("material"));
        assertEquals("2026-10-01", data.get("productionDate"));
        assertEquals("真实商品说明".repeat(200), data.get("description"));
    }
    @Test void detailPreservesAvailableFactsAndFullDescription() {
        when(mapper.selectById(1L)).thenReturn(product());
        var body = new InternalToolController.ProductDetailBody(); body.setProductId(1L);
        assertFacts(controller.productDetail(body).getData());
    }
    @Test @SuppressWarnings("unchecked") void corpusSyncPreservesTheSameFactualFields() {
        when(mapper.selectList(any())).thenReturn(List.of(product()));
        var data = controller.productsAll().getData();
        assertFacts(((List<Map<String, Object>>) data.get("products")).get(0));
    }
}
