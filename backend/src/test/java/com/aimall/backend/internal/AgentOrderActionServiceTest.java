package com.aimall.backend.internal;

import com.aimall.backend.common.BizException;
import com.aimall.backend.address.AddressService;
import com.aimall.backend.entity.Address;
import com.aimall.backend.entity.AgentAction;
import com.aimall.backend.entity.Conversation;
import com.aimall.backend.entity.OrderInfo;
import com.aimall.backend.entity.Product;
import com.aimall.backend.mapper.AgentActionMapper;
import com.aimall.backend.mapper.ConversationMapper;
import com.aimall.backend.mapper.OrderInfoMapper;
import com.aimall.backend.mapper.ProductMapper;
import com.aimall.backend.order.OrderService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.data.redis.core.StringRedisTemplate;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class AgentOrderActionServiceTest {
    private final AddressService addressService = mock(AddressService.class);
    private final AgentActionMapper actionMapper = mock(AgentActionMapper.class);
    private final ProductMapper productMapper = mock(ProductMapper.class);
    private final ConversationMapper conversationMapper = mock(ConversationMapper.class);
    private final OrderInfoMapper orderInfoMapper = mock(OrderInfoMapper.class);
    private final OrderService orderService = mock(OrderService.class);
    private final StringRedisTemplate redisTemplate = mock(StringRedisTemplate.class);
    private final Clock clock = Clock.fixed(Instant.parse("2026-08-23T08:00:00Z"), ZoneOffset.UTC);
    private AgentOrderActionService service;

    @BeforeEach void setUp() {
        service = new AgentOrderActionService(addressService, actionMapper, productMapper, conversationMapper,
                orderInfoMapper, orderService, redisTemplate, new ObjectMapper(), clock);
    }

    @Test void prepareDoesNotCreateOrder() {
        when(productMapper.selectById(10L)).thenReturn(product("99.00", 8));
        when(conversationMapper.selectById(20L)).thenReturn(conversation(1L));
        doAnswer(invocation -> { AgentAction a = invocation.getArgument(0); a.setActionId("act-test"); return 1; })
                .when(actionMapper).insert(any(AgentAction.class));
        var result = service.prepare(request(1L, 20L, 10L, 2));
        assertEquals("act-test", result.actionId());
        assertEquals(new BigDecimal("198.00"), result.amount());
        verifyNoInteractions(orderService);
    }

    @Test void prepareUsesDefaultAddressWhenDeliveryFieldsAreOmitted() {
        Address address = new Address();
        address.setReceiverName("李四");
        address.setReceiverPhone("13900139000");
        address.setReceiverAddress("浙江省杭州市西湖区文三路90号");
        when(addressService.defaultFor(1L)).thenReturn(address);
        when(productMapper.selectById(10L)).thenReturn(product("99.00", 8));
        when(conversationMapper.selectById(20L)).thenReturn(conversation(1L));
        doAnswer(invocation -> { AgentAction a = invocation.getArgument(0); a.setActionId("act-default"); return 1; })
                .when(actionMapper).insert(any(AgentAction.class));

        var result = service.prepare(new AgentOrderActionService.PrepareRequest(1L, 20L, 10L, 1, "", "", ""));

        assertEquals("李四", result.receiverName());
        assertEquals("13900139000", result.receiverPhone());
        assertEquals("浙江省杭州市西湖区文三路90号", result.receiverAddress());
        verifyNoInteractions(orderService);
    }

    @Test void preparePropagatesMissingDefaultAddressWithoutCreatingAction() {
        when(addressService.defaultFor(1L)).thenThrow(new BizException(2014, "请先添加默认收货地址"));

        BizException error = assertThrows(BizException.class, () -> service.prepare(
                new AgentOrderActionService.PrepareRequest(1L, 20L, 10L, 1, "", "", "")));

        assertEquals(2014, error.getCode());
        verifyNoInteractions(actionMapper, orderService);
    }

    @Test void expiredActionIsRejectedWithoutCreatingOrder() {
        AgentAction action = pendingAction(1L, "2026-08-23T07:59:59Z");
        when(actionMapper.selectForUpdate("act-expired")).thenReturn(action);
        BizException error = assertThrows(BizException.class, () -> service.confirm(1L, "act-expired"));
        assertEquals(2011, error.getCode());
        verifyNoInteractions(orderService);
    }

    @Test void actionOwnedByAnotherUserIsRejectedWithoutCreatingOrder() {
        AgentAction action = pendingAction(2L, "2026-08-23T08:10:00Z");
        when(actionMapper.selectForUpdate("act-other-user")).thenReturn(action);
        BizException error = assertThrows(BizException.class, () -> service.confirm(1L, "act-other-user"));
        assertEquals(2003, error.getCode());
        verifyNoInteractions(orderService);
    }

    @Test void confirmRevalidatesCurrentPriceAndCreatesExactlyOneOrder() throws Exception {
        AgentAction action = pendingAction(1L, "2026-08-23T08:10:00Z");
        action.setPayload(new ObjectMapper().writeValueAsString(request(1L, 20L, 10L, 2)));
        when(actionMapper.selectForUpdate("act-ok")).thenReturn(action);
        when(productMapper.selectById(10L)).thenReturn(product("120.00", 5));
        when(conversationMapper.selectById(20L)).thenReturn(conversation(1L));
        OrderInfo order = new OrderInfo(); order.setId(88L); order.setUserId(1L); order.setTotalAmount(new BigDecimal("240.00"));
        when(orderService.create(eq(1L), any(), eq("AI"), eq(20L))).thenReturn(order);
        when(actionMapper.markConfirmed("act-ok", 88L, new BigDecimal("240.00"))).thenReturn(1);
        OrderInfo result = service.confirm(1L, "act-ok");
        assertSame(order, result);
        verify(actionMapper).markConfirmed("act-ok", 88L, new BigDecimal("240.00"));
        verify(orderService).create(eq(1L), any(), eq("AI"), eq(20L));
    }

    @Test void confirmUsesDeliveryDataApprovedByTheBuyer() throws Exception {
        AgentAction action = pendingAction(1L, "2026-08-23T08:10:00Z");
        action.setPayload(new ObjectMapper().writeValueAsString(request(1L, 20L, 10L, 2)));
        when(actionMapper.selectForUpdate("act-edited")).thenReturn(action);
        when(productMapper.selectById(10L)).thenReturn(product("120.00", 5));
        when(conversationMapper.selectById(20L)).thenReturn(conversation(1L));
        OrderInfo order = new OrderInfo(); order.setId(89L); order.setUserId(1L); order.setTotalAmount(new BigDecimal("240.00"));
        when(orderService.create(eq(1L), any(), eq("AI"), eq(20L))).thenReturn(order);
        when(actionMapper.markConfirmed("act-edited", 89L, new BigDecimal("240.00"))).thenReturn(1);

        service.confirm(1L, "act-edited", new AgentOrderActionService.ApprovalRequest(
                "李四", "13900139000", "浙江省杭州市西湖区文三路90号"));

        var requestCaptor = org.mockito.ArgumentCaptor.forClass(com.aimall.backend.order.OrderDtos.CreateOrderRequest.class);
        verify(orderService).create(eq(1L), requestCaptor.capture(), eq("AI"), eq(20L));
        assertEquals("李四", requestCaptor.getValue().getReceiverName());
        assertEquals("13900139000", requestCaptor.getValue().getReceiverPhone());
        assertEquals("浙江省杭州市西湖区文三路90号", requestCaptor.getValue().getReceiverAddress());
    }

    @Test void confirmRejectsInvalidApprovedPhoneWithoutCreatingOrder() throws Exception {
        AgentAction action = pendingAction(1L, "2026-08-23T08:10:00Z");
        action.setPayload(new ObjectMapper().writeValueAsString(request(1L, 20L, 10L, 2)));
        when(actionMapper.selectForUpdate("act-invalid-phone")).thenReturn(action);

        BizException error = assertThrows(BizException.class, () -> service.confirm(1L, "act-invalid-phone",
                new AgentOrderActionService.ApprovalRequest("李四", "123", "杭州文三路90号")));

        assertEquals(2001, error.getCode());
        verifyNoInteractions(orderService);
    }

    @Test void statusReturnsThePersistedHumanDecision() {
        AgentAction action = pendingAction(1L, "2026-08-23T08:10:00Z");
        action.setStatus("CANCELLED");
        when(actionMapper.selectById("act-status")).thenReturn(action);

        var result = service.status(1L, "act-status");

        assertEquals("CANCELLED", result.status());
        assertNull(result.orderId());
    }

    @Test void cancelPersistsTheHumanDecisionWithoutCreatingAnOrder() {
        AgentAction action = pendingAction(1L, "2026-08-23T08:10:00Z");
        when(actionMapper.selectForUpdate("act-cancel")).thenReturn(action);
        when(actionMapper.markCancelled("act-cancel")).thenReturn(1);

        service.cancel(1L, "act-cancel");

        verify(actionMapper).markCancelled("act-cancel");
        verifyNoInteractions(orderService);
    }
    private AgentOrderActionService.PrepareRequest request(Long userId, Long conversationId, Long productId, int quantity) {
        return new AgentOrderActionService.PrepareRequest(userId, conversationId, productId, quantity,
                "张三", "13800138000", "上海市测试路1号");
    }
    private Product product(String price, int stock) {
        Product p = new Product(); p.setId(10L); p.setName("测试商品"); p.setStatus("ON_SALE");
        p.setPrice(new BigDecimal(price)); p.setStock(stock); return p;
    }
    private Conversation conversation(Long userId) { Conversation c = new Conversation(); c.setId(20L); c.setUserId(userId); return c; }
    private AgentAction pendingAction(Long userId, String expiresAt) {
        AgentAction a = new AgentAction(); a.setActionId("act"); a.setUserId(userId); a.setType("ORDER_CREATE");
        a.setStatus("PENDING"); a.setConversationId(20L); a.setExpiresAt(Instant.parse(expiresAt)); return a;
    }
}
