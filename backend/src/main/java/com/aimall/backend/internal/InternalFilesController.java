package com.aimall.backend.internal;

import com.aimall.backend.common.BizException;
import com.aimall.backend.config.ObjectStorage;
import com.aimall.backend.entity.KbDoc;
import com.aimall.backend.mapper.KbDocMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 内部文件服务：AI 服务下载知识库源文件（内网 + 内部令牌，文件存储于对象存储 MinIO）
 */
@RestController
@RequestMapping("/internal/files")
@RequiredArgsConstructor
public class InternalFilesController {

    private final KbDocMapper kbDocMapper;
    private final ObjectStorage storage;

    @GetMapping("/{docId}")
    public ResponseEntity<byte[]> download(@PathVariable Long docId) {
        KbDoc doc = kbDocMapper.selectById(docId);
        if (doc == null) {
            throw new BizException(2002, "文档不存在");
        }
        try {
            byte[] data = storage.get(doc.getFileUrl());
            return ResponseEntity.ok()
                    .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=" + doc.getFileUrl())
                    .contentType(MediaType.APPLICATION_OCTET_STREAM)
                    .body(data);
        } catch (Exception e) {
            throw new BizException(2002, "文件读取失败：" + e.getMessage());
        }
    }
}
