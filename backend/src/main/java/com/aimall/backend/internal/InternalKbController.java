package com.aimall.backend.internal;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.KbChunk;
import com.aimall.backend.entity.KbDoc;
import com.aimall.backend.mapper.KbChunkMapper;
import com.aimall.backend.mapper.KbDocMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

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
     * Exact in-process BM25 retrieval across storage-valid ACTIVE knowledge-base chunks.
     * Request-side document filters intentionally belong to the AI pipeline after both legs return.
     */
    @PostMapping("/search")
    public ApiResponse<Map<String, Object>> search(@RequestBody SearchBody body) {
        Map<String, Object> data = new HashMap<>();
        if (body.getQuery() == null || body.getQuery().isBlank()) {
            data.put("hits", List.of());
            data.put("total", 0);
            return ApiResponse.ok(data);
        }

        List<KbDoc> docs = kbDocMapper.selectList(new QueryWrapper<KbDoc>()
                .eq("status", "ACTIVE")
                .eq("deleted", 0));
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
