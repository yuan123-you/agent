package com.aimall.backend.order;

import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.Product;
import com.aimall.backend.mapper.OrderInfoMapper;
import com.aimall.backend.mapper.OrderItemMapper;
import com.aimall.backend.mapper.ProductMapper;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import static org.mockito.ArgumentMatchers.any;

/**
 * 库存乐观锁单测：并发冲突（影响行数 0）时绝不放行超卖。
 * 仅验证不可超卖的失败路径（针对 repo 最关键的 money 逻辑）。
 */
class OrderServiceTest {

    private final ProductMapper productMapper = mock(ProductMapper.class);
    private final OrderService service = new OrderService(
            mock(OrderInfoMapper.class), mock(OrderItemMapper.class), productMapper, mock(OrderSseNotifier.class));

    private static Product product(int stock, int version) {
        Product p = new Product();
        p.setId(1L);
        p.setStatus("ON_SALE");
        p.setName("测试商品");
        p.setPrice(new BigDecimal("99.00"));
        p.setStock(stock);
        p.setVersion(version);
        return p;
    }

    private static OrderDtos.CreateOrderRequest req(int quantity) {
        OrderDtos.CreateOrderRequest r = new OrderDtos.CreateOrderRequest();
        r.setProductId(1L);
        r.setQuantity(quantity);
        r.setReceiverName("张三");
        r.setReceiverPhone("13800000000");
        r.setReceiverAddress("测试地址");
        return r;
    }

    /** 持久冲突：5×updateById 均返回 0（他人并发已改版本）→ 必须抛异常，杜绝超卖 */
    @Test
    void create_throwsWhenOptimisticConflictPersists() {
        when(productMapper.selectById(1L)).thenReturn(product(10, 5));
        when(productMapper.updateById(any(Product.class))).thenReturn(0);

        BizException ex = assertThrows(BizException.class,
                () -> service.create(1L, req(5), "USER", null));
        assertEquals(2006, ex.getCode());
    }

    /** 库存不足：stock < qty 直接失败 */
    @Test
    void create_failsWhenStockInsufficient() {
        when(productMapper.selectById(1L)).thenReturn(product(3, 1));

        BizException ex = assertThrows(BizException.class,
                () -> service.create(1L, req(5), "USER", null));
        assertEquals(2006, ex.getCode());
    }

    /** 首次即扣减成功 */
    @Test
    void create_succeedsOnFirstAttempt() {
        when(productMapper.selectById(1L)).thenReturn(product(10, 5));
        when(productMapper.updateById(any(Product.class))).thenReturn(1);

        var order = service.create(1L, req(5), "USER", null);
        assertNotNull(order);
        assertEquals("PENDING_PAYMENT", order.getStatus());
    }
}