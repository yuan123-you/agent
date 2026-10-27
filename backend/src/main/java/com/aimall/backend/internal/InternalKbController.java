package com.aimall.backend.internal;

import com.fasterxml.jackson.annotation.JsonAlias;
import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.KbChunk;
import com.aimall.backend.entity.KbDoc;
import com.aimall.backend.mapper.KbChunkMapper;
import com.aimall.backend.mapper.KbDocMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * 知识库内部回调：分块落库（预分配 id）+ 摄取结果回写 + 关键词检索（RAG 向量不可用时的兜底）
 */
@RestController
@RequestMapping("/internal/kb")
@RequiredArgsConstructor
public class InternalKbController {

    private final KbDocMapper kbDocMapper;
    private final KbChunkMapper kbChunkMapper;
    private final Bm25Retriever bm25Retriever;

    @Data
    public static class ChunkItem {
        private Integer chunkIndex;
        private String content;
        private Integer tokenCount;
    }

    @Data
    public static class ChunksBatchBody {
        private Long docId;
        @JsonAlias("version")
        private Integer docVersion;
        private List<ChunkItem> chunks;
    }

    @Data
    public static class ResultBody {
        private Long docId;
        @JsonAlias("version")
        private Integer docVersion;
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
    @Transactional
    public ApiResponse<Map<String, Object>> chunksBatch(@RequestBody ChunksBatchBody body) {
        KbDoc doc = requireProcessingTask(body.getDocId(), body.getDocVersion());
        List<Long> ids = new ArrayList<>();
        for (ChunkItem chunk : body.getChunks()) {
            KbChunk row = new KbChunk();
            row.setDocId(doc.getId());
            row.setProductId(doc.getProductId());
            row.setDocType(doc.getDocType());
            row.setDocVersion(body.getDocVersion());
            row.setChunkIndex(chunk.getChunkIndex());
            row.setContent(chunk.getContent());
            row.setTokenCount(chunk.getTokenCount() == null ? 0 : chunk.getTokenCount());
            kbChunkMapper.insert(row);
            ids.add(row.getId());
        }
        return ApiResponse.ok(Map.of("ids", ids));
    }

    /** 摄取结果回写：仅接受当前 PROCESSING 任务的 ACTIVE / FAILED。 */
    @PostMapping("/result")
    @Transactional
    public ApiResponse<Void> result(@RequestBody ResultBody body) {
        if (!"ACTIVE".equals(body.getStatus()) && !"FAILED".equals(body.getStatus())) {
            throw new BizException(2001, "摄取结果须为 ACTIVE 或 FAILED");
        }
        KbDoc doc = requireProcessingTask(body.getDocId(), body.getDocVersion());
        KbDoc upd = new KbDoc();
        upd.setStatus(body.getStatus());
        upd.setChunkCount(body.getChunkCount());
        upd.setVectorCount(body.getVectorCount());
        upd.setFailReason(body.getFailReason());
        int changed = kbDocMapper.update(upd, new LambdaUpdateWrapper<KbDoc>()
                .eq(KbDoc::getId, doc.getId())
                .eq(KbDoc::getVersion, body.getDocVersion())
                .eq(KbDoc::getStatus, "PROCESSING"));
        if (changed != 1) {
            throw new BizException(2001, "摄取任务已失效");
        }
        if ("ACTIVE".equals(body.getStatus())) {
            kbChunkMapper.delete(new LambdaQueryWrapper<KbChunk>()
                    .eq(KbChunk::getDocId, doc.getId())
                    .ne(KbChunk::getDocVersion, body.getDocVersion()));
        }
        return ApiResponse.ok();
    }

    // The row lock is held by the callback transaction through all chunk writes/pruning.
    private KbDoc requireProcessingTask(Long docId, Integer docVersion) {
        if (docId == null || docVersion == null || docVersion < 1) {
            throw new BizException(2001, "摄取回调缺少有效文档版本");
        }
        KbDoc doc = kbDocMapper.selectForUpdate(docId);
        if (doc == null) {
            throw new BizException(2002, "文档不存在");
        }
        if (!"PROCESSING".equals(doc.getStatus()) || !Objects.equals(docVersion, doc.getVersion())) {
            throw new BizException(2001, "摄取任务已失效");
        }
        return doc;
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
     * Exact in-process BM25 retrieval across storage-valid ACTIVE knowledge-base chunks.
     * Apply request scope before ranking/LIMIT; the AI pipeline also validates metadata.
     */
    @PostMapping("/search")
    public ApiResponse<Map<String, Object>> search(@RequestBody SearchBody body) {
        Map<String, Object> data = new HashMap<>();
        if (body.getQuery() == null || body.getQuery().isBlank()) {
            data.put("hits", List.of());
            data.put("total", 0);
            return ApiResponse.ok(data);
        }

        QueryWrapper<KbDoc> scope = new QueryWrapper<KbDoc>()
                .eq("status", "ACTIVE").eq("deleted", 0)
                .eq(body.getDocType() != null && !body.getDocType().isBlank()
                        && !"ALL".equals(body.getDocType()), "doc_type", body.getDocType());
        if (body.getProductId() != null) {
            scope.and(w -> w.eq("product_id", body.getProductId())
                    .or().isNull("product_id").or().eq("product_id", -1L));
        }
        List<KbDoc> docs = kbDocMapper.selectList(scope);
        if (docs.isEmpty()) {
            data.put("hits", List.of());
            data.put("total", 0);
            return ApiResponse.ok(data);
        }

        Map<Long, KbDoc> docsById = new HashMap<>();
        for (KbDoc doc : docs) {
            docsById.put(doc.getId(), doc);
        }
        List<KbChunk> chunks = kbChunkMapper.selectList(new QueryWrapper<KbChunk>()
                .in("doc_id", docsById.keySet())
                .apply("doc_version = (SELECT version FROM kb_doc WHERE id = kb_chunk.doc_id)"));
        List<Bm25Retriever.Document> corpus = chunks.stream()
                .filter(chunk -> body.getDocType() == null || body.getDocType().isBlank()
                        || "ALL".equals(body.getDocType()) || body.getDocType().equals(chunk.getDocType()))
                .filter(chunk -> body.getProductId() == null || chunk.getProductId() == null
                        || Long.valueOf(-1).equals(chunk.getProductId())
                        || body.getProductId().equals(chunk.getProductId()))
                .map(chunk -> {
                    KbDoc doc = docsById.get(chunk.getDocId());
                    return new Bm25Retriever.Document(chunk.getId(), chunk.getDocId(), chunk.getProductId(),
                            chunk.getDocType(), chunk.getContent(), doc.getTitle());
                })
                .toList();
        List<Bm25Retriever.Hit> matches = bm25Retriever.search(body.getQuery(), corpus,
                body.getTopK() == null ? 20 : body.getTopK());
        List<Map<String, Object>> hits = matches.stream().map(match -> {
            Bm25Retriever.Document document = match.document();
            Map<String, Object> hit = new HashMap<>();
            hit.put("chunk_id", document.chunkId());
            hit.put("doc_id", document.docId());
            hit.put("product_id", document.productId());
            hit.put("docType", document.docType());
            hit.put("content", document.content());
            hit.put("source", document.source());
            hit.put("score", match.score());
            return hit;
        }).toList();
        data.put("hits", hits);
        data.put("total", hits.size());
        return ApiResponse.ok(data);
    }
}
