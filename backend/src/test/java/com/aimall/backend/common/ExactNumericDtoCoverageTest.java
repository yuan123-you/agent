package com.aimall.backend.common;

import com.aimall.backend.internal.InternalToolController;
import com.aimall.backend.order.OrderDtos;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;
import java.lang.reflect.Field;
import java.math.BigDecimal;
import java.util.List;
import java.util.Arrays;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.junit.jupiter.params.provider.Arguments;
import static org.junit.jupiter.api.Assertions.*;

class ExactNumericDtoCoverageTest {
    private static final List<Class<?>> DTOS = List.of(OrderDtos.CreateOrderRequest.class,
            InternalToolController.ProductSearchBody.class, InternalToolController.ProductDetailBody.class,
            InternalToolController.OrderQueryBody.class, InternalToolController.OrderCreateBody.class,
            InternalToolController.EscalateBody.class, InternalToolController.OrderCancelBody.class,
            InternalToolController.AfterSalePrepareBody.class, InternalToolController.OrderConfirmBody.class);
    static Stream<Arguments> fields() {
        return DTOS.stream().flatMap(type -> Arrays.stream(type.getDeclaredFields())
                .filter(field -> field.getType() == Long.class || field.getType() == Integer.class)
                .map(field -> Arguments.of(type,field)));
    }
    @ParameterizedTest @MethodSource("fields")
    void eachIntegralFieldDeclaresItsExactDeserializerAtTheSource(Class<?> type, Field field) {
        var annotation = field.getAnnotation(JsonDeserialize.class);
        assertNotNull(annotation, type.getSimpleName() + "." + field.getName());
        assertTrue(annotation.using().getName().startsWith("com.aimall.backend.common."));
    }
    @ParameterizedTest @MethodSource("fields")
    void exactSignedRangesTokensNullsAndDirectBeanSettersRemainCompatible(Class<?> type, Field field) throws Exception {
        var mapper = new ObjectMapper();
        String maximum = field.getType() == Long.class ? "9223372036854775807" : "2147483647";
        String minimum = field.getType() == Long.class ? "-9223372036854775808" : "-2147483648";
        String getter = "get" + Character.toUpperCase(field.getName().charAt(0)) + field.getName().substring(1);
        String setter = "set" + getter.substring(3);
        for (String token : List.of(maximum, maximum+".0", minimum, minimum+".0", "2", "2.0", "2e0", "\"2\"")) {
            Object dto = mapper.readValue("{\""+field.getName()+"\":"+token+"}", type);
            Number actual = (Number) type.getMethod(getter).invoke(dto);
            String expected = token.startsWith(maximum) ? maximum : token.startsWith(minimum) ? minimum : "2";
            assertEquals(new BigDecimal(expected), new BigDecimal(actual.toString()));
            Number replacement = field.getType() == Long.class ? (Number) Long.valueOf(3) : Integer.valueOf(3);
            type.getMethod(setter, field.getType()).invoke(dto,replacement);
            assertEquals(3, ((Number)type.getMethod(getter).invoke(dto)).intValue());
        }
        Object nullable = mapper.readValue("{\""+field.getName()+"\":null}",type);
        assertNull(type.getMethod(getter).invoke(nullable));
    }
    @Test void sourceInventoryAndDecimalPriceFieldsStayExplicit() throws Exception {
        assertEquals(23,fields().count());
        for (String name : List.of("minPrice","maxPrice")) {
            Field field = InternalToolController.ProductSearchBody.class.getDeclaredField(name);
            assertEquals(BigDecimal.class,field.getType()); assertNull(field.getAnnotation(JsonDeserialize.class));
        }
    }
    public static class UnannotatedProbe { public Integer quantity; }
    @Test void defaultJacksonRulesRemainUnchangedOutsideAnnotatedFields() throws Exception {
        assertEquals(2,new ObjectMapper().readValue("{\"quantity\":2.5}",UnannotatedProbe.class).quantity);
    }
}
