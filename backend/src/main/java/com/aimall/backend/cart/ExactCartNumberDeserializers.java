package com.aimall.backend.cart;

import com.aimall.backend.common.ExactNumberDeserializers;

/** Compatibility names for existing cart DTO annotations and direct callers. */
public final class ExactCartNumberDeserializers {
    private ExactCartNumberDeserializers() { }

    public static final class IntegerValue extends ExactNumberDeserializers.IntegerValue { }
    public static final class LongValue extends ExactNumberDeserializers.LongValue { }
}
