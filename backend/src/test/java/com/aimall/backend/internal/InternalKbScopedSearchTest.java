package com.aimall.backend.internal;

import com.aimall.backend.entity.KbDoc;
import com.aimall.backend.entity.KbChunk;
import com.aimall.backend.mapper.KbDocMapper;
import com.aimall.backend.mapper.KbChunkMapper;
import org.junit.jupiter.api.Test;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class InternalKbScopedSearchTest {
    @Test @SuppressWarnings("unchecked") void scopeIsAppliedBeforeTopTwentyAndKeepsGlobalDocs() {
        var docs = mock(KbDocMapper.class); var chunks = mock(KbChunkMapper.class);
        var controller = new InternalKbController(docs, chunks, new Bm25Retriever());
        List<KbDoc> documentRows = new ArrayList<>(); List<KbChunk> chunkRows = new ArrayList<>();
        for (long i = 1; i <= 24; i++) {
            Long productId = null;
            if (i <= 21) productId = 999L;
            else if (i == 22) productId = 7L;
            else if (i == 24) productId = -1L;
            var doc = new KbDoc(); doc.setId(i); doc.setStatus("ACTIVE"); doc.setDeleted(0);
            doc.setProductId(productId); doc.setDocType("POLICY"); doc.setTitle("退货政策"); documentRows.add(doc);
            var chunk = new KbChunk(); chunk.setId(i); chunk.setDocId(i); chunk.setProductId(productId);
            chunk.setDocType("POLICY"); chunk.setContent("七天退货期限"); chunkRows.add(chunk);
        }
        when(docs.selectList(any())).thenReturn(documentRows);
        when(chunks.selectList(any())).thenReturn(chunkRows);
        var request = new InternalKbController.SearchBody(); request.setQuery("退货期限");
        request.setProductId(7L); request.setDocType("POLICY"); request.setTopK(20);
        var hits = (List<Map<String,Object>>) controller.search(request).getData().get("hits");
        assertEquals(List.of(22L,23L,24L), hits.stream().map(h -> h.get("chunk_id")).toList());
        request.setDocType("FAQ");
        assertEquals(List.of(), controller.search(request).getData().get("hits"));
    }
}
