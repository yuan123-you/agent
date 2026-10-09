package com.aimall.backend.cart;

import com.aimall.backend.common.GlobalExceptionHandler;
import com.aimall.backend.entity.CartItem;
import com.aimall.backend.mapper.CartItemMapper;
import com.aimall.backend.mapper.ProductMapper;
import com.aimall.backend.order.OrderService;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.conditions.Wrapper;
import com.baomidou.mybatisplus.core.metadata.TableInfoHelper;
import org.apache.ibatis.builder.MapperBuilderAssistant;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.mockito.ArgumentCaptor;
import org.springframework.core.MethodParameter;
import org.springframework.http.MediaType;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class CartUpdateRequestValidationTest {
    private final CartItemMapper cart = mock(CartItemMapper.class);
    private final ProductMapper products = mock(ProductMapper.class);
    private final OrderService orders = mock(OrderService.class);
    private final CartController controller = new CartController(cart, products, orders);
    private MockMvc mvc;

    @RestController static class QueryProbe {
        @GetMapping("/cart-binding-probe") String query(@RequestParam Long id) { return "ok"; }
    }

    @BeforeEach void setup() {
        TableInfoHelper.initTableInfo(new MapperBuilderAssistant(new MybatisConfiguration(), "cart-update-http"), CartItem.class);
        mvc = MockMvcBuilders.standaloneSetup(controller, new QueryProbe())
                .setControllerAdvice(new GlobalExceptionHandler())
                .setCustomArgumentResolvers(new HandlerMethodArgumentResolver() {
                    @Override public boolean supportsParameter(MethodParameter parameter) {
                        return parameter.hasParameterAnnotation(AuthenticationPrincipal.class);
                    }
                    @Override public Object resolveArgument(MethodParameter parameter, ModelAndViewContainer container,
                            NativeWebRequest request, WebDataBinderFactory factory) { return 7L; }
                }).build();
        var row = new CartItem(); row.setId(81L); row.setUserId(7L); row.setProductId(10L); row.setQuantity(3); row.setChecked(1);
        when(cart.selectById(81L)).thenReturn(row);
    }

    @ParameterizedTest @ValueSource(strings = {"2.0000000000000000000000001", "2.5", "2147483648", "2147483648.0"})
    void invalidRawQuantityMustRejectBeforeLookupOrQuantityWrite(String quantity) throws Exception {
        // Make the old rounded quantity=2 write succeed, proving false HTTP success rather than only a read.
        when(cart.setQuantity(81L,7L,2,null)).thenReturn(1);
        mvc.perform(put("/api/v1/cart/items/81").contentType(MediaType.APPLICATION_JSON)
                .content("{\"quantity\":" + quantity + "}"))
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value(2001));
        verifyNoInteractions(cart, products, orders);
    }

    @ParameterizedTest @ValueSource(strings = {"2", "2.0", "\"2\""})
    void integralQuantityPreservesUpdateContract(String quantity) throws Exception {
        when(cart.setQuantity(81L,7L,2,null)).thenReturn(1);
        mvc.perform(put("/api/v1/cart/items/81").contentType(MediaType.APPLICATION_JSON)
                .content("{\"quantity\":" + quantity + "}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.code").value(0));
        verify(cart).selectById(81L); verify(cart).setQuantity(81L,7L,2,null);
        verifyNoMoreInteractions(cart); verifyNoInteractions(products,orders);
    }

    @Test void suppliedNullQuantityIsInvalidRatherThanAnOmittedQuantity() throws Exception {
        mvc.perform(put("/api/v1/cart/items/81").contentType(MediaType.APPLICATION_JSON).content("{\"quantity\":null}"))
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value(2001));
        verify(cart).selectById(81L); verifyNoMoreInteractions(cart); verifyNoInteractions(products,orders);
    }

    @Test void missingBothFieldsRemainsAnOwnedNoOp() throws Exception {
        mvc.perform(put("/api/v1/cart/items/81").contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.code").value(0));
        verify(cart).selectById(81L); verifyNoMoreInteractions(cart); verifyNoInteractions(products,orders);
    }

    @ParameterizedTest @ValueSource(strings = {"true", "false", "null", "\"true\"", "1", "{}"})
    @SuppressWarnings({"unchecked", "rawtypes"})
    void checkboxOnlyPreservesExistingBooleanTrueEqualsPolicy(String token) throws Exception {
        when(cart.update(any(CartItem.class), any())).thenReturn(1);
        mvc.perform(put("/api/v1/cart/items/81").contentType(MediaType.APPLICATION_JSON).content("{\"checked\":" + token + "}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.code").value(0));
        ArgumentCaptor<CartItem> update = ArgumentCaptor.forClass(CartItem.class);
        ArgumentCaptor<Wrapper<CartItem>> guard = ArgumentCaptor.forClass((Class)Wrapper.class);
        verify(cart).selectById(81L); verify(cart).update(update.capture(), guard.capture());
        assertNull(update.getValue().getQuantity());
        assertEquals("true".equals(token) ? 1 : 0, update.getValue().getChecked());
        assertTrue(guard.getValue().getSqlSegment().contains("user_id ="));
        assertTrue(guard.getValue().getSqlSegment().matches("(?s).*\\bid\\s*=.*"));
        verifyNoMoreInteractions(cart); verifyNoInteractions(products,orders);
    }

    @Test void zeroAffectedQuantityWriteStillRejectsRatherThanReportingSuccess() throws Exception {
        when(cart.setQuantity(81L,7L,2,null)).thenReturn(0);
        mvc.perform(put("/api/v1/cart/items/81").contentType(MediaType.APPLICATION_JSON).content("{\"quantity\":2.0}"))
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value(2006));
        verify(cart).setQuantity(81L,7L,2,null);
    }

    @Test void zeroAffectedCheckboxWriteStillRejectsRatherThanReportingSuccess() throws Exception {
        when(cart.update(any(CartItem.class), any())).thenReturn(0);
        mvc.perform(put("/api/v1/cart/items/81").contentType(MediaType.APPLICATION_JSON).content("{\"checked\":true}"))
                .andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value(2002));
    }

    @ParameterizedTest @ValueSource(strings = {"not-a-long", "81.5", "9223372036854775808"})
    void invalidLongPathIs400BeforeCartEffects(String path) throws Exception {
        mvc.perform(put("/api/v1/cart/items/" + path).contentType(MediaType.APPLICATION_JSON).content("{\"quantity\":2}"))
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value(2001));
        verifyNoInteractions(cart, products, orders);
    }

    @Test void unrelatedQueryBindingMismatchIsNotReclassifiedByPathOnlyHandler() throws Exception {
        mvc.perform(get("/cart-binding-probe").param("id","not-a-long"))
                .andExpect(status().isInternalServerError()).andExpect(jsonPath("$.code").value(9999));
        verifyNoInteractions(cart, products, orders);
    }

    @Test void unrelatedCartRuntimeFailureRemains500() throws Exception {
        when(cart.setQuantity(81L,7L,2,null)).thenThrow(new IllegalStateException("injected cart failure"));
        mvc.perform(put("/api/v1/cart/items/81").contentType(MediaType.APPLICATION_JSON).content("{\"quantity\":2}"))
                .andExpect(status().isInternalServerError()).andExpect(jsonPath("$.code").value(9999));
    }
}
