package com.aimall.backend.kb;

import com.aimall.backend.chat.AiClient;
import com.aimall.backend.common.BizException;
import com.aimall.backend.config.ObjectStorage;
import com.aimall.backend.entity.KbChunk;
import com.aimall.backend.entity.KbDoc;
import com.aimall.backend.mapper.KbChunkMapper;
import com.aimall.backend.mapper.KbDocMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.ClassPathResource;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * 知识库服务：上传 → 异步摄取（AI 服务）→ 状态回写；停用/重建/删除；
 * 含平台规则种子文档自动播种（启动导入 + 定时自愈重试）
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class KbService {

    private static final Set<String> ALLOWED_FORMATS = Set.of("PDF", "MD", "TXT");
    private static final Set<String> ALLOWED_TYPES = Set.of("FAQ", "INTRO", "POLICY");

    /** 平台规则种子知识库（AI 回答售后/政策类问题的依据，启动自动播种） */
    public static final String SEED_POLICY_TITLE = "AI Mall 平台服务规则知识库";
    public static final String SEED_POLICY_FILE = "seed-platform-policies.md";
    private static final String SEED_POLICY_CLASSPATH = "kbseed/platform-policies.md";

    private final KbDocMapper kbDocMapper;
    private final KbChunkMapper kbChunkMapper;
    private final AiClient aiClient;
    private final ObjectStorage storage;

    public KbDoc upload(MultipartFile file, Long productId, String title, String docType, Long userId) {
        String format = extOf(file.getOriginalFilename());
        if (!ALLOWED_FORMATS.contains(format)) {
            throw new BizException(2007, "仅支持 PDF/MD/TXT 格式");
        }
        if (!ALLOWED_TYPES.contains(docType)) {
            throw new BizException(2001, "文档类型须为 FAQ/INTRO/POLICY");
        }
        // 存储文件到对象存储（UUID 重命名）
        String storedName;
        try {
            storedName = UUID.randomUUID().toString().replace("-", "") + "." + format.toLowerCase(Locale.ROOT);
            storage.put(storedName, file.getInputStream(), file.getContentType());
        } catch (Exception e) {
            throw new BizException(3001, "文件保存失败：" + e.getMessage());
        }
        // 落库 PENDING
        KbDoc doc = new KbDoc();
        doc.setProductId(productId);
        doc.setTitle(title);
        doc.setDocType(docType);
        doc.setFileUrl(storedName);
        doc.setFileFormat(format);
        doc.setStatus("PENDING");
        doc.setVersion(1);
        doc.setCreatedBy(userId);
        kbDocMapper.insert(doc);
        // 触发摄取（PROCESSING）
        markStatus(doc.getId(), "PROCESSING", null);
        doc.setStatus("PROCESSING");
        triggerIngest(doc);
        return doc;
    }

    public void triggerIngest(KbDoc doc) {
        Map<String, Object> body = new HashMap<>();
        body.put("doc_id", doc.getId());
        body.put("product_id", doc.getProductId());
        body.put("doc_type", doc.getDocType());
        body.put("doc_version", doc.getVersion());
        body.put("file_url", "/internal/files/" + doc.getId());
        body.put("file_format", doc.getFileFormat());
        aiClient.triggerIngest(body).subscribe(
                ok -> { },
                e -> {
                    log.warn("trigger ingest failed doc={}: {}", doc.getId(), e.getMessage());
                    markStatus(doc.getId(), "FAILED", "AI 服务不可达: " + e.getMessage());
                }
        );
    }

    /** Scheduler entry point: mark one seed PROCESSING before asynchronously dispatching it. */
    public void dispatchSeedDocument(KbDoc doc) {
        markStatus(doc.getId(), "PROCESSING", null);
        doc.setStatus("PROCESSING");
        triggerIngest(doc);
    }
    /** 停用：删除 Milvus 向量（检索即失效）；启用：重建索引 */
    public void toggleStatus(Long id, String status) {
        KbDoc doc = requireDoc(id);
        if ("DISABLED".equals(status)) {
            blockDelete(doc, 0);
            markStatus(id, "DISABLED", null);
        } else if ("ACTIVE".equals(status)) {
            if ("ACTIVE".equals(doc.getStatus())) {
                return;
            }
            reindex(id);
        } else {
            throw new BizException(2001, "状态须为 ACTIVE 或 DISABLED");
        }
    }

    /** 重建索引：version+1 → PROCESSING → 摄取（成功后 AI 侧清理旧版本向量） */
    public void reindex(Long id) {
        KbDoc doc = requireDoc(id);
        KbDoc upd = new KbDoc();
        upd.setId(doc.getId());
        upd.setVersion(doc.getVersion() + 1);
        upd.setStatus("PROCESSING");
        kbDocMapper.updateById(upd);
        doc.setVersion(doc.getVersion() + 1);
        doc.setStatus("PROCESSING");
        triggerIngest(doc);
    }

    /** 删除：清向量 + 清分块 + 软删文档 */
    public void delete(Long id) {
        KbDoc doc = requireDoc(id);
        blockDelete(doc, 0);
        kbChunkMapper.delete(new LambdaQueryWrapper<KbChunk>().eq(KbChunk::getDocId, id));
        kbDocMapper.deleteById(id);
    }

    public Page<KbDoc> list(String status, long page, long size) {
        return kbDocMapper.selectPage(new Page<>(page, size),
                new LambdaQueryWrapper<KbDoc>()
                        .eq(status != null && !status.isBlank(), KbDoc::getStatus, status)
                        .orderByDesc(KbDoc::getId));
    }

    // ---------- 种子知识库（平台规则） ----------

    /** 确保种子文档存在（幂等）：不存在则落库 PENDING 并复制文件 */
    @Transactional
    public KbDoc ensureSeedPolicy() {
        KbDoc exist = kbDocMapper.selectOne(new LambdaQueryWrapper<KbDoc>()
                .eq(KbDoc::getTitle, SEED_POLICY_TITLE)
                .last("LIMIT 1"));
        if (exist != null) {
            return exist;
        }
        try (var in = new ClassPathResource(SEED_POLICY_CLASSPATH).getInputStream()) {
            storage.put(SEED_POLICY_FILE, in, "text/markdown");
        } catch (Exception e) {
            log.error("seed policy file upload failed: {}", e.getMessage());
            return null;
        }
        KbDoc doc = new KbDoc();
        doc.setProductId(null);
        doc.setTitle(SEED_POLICY_TITLE);
        doc.setDocType("POLICY");
        doc.setFileUrl(SEED_POLICY_FILE);
        doc.setFileFormat("MD");
        doc.setStatus("PENDING");
        doc.setVersion(1);
        doc.setCreatedBy(1L);
        kbDocMapper.insert(doc);
        log.info("seed policy doc created: id={} title={}", doc.getId(), SEED_POLICY_TITLE);
        return doc;
    }

    /** 启动播种：存在未生效种子则置 PROCESSING 并触发摄取（失败由定时任务自愈重试） */
    public void seedPolicyIfNeeded() {
        try {
            KbDoc doc = ensureSeedPolicy();
            if (doc == null || "ACTIVE".equals(doc.getStatus())) {
                return;
            }
            markSeedProcessing(doc);
            triggerIngest(doc);
            log.info("seed policy ingest triggered: id={}", doc.getId());
        } catch (Exception e) {
            log.warn("seed policy trigger failed: {}", e.getMessage());
        }
    }

    /** 定时自愈：种子未生效（FAILED 或卡住超 2 分钟）则重试摄取（LLM 配置修复后自动恢复） */
    @Scheduled(fixedDelay = 90_000, initialDelay = 60_000)
    public void seedPolicyRetry() {
        try {
            KbDoc doc = kbDocMapper.selectOne(new LambdaQueryWrapper<KbDoc>()
                    .eq(KbDoc::getTitle, SEED_POLICY_TITLE)
                    .last("LIMIT 1"));
            if (doc == null || "ACTIVE".equals(doc.getStatus())) {
                return;
            }
            boolean failed = "FAILED".equals(doc.getStatus());
            boolean stuck = doc.getUpdatedAt() != null
                    && doc.getUpdatedAt().isBefore(LocalDateTime.now().minusSeconds(120));
            if (failed || stuck) {
                log.info("seed policy retry: id={} status={}", doc.getId(), doc.getStatus());
                markSeedProcessing(doc);
                triggerIngest(doc);
            }
        } catch (Exception e) {
            log.warn("seed policy retry failed: {}", e.getMessage());
        }
    }

    private void markSeedProcessing(KbDoc doc) {
        KbDoc upd = new KbDoc();
        upd.setId(doc.getId());
        upd.setStatus("PROCESSING");
        upd.setFailReason(null);
        kbDocMapper.updateById(upd);
        doc.setStatus("PROCESSING");
    }

    public KbDoc requireDoc(Long id) {
        KbDoc doc = kbDocMapper.selectById(id);
        if (doc == null) {
            throw new BizException(2002, "文档不存在");
        }
        return doc;
    }

    private void blockDelete(KbDoc doc, int keepVersion) {
        try {
            aiClient.deleteVectors(doc.getId(), keepVersion).block(Duration.ofSeconds(10));
        } catch (Exception e) {
            log.warn("delete vectors failed doc={}: {}", doc.getId(), e.getMessage());
        }
    }

    private void markStatus(Long id, String status, String failReason) {
        KbDoc upd = new KbDoc();
        upd.setId(id);
        upd.setStatus(status);
        upd.setFailReason(failReason);
        kbDocMapper.updateById(upd);
    }

    private String extOf(String filename) {
        if (filename == null) {
            return "";
        }
        int idx = filename.lastIndexOf('.');
        return idx < 0 ? "" : filename.substring(idx + 1).toUpperCase(Locale.ROOT);
    }
}

