package com.aimall.backend.internal;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.KbChunk;
import com.aimall.backend.entity.KbDoc;
import com.aimall.backend.mapper.KbChunkMapper;
import com.aimall.backend.mapper.KbDocMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 知识库内部回调：分块落库（预分配 id）+ 摄取结果回写 + 关键词检索（RAG 向量不可用时的兜底）
 */
@RestController
@RequestMapping("/internal/kb")
@RequiredArgsConstructor
public class InternalKbController {

    private final KbDocMapper kbDocMapper;
    private final KbChunkMapper kbChunkMapper;

    @Data
    public static class ChunkItem {
        private Integer chunkIndex;
        private String content;
        private Integer tokenCount;
    }

    @Data
    public static class ChunksBatchBody {
        private Long docId;
        private List<ChunkItem> chunks;
    }

    @Data
    public static class ResultBody {
        private Long docId;
        private String status;
        private Integer chunkCount;
        private Integer vectorCount;
        private String failReason;
    }

    @Data
    public static class SearchBody {
        private String query;
        private String docType;
        private Long productId;
        private Integer topK;
    }

    /** 分块元数据批量落库，返回预分配的 chunk id（= Milvus 主键） */
    @PostMapping("/chunks/batch")
    public ApiResponse<Map<String, Object>> chunksBatch(@RequestBody ChunksBatchBody body) {
        KbDoc doc = kbDocMapper.selectById(body.getDocId());
        if (doc == null) {
            throw new BizException(2002, "文档不存在");
        }
        List<Long> ids = new ArrayList<>();
        for (ChunkItem chunk : body.getChunks()) {
            KbChunk row = new KbChunk();
            row.setDocId(doc.getId());
            row.setProductId(doc.getProductId());
            row.setDocType(doc.getDocType());
            row.setDocVersion(doc.getVersion());
            row.setChunkIndex(chunk.getChunkIndex());
            row.setContent(chunk.getContent());
            row.setTokenCount(chunk.getTokenCount() == null ? 0 : chunk.getTokenCount());
            kbChunkMapper.insert(row);
            ids.add(row.getId());
        }
        return ApiResponse.ok(Map.of("ids", ids));
    }

    /** 摄取结果回写：ACTIVE / FAILED */
    @PostMapping("/result")
    public ApiResponse<Void> result(@RequestBody ResultBody body) {
        KbDoc doc = kbDocMapper.selectById(body.getDocId());
        if (doc == null) {
            throw new BizException(2002, "文档不存在");
        }
        if ("ACTIVE".equals(body.getStatus()) && doc.getVersion() != null) {
            kbChunkMapper.delete(new LambdaQueryWrapper<KbChunk>()
                    .eq(KbChunk::getDocId, doc.getId())
                    .ne(KbChunk::getDocVersion, doc.getVersion()));
        }
        KbDoc upd = new KbDoc();
        upd.setId(doc.getId());
        upd.setStatus(body.getStatus());
        if (body.getChunkCount() != null) {
            upd.setChunkCount(body.getChunkCount());
        }
        if (body.getVectorCount() != null) {
            upd.setVectorCount(body.getVectorCount());
        }
        if (body.getFailReason() != null) {
            upd.setFailReason(body.getFailReason());
        }
        kbDocMapper.updateById(upd);
        return ApiResponse.ok();
    }

    @Data
    public static class TitlesBody {
        private List<Long> docIds;
    }

    @Data
    public static class CurrentChunksBody {
        private List<Long> chunkIds;
    }

    /** 校验 Milvus 候选是否仍属于 ACTIVE 文档的当前版本，并返回 chunkId → title。 */
    @PostMapping("/chunks/current")
    public ApiResponse<Map<String, String>> currentChunks(@RequestBody CurrentChunksBody body) {
        if (body.getChunkIds() == null || body.getChunkIds().isEmpty()) {
            return ApiResponse.ok(Map.of());
        }
        List<KbChunk> chunks = kbChunkMapper.selectBatchIds(body.getChunkIds());
        if (chunks.isEmpty()) {
            return ApiResponse.ok(Map.of());
        }
        List<Long> docIds = chunks.stream().map(KbChunk::getDocId).distinct().toList();
        Map<Long, KbDoc> docs = new HashMap<>();
        for (KbDoc doc : kbDocMapper.selectBatchIds(docIds)) {
            docs.put(doc.getId(), doc);
        }
        Map<String, String> current = new HashMap<>();
        for (KbChunk chunk : chunks) {
            KbDoc doc = docs.get(chunk.getDocId());
            if (doc != null && "ACTIVE".equals(doc.getStatus())
                    && doc.getVersion() != null && doc.getVersion().equals(chunk.getDocVersion())) {
                current.put(String.valueOf(chunk.getId()), doc.getTitle());
            }
        }
        return ApiResponse.ok(current);
    }

