package com.aimall.backend.order;

import com.aimall.backend.address.AddressService;
import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.*;
import com.aimall.backend.mapper.*;
import com.aimall.backend.promotion.PromotionService;
import java.math.BigDecimal;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class OrderSkuAndAgentQuoteTest {
    final OrderInfoMapper orders = mock(OrderInfoMapper.class);
    final OrderItemMapper items = mock(OrderItemMapper.class);
    final ProductMapper products = mock(ProductMapper.class);
    final MallSkuMapper skus = mock(MallSkuMapper.class);
    final PromotionService promotions = mock(PromotionService.class);
    final OrderSseNotifier notifier = mock(OrderSseNotifier.class);
    final OrderService service = new OrderService(orders, items, products, skus, promotions, notifier, mock(AddressService.class));
    OrderSkuAndAgentQuoteTest() {
        Product p = new Product(); p.setId(1L); p.setName("Product"); p.setStatus("ON_SALE");
        p.setPrice(new BigDecimal("10.00")); p.setStock(5); p.setVersion(0);
        when(products.selectById(1L)).thenReturn(p); when(products.updateById(any(Product.class))).thenReturn(1);
        when(orders.insert(any(OrderInfo.class))).thenAnswer(i -> { i.<OrderInfo>getArgument(0).setId(9L); return 1; });
    }
    OrderDtos.CreateOrderRequest request(Long skuId) {
        var r = new OrderDtos.CreateOrderRequest(); r.setProductId(1L); r.setSkuId(skuId); r.setQuantity(2);
        r.setReceiverName("Buyer"); r.setReceiverPhone("13800000000"); r.setReceiverAddress("Address"); return r;
    }
    @ParameterizedTest @NullSource @ValueSource(longs={0,-1})
    void skuBackedProductsCannotFallBackToAggregateIncludingAllDisabled(Long id) {
        when(skus.selectCount(any())).thenReturn(1L);
        BizException error = assertThrows(BizException.class, () -> service.create(7L,request(id),"AI",2L));
        assertTrue(error.getMessage().contains("选择规格"));
        assertThrows(BizException.class, () -> service.checkout(7L,List.of(new OrderService.CheckoutItem(1L,id,2)),null,"Buyer","13800000000","Address",null));
        verify(products,never()).updateById(any(Product.class)); verifyNoInteractions(orders,items,notifier);
    }
    @Test void legacyProductWithoutAnySkuStillCreates() {
        assertEquals(new BigDecimal("20.00"),service.create(7L,request(null),"USER",null).getTotalAmount());
    }
    @Test void explicitValidSkuReservesVariantAndUsesItsPrice() {
        MallSku s = new MallSku(); s.setId(3L); s.setProductId(1L); s.setStatus("ENABLE"); s.setStock(4); s.setVersion(0); s.setPrice(new BigDecimal("12.00"));
        when(skus.selectById(3L)).thenReturn(s); when(skus.updateById(any(MallSku.class))).thenReturn(1);
        assertEquals(new BigDecimal("24.00"),service.create(7L,request(3L),"USER",null).getTotalAmount());
        verify(skus).updateById(argThat((MallSku v) -> v.getStock()==2));
    }
    BigDecimal quote(int quantity) {
        return service.quoteForAgent(7L,1L,quantity);
    }
    @Test void agentQuoteReturnsEffectiveTotalWithoutReservationsOrOrderWrites() {
        assertEquals(new BigDecimal("20.00"),quote(2));
        MallSeckill s = new MallSeckill(); s.setId(4L); s.setSeckillPrice(new BigDecimal("3.00")); s.setSeckillStock(3); s.setSeckillLimit(2);
        when(promotions.resolveSeckill(1L)).thenReturn(s);
        assertEquals(new BigDecimal("6.00"),quote(2));
        verify(products,never()).updateById(any(Product.class)); verify(skus,never()).updateById(any(MallSku.class));
        verify(promotions,never()).deductSeckillStock(any(),anyInt()); verifyNoInteractions(orders,items,notifier);
    }
    @Test void quoteRejectsSkuProductsAndInvalidQuantitiesOrStock() {
        when(skus.selectCount(any())).thenReturn(1L); assertThrows(BizException.class,()->quote(1));
        when(skus.selectCount(any())).thenReturn(0L); assertThrows(BizException.class,()->quote(0));
        assertThrows(BizException.class,()->quote(6));
    }
}
