package com.aimall.backend.common;

import lombok.AllArgsConstructor;
import lombok.Data;

/**
 * 统一响应体：{code, message, data, traceId}
 */
@Data
@AllArgsConstructor
public class ApiResponse<T> {

    private int code;
    private String message;
    private T data;
    private String traceId;

    public static <T> ApiResponse<T> ok(T data) {
        return new ApiResponse<>(0, "success", data, null);
    }

    public static ApiResponse<Void> ok() {
        return new ApiResponse<>(0, "success", null, null);
    }

    public static ApiResponse<Void> fail(int code, String message) {
        return new ApiResponse<>(code, message, null, null);
    }
}
