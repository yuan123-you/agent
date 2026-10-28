package com.aimall.backend.aftersale;
import com.aimall.backend.entity.*;
import com.aimall.backend.mapper.*;
import com.aimall.backend.promotion.PromotionService;
import com.aimall.backend.common.BizException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class AfterSaleServiceTest {
    OrderInfoMapper orders = mock(OrderInfoMapper.class); OrderItemMapper items = mock(OrderItemMapper.class);
    ProductMapper products = mock(ProductMapper.class); MallSkuMapper skus = mock(MallSkuMapper.class);
    AfterSaleMapper cases = mock(AfterSaleMapper.class); MerchantMapper merchants = mock(MerchantMapper.class);
    PromotionService promotions = mock(PromotionService.class);
    AfterSaleService service; OrderInfo order; OrderItem item; Product product;
    List<AfterSale> stored = new ArrayList<>();
    @BeforeEach void setup() {
        service = new AfterSaleService(orders, items, products, skus, cases, merchants, promotions, new ObjectMapper(), Clock.systemUTC());
        order = new OrderInfo(); order.setId(1L); order.setUserId(7L); order.setStatus("PAID"); order.setTotalAmount(new BigDecimal("80.00")); order.setOrderNo("ORDER1");
        item = new OrderItem(); item.setId(2L); item.setOrderId(1L); item.setProductId(3L); item.setQuantity(2); item.setPrice(new BigDecimal("50.00")); item.setSubtotal(new BigDecimal("100.00"));
        product = new Product(); product.setId(3L); product.setMerchantId(5L);
        when(orders.selectById(1L)).thenReturn(order); when(items.selectById(2L)).thenReturn(item); when(items.selectList(any())).thenReturn(List.of(item));
        when(products.selectById(3L)).thenReturn(product); when(cases.selectList(any())).thenAnswer(i -> new ArrayList<>(stored));
        when(cases.insert(any(AfterSale.class))).thenAnswer(i -> { AfterSale c=i.getArgument(0); c.setId((long)stored.size()+1); stored.add(c); return 1; });
        when(cases.selectById(anyLong())).thenAnswer(i -> stored.stream().filter(c -> c.getId().equals(i.getArgument(0))).findFirst().orElse(null));
        when(cases.updateById(any(AfterSale.class))).thenReturn(1);
    }
    AfterSale apply(String type, String amount) {
        return service.apply(7L,new AfterSaleService.Apply(1L,2L,type,"PERSONAL","不合适",1,new BigDecimal(amount),List.of(),UUID.randomUUID().toString()),null,null);
    }
    @Test void applicationUsesPaidAllocationAndDoesNotChangeOrderOrInventory() {
        AfterSale c=apply("REFUND_ONLY","40.00"); assertEquals("PENDING_MERCHANT",c.getStatus()); assertEquals("PAID",order.getStatus());
        verify(orders).lockOrder(1L); verify(products,never()).adjustAfterSaleStock(anyLong(),anyInt(),anyBoolean());
        assertThrows(BizException.class, () -> apply("REFUND_ONLY","40.01"));
    }
    @Test void blocksCrossBuyerAndDuplicateActiveItem() {
        assertThrows(BizException.class, () -> service.apply(8L,new AfterSaleService.Apply(1L,2L,"REFUND_ONLY","QUALITY","坏了",1,BigDecimal.ONE,List.of(),"other"),null,null));
        apply("REFUND_ONLY","40"); assertThrows(BizException.class, () -> apply("REFUND_ONLY","40"));
    }
    @Test void rejectsUnshippedExchange() { assertThrows(BizException.class, () -> apply("EXCHANGE","0")); }
    @Test void merchantCannotReviewAnotherMerchantsCase() {
        AfterSale c=apply("REFUND_ONLY","40"); Merchant m=new Merchant(); m.setId(99L); m.setStatus("ACTIVE"); when(merchants.selectOne(any())).thenReturn(m);
        assertThrows(BizException.class, () -> service.act(9L,"MERCHANT",c.getId(),new AfterSaleService.Command("APPROVE",null,null,null,null,null,null,false)));
    }
    @Test void simulatedRefundIsIdempotentAndDoesNotCancelAPartiallyRefundedOrder() {
        AfterSale c=apply("REFUND_ONLY","40"); c.setStatus("WAITING_REFUND"); c.setCurrentHandler("PLATFORM");
        service.act(9L,"ADMIN",c.getId(),new AfterSaleService.Command("REFUND",null,null,null,null,null,null,false));
        assertEquals("REFUNDED",c.getStatus()); assertEquals("SIMULATED",c.getRefundMode()); assertNotNull(c.getRefundReference());
        service.act(9L,"ADMIN",c.getId(),new AfterSaleService.Command("REFUND",null,null,null,null,null,null,false));
        verify(products,times(1)).adjustAfterSaleStock(3L,1,false); verify(orders,never()).updateById(any(OrderInfo.class));
    }
    @Test void aReturnCannotBeRefundedBeforeReceipt() {
        order.setStatus("DELIVERED"); AfterSale c=apply("RETURN_REFUND","40"); c.setStatus("WAITING_RETURN"); c.setCurrentHandler("PLATFORM");
        assertThrows(BizException.class, () -> service.act(9L,"ADMIN",c.getId(),new AfterSaleService.Command("REFUND",null,null,null,null,null,null,false)));
    }

    @Test void oldRejectedCaseCannotBeAppealedOverANewerActiveApplication() {
        AfterSale first=apply("REFUND_ONLY","40"); first.setStatus("REJECTED");
        apply("REFUND_ONLY","40");
        assertThrows(BizException.class,()->service.act(7L,"CUSTOMER",first.getId(),new AfterSaleService.Command("APPEAL","补充说明",null,null,null,null,null,false)));
    }
    @Test void requestKeyCannotSilentlyReuseADifferentRefundPayload() {
        var first=new AfterSaleService.Apply(1L,2L,"REFUND_ONLY","PERSONAL","不合适",1,new BigDecimal("40"),List.of(),"same");
        AfterSale c=service.apply(7L,first,null,null);when(cases.selectOne(any())).thenReturn(c);
        assertSame(c,service.apply(7L,first,null,null));
        assertThrows(BizException.class,()->service.apply(7L,new AfterSaleService.Apply(1L,2L,"REFUND_ONLY","PERSONAL","改成其他理由",1,new BigDecimal("1"),List.of(),"same"),null,null));
    }
    @Test void approvalRequiresAnActualReturnAddressAndRejectRequiresAReason() {
        order.setStatus("DELIVERED");AfterSale c=apply("RETURN_REFUND","40");c.setCurrentHandler("PLATFORM");
        assertThrows(BizException.class,()->service.act(9L,"ADMIN",c.getId(),new AfterSaleService.Command("APPROVE",null,null,null,null,null,null,false)));
        assertThrows(BizException.class,()->service.act(9L,"ADMIN",c.getId(),new AfterSaleService.Command("REJECT"," ",null,null,null,null,null,false)));
    }
    @Test void quoteAndSubmissionBothUseDiscountedAmount() {
        assertEquals(new BigDecimal("40.00"),service.quote(7L,1L,2L,"REFUND_ONLY",1));
        assertThrows(BizException.class,()->apply("REFUND_ONLY","50"));
        assertThrows(BizException.class,()->service.quote(7L,1L,2L,null,1));
    }

    @Test void explicitRefundCannotBeReplayedAsADefaultMaximumUnderTheSameKey() {
        var explicit=new AfterSaleService.Apply(1L,2L,"REFUND_ONLY","PERSONAL","不合适",1,new BigDecimal("10"),List.of(),"amount-mode");
        AfterSale c=service.apply(7L,explicit,null,null);when(cases.selectOne(any())).thenReturn(c);
        assertThrows(BizException.class,()->service.apply(7L,new AfterSaleService.Apply(1L,2L,"REFUND_ONLY","PERSONAL","不合适",1,null,List.of(),"amount-mode"),null,null));
    }
    @Test void defaultRefundRetryReturnsItsOriginalCaseWithoutRequotingChangedEligibility() {
        var request=new AfterSaleService.Apply(1L,2L,"REFUND_ONLY","PERSONAL","不合适",1,null,List.of(),"default-retry");
        AfterSale c=service.apply(7L,request,null,null);c.setStatus("CANCELLED");when(cases.selectOne(any())).thenReturn(c);
        order.setStatus("REFUNDED");
        assertSame(c,service.apply(7L,request,null,null));assertEquals(new BigDecimal("40.00"),c.getRequestedRefundAmount());
    }
    @Test void explicitMoneyFormattingDoesNotChangeRequestIdentity() {
        var first=new AfterSaleService.Apply(1L,2L,"REFUND_ONLY","PERSONAL","不合适",1,new BigDecimal("10.00"),List.of(),"formatted-money");
        AfterSale c=service.apply(7L,first,null,null);when(cases.selectOne(any())).thenReturn(c);
        assertSame(c,service.apply(7L,new AfterSaleService.Apply(1L,2L,"REFUND_ONLY","PERSONAL","不合适",1,new BigDecimal("10"),List.of(),"formatted-money"),null,null));
    }
}
