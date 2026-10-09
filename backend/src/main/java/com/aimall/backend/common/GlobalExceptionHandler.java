package com.aimall.backend.common;

import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.multipart.MaxUploadSizeExceededException;

/**
 * 全局异常处理：非流式接口统一返回 JSON 响应体
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(BizException.class)
    public ResponseEntity<ApiResponse<Void>> handleBiz(BizException e) {
        HttpStatus status = switch (e.getCode()) {
            case 1001, 1003, 1004 -> HttpStatus.UNAUTHORIZED;
            case 1002, 2003 -> HttpStatus.FORBIDDEN;
            case 1005 -> HttpStatus.TOO_MANY_REQUESTS;
            case 2002 -> HttpStatus.NOT_FOUND;
            case 2004 -> HttpStatus.CONFLICT;
            case 5001, 5003 -> HttpStatus.BAD_GATEWAY;
            case 5002 -> HttpStatus.SERVICE_UNAVAILABLE;
            default -> HttpStatus.BAD_REQUEST;
        };
        return ResponseEntity.status(status).body(ApiResponse.fail(e.getCode(), e.getMessage()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiResponse<Void>> handleValid(MethodArgumentNotValidException e) {
        String msg = e.getBindingResult().getFieldErrors().stream()
                .map(f -> f.getField() + " " + f.getDefaultMessage())
                .findFirst().orElse("参数校验失败");
        return ResponseEntity.badRequest().body(ApiResponse.fail(2001, msg));
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<ApiResponse<Void>> handleUnreadableBody(HttpMessageNotReadableException e) {
        // Parser details can contain raw request values; expose only a stable protocol error.
        return ResponseEntity.badRequest().body(ApiResponse.fail(2001, "请求体格式错误或字段类型不合法"));
    }

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public ResponseEntity<ApiResponse<Void>> handleLongPathBinding(MethodArgumentTypeMismatchException e) {
        if (e.getRequiredType() == Long.class
                && e.getParameter().hasParameterAnnotation(PathVariable.class)) {
            return ResponseEntity.badRequest().body(ApiResponse.fail(2001, "路径参数必须为合法整数"));
        }
        // Do not broaden this proven path fix to query parameters or unrelated binding policies.
        return handleOther(e);
    }

    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public ResponseEntity<ApiResponse<Void>> handleUpload(MaxUploadSizeExceededException e) {
        return ResponseEntity.badRequest().body(ApiResponse.fail(2007, "文件大小超出限制（20MB）"));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> handleOther(Exception e) {
        log.error("unexpected error", e);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(ApiResponse.fail(9999, "系统繁忙，请稍后重试"));
    }
}
