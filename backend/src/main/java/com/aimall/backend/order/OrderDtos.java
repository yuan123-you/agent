package com.aimall.backend.order;

import com.aimall.backend.common.ExactNumberDeserializers;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

/**
 * 订单模块 DTO
 */
public class OrderDtos {

    @Data
    public static class CreateOrderRequest {
        @NotNull
        @JsonDeserialize(using = ExactNumberDeserializers.LongValue.class)
        private Long productId;
        @NotNull
        @Min(1)
        @Max(99)
        @JsonDeserialize(using = ExactNumberDeserializers.IntegerValue.class)
        private Integer quantity;
        @JsonDeserialize(using = ExactNumberDeserializers.LongValue.class)
        private Long addressId;
        private String receiverName;
        private String receiverPhone;
        private String receiverAddress;
    }
}
