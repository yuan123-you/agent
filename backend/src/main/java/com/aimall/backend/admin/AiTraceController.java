package com.aimall.backend.admin;
import com.aimall.backend.chat.AiTraceService;
import com.aimall.backend.common.*;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/admin/ai-traces")
@RequiredArgsConstructor
public class AiTraceController {
    private final AiTraceService service;
    @GetMapping
    public ApiResponse<PageResult<Map<String,Object>>> list(
            @RequestParam(required=false) String status, @RequestParam(required=false) Long conversationId,
            @RequestParam(required=false) String query, @RequestParam(defaultValue="1") long page,
            @RequestParam(defaultValue="20") long size) {
        return ApiResponse.ok(service.list(status,conversationId,query,page,size));
    }
    @GetMapping("/benchmark")
    public ApiResponse<Map<String,Object>> benchmark() {
        return ApiResponse.ok(service.getLatestBenchmark());
    }

    @GetMapping("/{traceId}")
    public ApiResponse<Map<String,Object>> detail(@PathVariable String traceId) { return ApiResponse.ok(service.detail(traceId)); }
}