    /** 文档标题批量查询（AI 向量检索命中后，将来源从内部编号映射为文档标题） */
    @PostMapping("/titles")
    public ApiResponse<Map<String, Object>> titles(@RequestBody TitlesBody body) {
        Map<String, Object> data = new HashMap<>();
        if (body.getDocIds() == null || body.getDocIds().isEmpty()) {
            return ApiResponse.ok(data);
        }
        List<KbDoc> docs = kbDocMapper.selectList(new LambdaQueryWrapper<KbDoc>()
                .in(KbDoc::getId, body.getDocIds()));
        for (KbDoc d : docs) {
            data.put(String.valueOf(d.getId()), d.getTitle());
        }
        return ApiResponse.ok(data);
    }

    /**
     * 关键词检索（RAG 兜底）：向量 Embedding 不可用时，AI 服务退化为本接口检索 ACTIVE 文档分块。
     * 检索逻辑：查询按空格/标点切词（≥2 字），任一词命中即召回，按命中词数排序。
     */
    @PostMapping("/search")
    public ApiResponse<Map<String, Object>> search(@RequestBody SearchBody body) {
        int topK = body.getTopK() == null ? 4 : Math.min(body.getTopK(), 10);
        List<String> terms = splitTerms(body.getQuery());
        Map<String, Object> data = new HashMap<>();
        if (terms.isEmpty()) {
            data.put("hits", List.of());
            data.put("total", 0);
            return ApiResponse.ok(data);
        }

        LambdaQueryWrapper<KbChunk> wrapper = new LambdaQueryWrapper<KbChunk>()
                .inSql(KbChunk::getDocId, "SELECT id FROM kb_doc WHERE status = 'ACTIVE' AND deleted = 0")
                .apply("doc_version = (SELECT version FROM kb_doc WHERE id = kb_chunk.doc_id)")
                .and(body.getDocType() != null && !"ALL".equals(body.getDocType())
                                && !body.getDocType().isBlank(),
                        w -> w.eq(KbChunk::getDocType, body.getDocType())
                                .or().isNull(KbChunk::getDocType))
                .and(w -> {
                    for (int i = 0; i < terms.size(); i++) {
                        if (i > 0) {
                            w.or();
                        }
                        w.like(KbChunk::getContent, terms.get(i));
                    }
                })
                .last("LIMIT 200");
        List<KbChunk> chunks = kbChunkMapper.selectList(wrapper);

        // 命中词数排序（相关性近似），稳定排序
        Map<Long, KbDoc> docCache = new HashMap<>();
        List<Map<String, Object>> hits = new ArrayList<>();
        for (KbChunk c : chunks) {
            int match = 0;
            for (String t : terms) {
                if (c.getContent() != null && c.getContent().contains(t)) {
                    match++;
                }
            }
            KbDoc doc = docCache.computeIfAbsent(c.getDocId(), id -> kbDocMapper.selectById(id));
            Map<String, Object> hit = new HashMap<>();
            hit.put("content", c.getContent());
            hit.put("chunk_id", c.getId());  // 双路 RRF 融合身份，与向量腿（Milvus 主键）对齐
            hit.put("source", doc != null ? doc.getTitle() : ("知识库文档#" + c.getDocId()));
            hit.put("docType", c.getDocType());
            hit.put("score", Math.min(0.9, 0.5 + match * 0.1));
            hit.put("_match", match);
            hits.add(hit);
        }
        hits.sort(Comparator.comparingInt(h -> -((int) h.get("_match"))));
        hits = hits.stream().limit(topK).peek(h -> h.remove("_match")).toList();

        data.put("hits", hits);
        data.put("total", hits.size());
        return ApiResponse.ok(data);
    }

    /** 中文查询切词：按空白/标点切分；数字与汉字间空格归一（"7 天"→"7天"）；
     * 长词（>8 字）追加 3-gram 滑窗提升召回；全量限 8 个词 */
    private List<String> splitTerms(String query) {
        Set<String> terms = new HashSet<>();
        if (query == null || query.isBlank()) {
            return List.of();
        }
        String normalized = query.trim()
                .replaceAll("(\\d)\\s+([\\u4e00-\\u9fa5\\d])", "$1$2")
                .replaceAll("([\\u4e00-\\u9fa5])\\s+(\\d)", "$1$2");
        for (String part : normalized.split("[\\s，。？?！!、,;；:：\"'（）()\\[\\]{}]+")) {
            String t = part.trim();
            if (t.length() < 2) {
                continue;
            }
            if (t.length() <= 8) {
                terms.add(t);
            } else {
                // 长句滑窗 3-gram（步长 2）
                for (int i = 0; i + 3 <= t.length(); i += 2) {
                    terms.add(t.substring(i, i + 3));
                    if (terms.size() >= 12) {
                        break;
                    }
                }
            }
        }
        if (terms.isEmpty() && normalized.length() >= 2) {
            terms.add(normalized.substring(0, Math.min(4, normalized.length())));
        }
        return List.copyOf(terms).stream().limit(8).toList();
    }
}
