package com.aimall.backend.kb;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.common.PageResult;
import com.aimall.backend.entity.KbDoc;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.HashMap;
import java.util.Map;

/**
 * 知识库管理接口：/api/v1/admin/kb（仅 ADMIN）
 */
@RestController
@RequestMapping("/api/v1/admin/kb")
@RequiredArgsConstructor
public class KbAdminController {

    private final KbService kbService;

    @GetMapping("/docs")
    public ApiResponse<PageResult<Map<String, Object>>> list(
            @RequestParam(required = false) String status,
            @RequestParam(defaultValue = "1") long page,
            @RequestParam(defaultValue = "20") long size) {
        return ApiResponse.ok(PageResult.of(kbService.list(status, page, size), this::toVo));
    }

    @GetMapping("/docs/{id}")
    public ApiResponse<Map<String, Object>> detail(@PathVariable Long id) {
        return ApiResponse.ok(toVo(kbService.requireDoc(id)));
    }

    /** 上传知识文档：multipart(file + productId + title + docType) → 异步摄取 */
    @PostMapping("/docs")
    public ApiResponse<Map<String, Object>> upload(@RequestParam("file") MultipartFile file,
                                                   @RequestParam(value = "productId", required = false) Long productId,
                                                   @RequestParam("title") String title,
                                                   @RequestParam("docType") String docType,
                                                   @AuthenticationPrincipal Long userId) {
        KbDoc doc = kbService.upload(file, productId, title, docType, userId);
        return ApiResponse.ok(toVo(doc));
    }

    /** 启用/停用：停用即删向量（检索失效），启用即重建 */
    @PostMapping("/docs/{id}/status")
    public ApiResponse<Void> toggleStatus(@PathVariable Long id, @RequestBody Map<String, String> body) {
        kbService.toggleStatus(id, body.get("status"));
        return ApiResponse.ok();
    }

    @PostMapping("/docs/{id}/reindex")
    public ApiResponse<Void> reindex(@PathVariable Long id) {
        kbService.reindex(id);
        return ApiResponse.ok();
    }

    @DeleteMapping("/docs/{id}")
    public ApiResponse<Void> delete(@PathVariable Long id) {
        kbService.delete(id);
        return ApiResponse.ok();
    }

    private Map<String, Object> toVo(KbDoc doc) {
        Map<String, Object> vo = new HashMap<>();
        vo.put("docId", doc.getId());
        vo.put("productId", doc.getProductId());
        vo.put("title", doc.getTitle());
        vo.put("docType", doc.getDocType());
        vo.put("fileFormat", doc.getFileFormat());
        vo.put("status", doc.getStatus());
        vo.put("chunkCount", doc.getChunkCount());
        vo.put("failReason", doc.getFailReason());
        vo.put("version", doc.getVersion());
        vo.put("createdAt", doc.getCreatedAt());
        return vo;
    }
}
