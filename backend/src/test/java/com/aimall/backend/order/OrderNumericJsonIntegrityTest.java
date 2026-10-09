package com.aimall.backend.order;

import com.aimall.backend.common.GlobalExceptionHandler;
import com.aimall.backend.entity.OrderInfo;
import java.math.BigDecimal;
import java.util.stream.Stream;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.*;
import org.mockito.ArgumentCaptor;
import org.springframework.core.MethodParameter;
import org.springframework.http.MediaType;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.method.support.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class OrderNumericJsonIntegrityTest {
    private final OrderService service = mock(OrderService.class);
    private final OrderSseNotifier notifier = mock(OrderSseNotifier.class);
    private MockMvc mvc;
    @BeforeEach void setup() {
        mvc = MockMvcBuilders.standaloneSetup(new OrderController(service,notifier))
                .setControllerAdvice(new GlobalExceptionHandler())
                .setCustomArgumentResolvers(new HandlerMethodArgumentResolver() {
                    @Override public boolean supportsParameter(MethodParameter parameter) { return parameter.hasParameterAnnotation(AuthenticationPrincipal.class); }
                    @Override public Object resolveArgument(MethodParameter p, ModelAndViewContainer c, NativeWebRequest r, WebDataBinderFactory f) { return 7L; }
                }).build();
        var order = new OrderInfo(); order.setId(30L); order.setOrderNo("ORD-30"); order.setStatus("PENDING_PAYMENT"); order.setTotalAmount(new BigDecimal("0.00"));
        when(service.create(eq(7L),any(),eq("USER"),isNull())).thenReturn(order);
    }
    static Stream<Arguments> badTokens() {
        return Stream.of("productId","quantity","addressId").flatMap(field -> {
            String maximum = field.equals("quantity") ? "2147483648" : "9223372036854775808";
            String minimum = field.equals("quantity") ? "-2147483649" : "-9223372036854775809";
            return Stream.of("2.5","2.0000000000000000000000001",maximum,minimum,maximum+".0",minimum+".0").map(token -> Arguments.of(field,token));
        });
    }
    private String body(String field,String token) {
        String json = "{\"productId\":10,\"quantity\":2,\"addressId\":3,\"receiverAddress\":\"private-body-marker\"}";
        return json.replaceFirst("\""+field+"\":\\d+", "\""+field+"\":"+token);
    }
    @ParameterizedTest @MethodSource("badTokens")
    void invalidRawIntegralFieldsAre400BeforeOrderOrNotificationEffects(String field,String token) throws Exception {
        var result = mvc.perform(post("/api/v1/orders").contentType(MediaType.APPLICATION_JSON).content(body(field,token)))
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value(2001))
                .andExpect(jsonPath("$.message").value("请求体格式错误或字段类型不合法")).andReturn();
        assertFalse(result.getResponse().getContentAsString().contains("private-body-marker"));
        verifyNoInteractions(service,notifier);
    }
    @ParameterizedTest @ValueSource(strings = {"2","2.0","2e0","\"2\""})
    void integralQuantityAndZeroPriceResponseContractRemainValid(String token) throws Exception {
        mvc.perform(post("/api/v1/orders").contentType(MediaType.APPLICATION_JSON).content(body("quantity",token)))
                .andExpect(status().isOk()).andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.orderId").value(30)).andExpect(jsonPath("$.data.orderNo").value("ORD-30"))
                .andExpect(jsonPath("$.data.status").value("PENDING_PAYMENT")).andExpect(jsonPath("$.data.totalAmount").value(0));
        var captured = ArgumentCaptor.forClass(OrderDtos.CreateOrderRequest.class);
        verify(service).create(eq(7L),captured.capture(),eq("USER"),isNull()); assertEquals(2,captured.getValue().getQuantity());
        verifyNoInteractions(notifier);
    }
    @ParameterizedTest @ValueSource(strings = {"null","\"\"","\" \"","\"null\""})
    void nullableAddressCoercionsStayValid(String token) throws Exception {
        mvc.perform(post("/api/v1/orders").contentType(MediaType.APPLICATION_JSON).content(body("addressId",token))).andExpect(status().isOk());
        var captured = ArgumentCaptor.forClass(OrderDtos.CreateOrderRequest.class);
        verify(service).create(eq(7L),captured.capture(),eq("USER"),isNull()); assertNull(captured.getValue().getAddressId());
    }
    @Test void exactLongFieldsPreservePrecisionAndPrincipalAuthority() throws Exception {
        mvc.perform(post("/api/v1/orders").contentType(MediaType.APPLICATION_JSON)
                .content("{\"userId\":999,\"productId\":9007199254740993.0,\"quantity\":2.0,\"addressId\":9223372036854775807.0}"))
                .andExpect(status().isOk());
        var captured = ArgumentCaptor.forClass(OrderDtos.CreateOrderRequest.class);
        verify(service).create(eq(7L),captured.capture(),eq("USER"),isNull());
        assertEquals(9007199254740993L,captured.getValue().getProductId()); assertEquals(Long.MAX_VALUE,captured.getValue().getAddressId());
    }
    @ParameterizedTest @ValueSource(strings = {"0.0","100.0"})
    void originalBeanQuantityBoundsRemainActive(String token) throws Exception {
        mvc.perform(post("/api/v1/orders").contentType(MediaType.APPLICATION_JSON).content(body("quantity",token)))
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value(2001));
        verifyNoInteractions(service,notifier);
    }
}
