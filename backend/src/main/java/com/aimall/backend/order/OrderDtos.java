package com.aimall.backend.order;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

/**
 * 订单模块 DTO
 */
public class OrderDtos {

    @Data
    public static class CreateOrderRequest {
        @NotNull
        private Long productId;
        @NotNull
        @Min(1)
        @Max(99)
        private Integer quantity;
        @NotBlank
        private String receiverName;
        @NotBlank
        private String receiverPhone;
        @NotBlank
        private String receiverAddress;
    }
}
