package com.aimall.backend.common;

import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.core.JsonToken;
import com.fasterxml.jackson.databind.DeserializationContext;
import com.fasterxml.jackson.databind.JsonDeserializer;
import com.fasterxml.jackson.databind.JsonMappingException;
import java.io.IOException;
import java.math.BigDecimal;

/** Field-local exact parsing; does not alter coercion rules for other DTOs. */
public final class ExactNumberDeserializers {
    private ExactNumberDeserializers() { }

    private static BigDecimal readNumber(JsonParser parser) throws IOException {
        if (parser.currentToken() == JsonToken.VALUE_NULL) return null;
        if (parser.currentToken() == JsonToken.VALUE_NUMBER_INT || parser.currentToken() == JsonToken.VALUE_NUMBER_FLOAT) {
            // Read the original decimal token, never a rounded double or truncated integer.
            return parser.getDecimalValue();
        }
        if (parser.currentToken() == JsonToken.VALUE_STRING) {
            String text = parser.getText().trim();
            if (text.isEmpty() || "null".equals(text)) return null; // Preserve legacy nullable optional fields.
            if (text.matches("[+-]?[0-9]+")) return new BigDecimal(text);
        }
        throw JsonMappingException.from(parser, "字段必须为范围内的整数");
    }

    public static class IntegerValue extends JsonDeserializer<Integer> {
        @Override public Integer deserialize(JsonParser parser, DeserializationContext context) throws IOException {
            try {
                BigDecimal value = readNumber(parser);
                return value == null ? null : value.intValueExact();
            } catch (ArithmeticException | NumberFormatException invalid) {
                throw JsonMappingException.from(parser, "字段必须为范围内的整数");
            }
        }
    }

    public static class LongValue extends JsonDeserializer<Long> {
        @Override public Long deserialize(JsonParser parser, DeserializationContext context) throws IOException {
            try {
                BigDecimal value = readNumber(parser);
                return value == null ? null : value.longValueExact();
            } catch (ArithmeticException | NumberFormatException invalid) {
                throw JsonMappingException.from(parser, "字段必须为范围内的整数");
            }
        }
    }
}
