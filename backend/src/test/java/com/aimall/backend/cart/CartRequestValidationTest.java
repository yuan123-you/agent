package com.aimall.backend.cart;

import com.aimall.backend.common.GlobalExceptionHandler;
import com.aimall.backend.entity.OrderInfo;
import com.aimall.backend.entity.Product;
import com.aimall.backend.mapper.CartItemMapper;
import com.aimall.backend.mapper.ProductMapper;
import com.aimall.backend.order.OrderService;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class CartRequestValidationTest {
    private final CartItemMapper cart = mock(CartItemMapper.class);
    private final ProductMapper products = mock(ProductMapper.class);
    private final OrderService orders = mock(OrderService.class);
    private final CartController controller = new CartController(cart, products, orders);
    private MockMvc mvc() {
        return MockMvcBuilders.standaloneSetup(controller).setControllerAdvice(new GlobalExceptionHandler()).build();
    }
    private void rejectedBeforeEffects(String endpoint, String json) throws Exception {
        mvc().perform(post(endpoint).contentType(MediaType.APPLICATION_JSON).content(json))
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value(2001));
        verifyNoInteractions(cart, products, orders);
    }

    @ParameterizedTest @ValueSource(strings = {
        "{}", "{\"productId\":1}", "{\"productId\":1,\"quantity\":null}",
        "{\"productId\":1,\"quantity\":0}", "{\"productId\":1,\"quantity\":-1}",
        "{\"productId\":1,\"quantity\":100}"})
    void invalidAddIsHttp400BeforeMapperOrOrderCalls(String json) throws Exception {
        rejectedBeforeEffects("/api/v1/cart/items", json);
    }

    @ParameterizedTest @ValueSource(strings = {
        "{\"productId\":10,\"quantity\":2.5}",
        "{\"productId\":10,\"quantity\":2.0000000000000000000000001}",
        "{\"productId\":10.5,\"quantity\":2}",
        "{\"productId\":10.0000000000000000000000001,\"quantity\":2}",
        "{\"productId\":10,\"quantity\":2147483648}",
        "{\"productId\":10,\"quantity\":2147483648.0}",
        "{\"productId\":10,\"quantity\":-2147483649}",
        "{\"productId\":9223372036854775808,\"quantity\":2}",
        "{\"productId\":9223372036854775808.0,\"quantity\":2}",
        "{\"productId\":-9223372036854775809,\"quantity\":2}",
        "{\"productId\":10,\"quantity\":\"2.5\"}",
        "{\"productId\":10,\"quantity\":true}",
        "{\"productId\":10,\"quantity\":[]}",
        "{\"productId\":10,\"quantity\":{}}"})
    void fractionalOrOverflowAddJsonIsRejectedBeforeCoercionCanReachMapper(String json) throws Exception {
        rejectedBeforeEffects("/api/v1/cart/items", json);
    }

    @ParameterizedTest @ValueSource(strings = {
        "{\"items\":[{\"productId\":10,\"quantity\":2.5}]}",
        "{\"items\":[{\"productId\":10,\"quantity\":2.0000000000000000000000001}]}",
        "{\"items\":[{\"productId\":10.5,\"quantity\":2}]}",
        "{\"items\":[{\"productId\":10.0000000000000000000000001,\"quantity\":2}]}",
        "{\"items\":[{\"productId\":10,\"quantity\":2147483648}]}",
        "{\"items\":[{\"productId\":10,\"quantity\":2147483648.0}]}",
        "{\"items\":[{\"productId\":9223372036854775808,\"quantity\":2}]}",
        "{\"items\":[{\"productId\":9223372036854775808.0,\"quantity\":2}]}",
        "{\"items\":[{\"productId\":10,\"quantity\":2}],\"addressId\":3.5}",
        "{\"items\":[{\"productId\":10,\"quantity\":2}],\"addressId\":3.000000000000000000000001}",
        "{\"items\":[{\"productId\":10,\"quantity\":2}],\"addressId\":9223372036854775808}",
        "{\"items\":[{\"productId\":10,\"quantity\":2}],\"addressId\":9223372036854775808.0}"})
    void fractionalOrOverflowCheckoutJsonIsRejectedBeforeAnyCartOrOrderEffects(String json) throws Exception {
        rejectedBeforeEffects("/api/v1/cart/checkout", json);
    }

    @ParameterizedTest @ValueSource(strings = {"/api/v1/cart/items", "/api/v1/cart/checkout"})
    void malformedJsonIs400AndDoesNotExposeRawBody(String endpoint) throws Exception {
        var result = mvc().perform(post(endpoint).contentType(MediaType.APPLICATION_JSON)
                .content("{\"receiverAddress\":\"private-body-marker\",\"quantity\":}"))
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value(2001))
                .andExpect(jsonPath("$.message").value("请求体格式错误或字段类型不合法")).andReturn();
        assertFalse(result.getResponse().getContentAsString().contains("private-body-marker"));
        assertFalse(result.getResponse().getContentAsString().contains("JsonParseException"));
        verifyNoInteractions(cart, products, orders);
    }

    @ParameterizedTest @ValueSource(strings = {"2", "2.0", "2e0", "\"2\""})
    void legacyIntegralAddJsonRemainsSuccessful(String quantityToken) throws Exception {
        var product = new Product(); product.setId(10L); product.setStock(1000); product.setStatus("ON_SALE");
        when(products.selectById(10L)).thenReturn(product);
        when(cart.increment(null, 10L, 2)).thenReturn(1);
        mvc().perform(post("/api/v1/cart/items").contentType(MediaType.APPLICATION_JSON)
                .content("{\"productId\":10.0,\"quantity\":" + quantityToken + "}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.code").value(0));
        verify(products).selectById(10L); verify(cart).increment(null, 10L, 2); verifyNoInteractions(orders);
    }

    @Test void integralCheckoutJsonKeepsLongPrecisionZeroPriceAndNoGlobal99Cap() throws Exception {
        long productId = 9007199254740993L;
        long addressId = Long.MAX_VALUE;
        var expected = List.of(new OrderService.CheckoutItem(productId, 150));
        var order = new OrderInfo(); order.setId(30L); order.setOrderNo("ORD-30"); order.setStatus("PENDING_PAYMENT"); order.setTotalAmount(new BigDecimal("0.00"));
        when(cart.selectList(any())).thenReturn(List.of());
        when(orders.checkout(null, expected, addressId, null, null, null)).thenReturn(order);
        mvc().perform(post("/api/v1/cart/checkout").contentType(MediaType.APPLICATION_JSON)
                .content("{\"items\":[{\"productId\":9007199254740993.0,\"quantity\":1.5e2}],\"addressId\":9223372036854775807.0}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.orderId").value(30)).andExpect(jsonPath("$.data.orderNo").value("ORD-30"))
                .andExpect(jsonPath("$.data.status").value("PENDING_PAYMENT")).andExpect(jsonPath("$.data.totalAmount").value(0));
        verify(orders).checkout(null, expected, addressId, null, null, null);
        verify(cart, never()).delete(any()); verifyNoInteractions(products);
    }

    @Test void dtoAccessorInterfacesAndNullableAddressRemainCompatible() throws Exception {
        var mapper = new ObjectMapper();
        var add = mapper.readValue("{\"productId\":\"10\",\"quantity\":\"2\"}", CartController.AddBody.class);
        add.setProductId(11L); add.setQuantity(3);
        assertEquals(11L, add.getProductId()); assertEquals(3, add.getQuantity());
        var checkout = mapper.readValue("{\"addressId\":null,\"items\":[{\"productId\":10,\"quantity\":2}]}", CartController.CheckoutBody.class);
        assertNull(checkout.getAddressId()); checkout.setAddressId(12L); assertEquals(12L, checkout.getAddressId());
        var item = checkout.getItems().get(0); item.setProductId(13L); item.setQuantity(4);
        assertEquals(13L, item.getProductId()); assertEquals(4, item.getQuantity());
    }

    @ParameterizedTest @ValueSource(strings = {"null", "\"\"", "\" \"", "\"null\""})
    void legacyNullableAddressCoercionsRemainCompatible(String addressToken) throws Exception {
        var checkout = new ObjectMapper().readValue("{\"addressId\":" + addressToken + "}", CartController.CheckoutBody.class);
        assertNull(checkout.getAddressId());
    }

    @Test void unrelatedRuntimeFailuresRemain500RatherThanBeingReclassifiedAsUnreadableJson() throws Exception {
        when(cart.selectList(any())).thenReturn(List.of());
        when(orders.checkout(any(), anyList(), any(), any(), any(), any()))
                .thenThrow(new IllegalStateException("internal-private-marker"));
        var result = mvc().perform(post("/api/v1/cart/checkout").contentType(MediaType.APPLICATION_JSON)
                .content("{\"items\":[{\"productId\":10,\"quantity\":2}]}"))
                .andExpect(status().isInternalServerError()).andExpect(jsonPath("$.code").value(9999)).andReturn();
        assertFalse(result.getResponse().getContentAsString().contains("internal-private-marker"));
    }
}
