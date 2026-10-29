package com.aimall.backend.internal;
import com.aimall.backend.chat.AiTraceService;
import com.aimall.backend.common.ApiResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/internal/ai-traces")
@RequiredArgsConstructor
public class InternalAiTraceController {
    private final AiTraceService service;
    @PostMapping("/{traceId}")
    public ApiResponse<Void> update(@PathVariable String traceId,@RequestBody String payload) {
        service.record(traceId,payload); return ApiResponse.ok();
    }
}
