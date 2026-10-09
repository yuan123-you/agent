package com.aimall.backend.cart;

import com.aimall.backend.common.BizException;
import com.aimall.backend.common.GlobalExceptionHandler;
import com.aimall.backend.entity.CartItem;
import com.aimall.backend.entity.OrderInfo;
import com.aimall.backend.mapper.CartItemMapper;
import com.aimall.backend.mapper.ProductMapper;
import com.aimall.backend.order.OrderService;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.TableInfoHelper;
import org.apache.ibatis.builder.MapperBuilderAssistant;
import org.junit.jupiter.api.BeforeEach;
import org.mockito.ArgumentCaptor;
import java.math.BigDecimal;
import java.util.Arrays;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class CartCheckoutInputIntegrityTest {
    private final CartItemMapper cart = mock(CartItemMapper.class);
    private final ProductMapper products = mock(ProductMapper.class);
    private final OrderService orders = mock(OrderService.class);
    private final CartController controller = new CartController(cart, products, orders);

    @BeforeEach void initializeCartLambdaMetadata() {
        // These are controller-only mocks; initialize metadata so captured SQL guards can be inspected.
        TableInfoHelper.initTableInfo(new MapperBuilderAssistant(new MybatisConfiguration(), "cart-fixture"), CartItem.class);
    }

    private CartItem snapshot(int quantity) {
        var row = new CartItem();
        row.setId(81L);
        row.setUserId(7L);
        row.setProductId(10L);
        row.setQuantity(quantity);
        row.setChecked(1);
        return row;
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private void assertLockedSnapshotCleanup(CartItem snapshot, List<OrderService.CheckoutItem> expected, boolean explicit) {
        ArgumentCaptor<LambdaQueryWrapper<CartItem>> selected = ArgumentCaptor.forClass((Class) LambdaQueryWrapper.class);
        ArgumentCaptor<LambdaQueryWrapper<CartItem>> deleted = ArgumentCaptor.forClass((Class) LambdaQueryWrapper.class);
        var sequence = inOrder(cart, orders);
        sequence.verify(cart).selectList(selected.capture());
        sequence.verify(orders).checkout(7L, expected, null, "Receiver", "13800000000", "Test address");
        sequence.verify(cart).delete(deleted.capture());
        sequence.verifyNoMoreInteractions();
        String selectionSql = selected.getValue().getSqlSegment();
        assertTrue(selectionSql.contains("user_id ="));
        assertTrue(selectionSql.contains("ORDER BY product_id ASC"));
        assertTrue(selectionSql.endsWith("FOR UPDATE"));
        var selectionParameters = selected.getValue().getParamNameValuePairs();
        assertEquals(2, selectionParameters.size());
        assertTrue(selectionParameters.containsValue(7L));
        if (explicit) {
            assertTrue(selectionSql.contains("product_id IN"));
            assertTrue(selectionParameters.containsValue(snapshot.getProductId()));
        } else {
            assertTrue(selectionSql.contains("checked ="));
            assertTrue(selectionParameters.containsValue(1));
        }
        String cleanupSql = deleted.getValue().getSqlSegment();
        assertTrue(cleanupSql.matches("(?s).*\\bid\\s*=.*"));
        assertTrue(cleanupSql.contains("user_id ="));
        assertTrue(cleanupSql.contains("product_id ="));
        assertTrue(cleanupSql.contains("quantity ="));
        var parameters = deleted.getValue().getParamNameValuePairs();
        assertEquals(4, parameters.size());
        assertTrue(parameters.containsValue(snapshot.getId()));
        assertTrue(parameters.containsValue(snapshot.getUserId()));
        assertTrue(parameters.containsValue(snapshot.getProductId()));
        assertTrue(parameters.containsValue(snapshot.getQuantity()));
        verifyNoInteractions(products);
    }

    private CartController.CheckoutBody body() {
        var body = new CartController.CheckoutBody();
        body.setReceiverName("Receiver");
        body.setReceiverPhone("13800000000");
        body.setReceiverAddress("Test address");
        return body;
    }

    private CartController.CheckoutItemBody item() {
        var item = new CartController.CheckoutItemBody();
        item.setProductId(10L);
        item.setQuantity(2);
        return item;
    }

    @ParameterizedTest @ValueSource(booleans = {true, false})
    void nullFirstOrLaterEntryIsBusinessErrorBeforeAnyStockOrCartWrites(boolean first) {
        var body = body();
        body.setItems(first ? Arrays.asList(null, item()) : Arrays.asList(item(), null));
        BizException error = assertThrows(BizException.class, () -> controller.checkout(7L, body));
        assertEquals(2001, error.getCode());
        verifyNoInteractions(cart, products, orders);
    }

    @ParameterizedTest @ValueSource(booleans = {true, false})
    void nullJsonEntryReturnsHttp400AndBusinessCodeRatherThanServerError(boolean first) throws Exception {
        var mvc = MockMvcBuilders.standaloneSetup(controller)
                .setControllerAdvice(new GlobalExceptionHandler()).build();
        String valid = "{\"productId\":10,\"quantity\":2}";
        String items = first ? "null," + valid : valid + ",null";
        mvc.perform(post("/api/v1/cart/checkout").contentType(MediaType.APPLICATION_JSON)
                .content("{\"items\":[" + items + "]}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(2001));
        verifyNoInteractions(cart, products, orders);
    }

    private OrderInfo order() {
        var order = new OrderInfo();
        order.setId(30L);
        order.setOrderNo("ORD-30");
        order.setStatus("PENDING_PAYMENT");
        order.setTotalAmount(new BigDecimal("25.00"));
        return order;
    }

    @ParameterizedTest @ValueSource(strings = {"25.00", "0.00"})
    void validExplicitEntriesRetainCheckoutAndCartCleanup(String total) {
        var body = body();
        body.setItems(List.of(item()));
        var expected = List.of(new OrderService.CheckoutItem(10L, 2));
        // Explicit quantity is 2; existing policy clears the whole locked cart row of 5.
        var snapshot = snapshot(5);
        when(cart.selectList(any())).thenReturn(List.of(snapshot));
        when(cart.delete(any())).thenReturn(1);
        var order = order();
        order.setTotalAmount(new BigDecimal(total));
        when(orders.checkout(7L, expected, null, "Receiver", "13800000000", "Test address")).thenReturn(order);
        var result = controller.checkout(7L, body);
        assertEquals(0, result.getCode());
        assertEquals(30L, result.getData().get("orderId"));
        assertEquals("ORD-30", result.getData().get("orderNo"));
        assertEquals("PENDING_PAYMENT", result.getData().get("status"));
        assertEquals(new BigDecimal(total), result.getData().get("totalAmount"));
        assertLockedSnapshotCleanup(snapshot, expected, true);
    }

    @Test void explicitBuyNowWithoutCartSnapshotDoesNotBlindlyDelete() {
        var body = body();
        body.setItems(List.of(item()));
        var expected = List.of(new OrderService.CheckoutItem(10L, 2));
        when(cart.selectList(any())).thenReturn(List.of());
        when(orders.checkout(7L, expected, null, "Receiver", "13800000000", "Test address")).thenReturn(order());
        var result = controller.checkout(7L, body);
        assertEquals(0, result.getCode());
        assertEquals(30L, result.getData().get("orderId"));
        assertEquals("ORD-30", result.getData().get("orderNo"));
        assertEquals("PENDING_PAYMENT", result.getData().get("status"));
        assertEquals(new BigDecimal("25.00"), result.getData().get("totalAmount"));
        var sequence = inOrder(cart, orders);
        sequence.verify(cart).selectList(any());
        sequence.verify(orders).checkout(7L, expected, null, "Receiver", "13800000000", "Test address");
        sequence.verifyNoMoreInteractions();
        verify(cart, never()).delete(any());
        verifyNoInteractions(products);
    }

    @ParameterizedTest @ValueSource(booleans = {true, false})
    void zeroRowSnapshotCleanupCannotReturnSuccess(boolean explicit) {
        var body = body();
        if (explicit) body.setItems(List.of(item()));
        var snapshot = snapshot(2);
        var expected = List.of(new OrderService.CheckoutItem(10L, 2));
        when(cart.selectList(any())).thenReturn(List.of(snapshot));
        // The original fallback success fixture implicitly returned this same zero via Mockito.
        when(cart.delete(any())).thenReturn(0);
        when(orders.checkout(7L, expected, null, "Receiver", "13800000000", "Test address")).thenReturn(order());
        var error = assertThrows(BizException.class, () -> controller.checkout(7L, body));
        assertEquals(2004, error.getCode());
        assertLockedSnapshotCleanup(snapshot, expected, explicit);
    }

    @ParameterizedTest @ValueSource(booleans = {true, false})
    void missingOrEmptyExplicitItemsStillUseCheckedCartFallback(boolean missing) {
        var body = body();
        body.setItems(missing ? null : List.of());
        CartItem checked = snapshot(2);
        when(cart.selectList(any())).thenReturn(List.of(checked));
        when(cart.delete(any())).thenReturn(1);
        var expected = List.of(new OrderService.CheckoutItem(10L, 2));
        when(orders.checkout(7L, expected, null, "Receiver", "13800000000", "Test address"))
                .thenReturn(order());
        assertEquals(30L, controller.checkout(7L, body).getData().get("orderId"));
        assertLockedSnapshotCleanup(checked, expected, false);
    }
}