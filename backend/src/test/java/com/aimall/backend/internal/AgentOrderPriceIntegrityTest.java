package com.aimall.backend.internal;

import com.aimall.backend.address.AddressService;
import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.AgentAction;
import com.aimall.backend.entity.Conversation;
import com.aimall.backend.entity.OrderInfo;
import com.aimall.backend.entity.Product;
import com.aimall.backend.mapper.AgentActionMapper;
import com.aimall.backend.mapper.AfterSaleMapper;
import com.aimall.backend.mapper.ConversationMapper;
import com.aimall.backend.mapper.OrderInfoMapper;
import com.aimall.backend.mapper.OrderItemMapper;
import com.aimall.backend.mapper.ProductMapper;
import com.aimall.backend.order.OrderDtos;
import com.aimall.backend.order.OrderService;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.mockito.ArgumentCaptor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/** Catalog-price checks must run before quotes or order confirmation side effects. */
class AgentOrderPriceIntegrityTest {
    private final AgentActionMapper actions = mock(AgentActionMapper.class);
    private final ProductMapper products = mock(ProductMapper.class);
    private final ConversationMapper conversations = mock(ConversationMapper.class);
    private final OrderInfoMapper orders = mock(OrderInfoMapper.class);
    private final OrderService orderService = mock(OrderService.class);
    private final StringRedisTemplate redis = mock(StringRedisTemplate.class);
    private final ObjectMapper json = new ObjectMapper();
    private final Clock clock = Clock.fixed(Instant.parse("2026-10-08T12:00:00Z"), ZoneOffset.UTC);
    private final AgentOrderActionService service = new AgentOrderActionService(mock(AddressService.class),
            actions, products, conversations, orders, mock(OrderItemMapper.class), mock(AfterSaleMapper.class),
            orderService, redis, json, clock);

    private AgentOrderActionService.PrepareRequest request() {
        return new AgentOrderActionService.PrepareRequest(7L, 20L, 10L, 2,
                "Receiver", "13800000000", "Test address");
    }

    private void catalog(String price) {
        Product product = new Product();
        product.setId(10L);
        product.setName("Snapshot product");
        product.setStatus("ON_SALE");
        product.setStock(10);
        product.setPrice(price == null ? null : new BigDecimal(price));
        when(products.selectById(10L)).thenReturn(product);
        Conversation conversation = new Conversation();
        conversation.setId(20L);
        conversation.setUserId(7L);
        when(conversations.selectById(20L)).thenReturn(conversation);
    }

    private void pendingAction() throws Exception {
        AgentAction action = new AgentAction();
        action.setActionId("act-price");
        action.setUserId(7L);
        action.setConversationId(20L);
        action.setType(AgentOrderActionService.ORDER_CREATE);
        action.setStatus("PENDING");
        action.setPayload(json.writeValueAsString(request()));
        action.setAmount(new BigDecimal("25.00"));
        action.setExpiresAt(clock.instant().plusSeconds(600));
        when(actions.selectForUpdate("act-price")).thenReturn(action);
    }

    @ParameterizedTest @NullSource @ValueSource(strings = {"-0.01", "-12.50"})
    void prepareRejectsMalformedCatalogPriceBeforeQuotePersistence(String price) {
        catalog(price);
        BizException error = assertThrows(BizException.class, () -> service.prepare(request()));
        assertEquals(2001, error.getCode());
        verifyNoInteractions(actions, orders, orderService, redis);
        verify(products, never()).updateById(any(Product.class));
    }

    @ParameterizedTest @NullSource @ValueSource(strings = {"-0.01", "-12.50"})
    void pendingConfirmationRejectsMalformedCurrentPriceBeforeOrderOrIdempotencyWrites(String price) throws Exception {
        catalog(price);
        pendingAction();
        // A working downstream stub ensures negative-price failures expose missing validation,
        // not an unrelated null mock return after the unchecked arithmetic.
        OrderInfo downstream = new OrderInfo();
        downstream.setId(30L);
        downstream.setTotalAmount(new BigDecimal("25.00"));
        when(orderService.create(eq(7L), any(OrderDtos.CreateOrderRequest.class), eq("AI"), eq(20L)))
                .thenReturn(downstream);
        when(actions.markConfirmed("act-price", 30L, downstream.getTotalAmount())).thenReturn(1);
        BizException error = assertThrows(BizException.class, () -> service.confirm(7L, "act-price"));
        assertEquals(2001, error.getCode());
        verify(actions).selectForUpdate("act-price");
        verifyNoMoreInteractions(actions);
        verifyNoInteractions(orders, orderService, redis);
        verify(products, never()).updateById(any(Product.class));
    }

    @ParameterizedTest @ValueSource(strings = {"0.00", "12.50"})
    void preparePreservesZeroAndPositiveQuotesWithoutCreatingAnOrder(String price) {
        catalog(price);
        var result = service.prepare(request());
        BigDecimal expected = new BigDecimal(price).multiply(BigDecimal.valueOf(2));
        assertEquals(new BigDecimal(price), result.unitPrice());
        assertEquals(expected, result.amount());
        var action = ArgumentCaptor.forClass(AgentAction.class);
        verify(actions).insert(action.capture());
        assertEquals(expected, action.getValue().getAmount());
        assertEquals("PENDING", action.getValue().getStatus());
        verifyNoInteractions(orders, orderService, redis);
    }

    @SuppressWarnings("unchecked")
    @ParameterizedTest @ValueSource(strings = {"0.00", "12.50"})
    void confirmationPreservesValidOrderAndIdempotencyWorkflow(String price) throws Exception {
        catalog(price);
        pendingAction();
        ValueOperations<String, String> values = mock(ValueOperations.class);
        when(redis.opsForValue()).thenReturn(values);
        OrderInfo order = new OrderInfo();
        order.setId(30L);
        order.setUserId(7L);
        order.setTotalAmount(new BigDecimal(price).multiply(BigDecimal.valueOf(2)));
        when(orderService.create(eq(7L), any(OrderDtos.CreateOrderRequest.class), eq("AI"), eq(20L)))
                .thenReturn(order);
        when(actions.markConfirmed("act-price", 30L, order.getTotalAmount())).thenReturn(1);

        assertSame(order, service.confirm(7L, "act-price"));

        var request = ArgumentCaptor.forClass(OrderDtos.CreateOrderRequest.class);
        verify(orderService).create(eq(7L), request.capture(), eq("AI"), eq(20L));
        assertEquals(10L, request.getValue().getProductId());
        assertEquals(2, request.getValue().getQuantity());
        verify(actions).markConfirmed("act-price", 30L, order.getTotalAmount());
        verify(values).get("ai:order:20:10");
        verify(values).set("ai:order:20:10", "30", AgentOrderActionService.ACTION_TTL);
    }
}