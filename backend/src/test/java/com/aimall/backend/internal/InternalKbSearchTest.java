package com.aimall.backend.internal;

import com.aimall.backend.entity.KbChunk;
import com.aimall.backend.entity.KbDoc;
import com.aimall.backend.mapper.KbChunkMapper;
import com.aimall.backend.mapper.KbDocMapper;
import com.baomidou.mybatisplus.core.conditions.Wrapper;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@SuppressWarnings("unchecked")
class InternalKbSearchTest {
    private final KbDocMapper kbDocMapper = mock(KbDocMapper.class);
    private final KbChunkMapper kbChunkMapper = mock(KbChunkMapper.class);
    private final InternalKbController controller = new InternalKbController(
            kbDocMapper, kbChunkMapper, new Bm25Retriever(1.5, 0.75));

    @Test void searchUsesOnlyActiveDocumentsAndReturnsCompleteHitMetadata() {
        KbDoc active = doc(10L, "ACTIVE", 100L, "POLICY", "退换货条款");
        KbDoc inactive = doc(11L, "DISABLED", 101L, "FAQ", "不应加载");
        List<KbDoc> storedDocs = List.of(active, inactive);
        KbChunk activeChunk = chunk(1L, 10L, 100L, "POLICY", "七天无理由退货");
        when(kbDocMapper.selectList(any())).thenAnswer(invocation -> storedDocs.stream()
                .filter(doc -> "ACTIVE".equals(doc.getStatus()) && Integer.valueOf(0).equals(doc.getDeleted()))
                .toList());
        when(kbChunkMapper.selectList(any())).thenReturn(List.of(activeChunk));

        InternalKbController.SearchBody body = new InternalKbController.SearchBody();
        body.setQuery("无理由退货");
        body.setDocType("FAQ");
        body.setProductId(999L);
        body.setTopK(20);
        Map<String, Object> data = controller.search(body).getData();

        @SuppressWarnings("unchecked")
        Map<String, Object> hit = ((List<Map<String, Object>>) data.get("hits")).get(0);
        assertEquals(1L, hit.get("chunk_id"));
        assertEquals(10L, hit.get("doc_id"));
        assertTrue(hit.containsKey("product_id"));
        assertEquals("POLICY", hit.get("docType"));
        assertEquals("退换货条款", hit.get("source"));
        assertTrue(((Number) hit.get("score")).doubleValue() > 0);

        ArgumentCaptor<Wrapper<KbDoc>> docs = ArgumentCaptor.forClass(Wrapper.class);
        ArgumentCaptor<Wrapper<KbChunk>> chunks = ArgumentCaptor.forClass(Wrapper.class);
        verify(kbDocMapper).selectList(docs.capture());
        verify(kbChunkMapper).selectList(chunks.capture());
        assertTrue(docs.getValue().getSqlSegment().contains("status"));
        assertTrue(docs.getValue().getSqlSegment().contains("deleted"));
        assertTrue(chunks.getValue().getSqlSegment().contains("doc_id"));
        assertTrue(params(chunks.getValue()).containsValue(10L));
    }

    @Test void searchDefaultsTopKToTwenty() {
        Bm25Retriever retriever = mock(Bm25Retriever.class);
        InternalKbController defaultLimitController = new InternalKbController(kbDocMapper, kbChunkMapper, retriever);
        KbDoc active = doc(10L, "ACTIVE", 100L, "POLICY", "退换货条款");
        KbChunk activeChunk = chunk(1L, 10L, 100L, "POLICY", "七天无理由退货");
        Bm25Retriever.Document document = new Bm25Retriever.Document(1L, 10L, 100L,
                "POLICY", "七天无理由退货", "退换货条款");
        when(kbDocMapper.selectList(any())).thenReturn(List.of(active));
        when(kbChunkMapper.selectList(any())).thenReturn(List.of(activeChunk));
        when(retriever.search(eq("无理由退货"), anyList(), eq(20)))
                .thenReturn(List.of(new Bm25Retriever.Hit(document, 1.0)));

        InternalKbController.SearchBody body = new InternalKbController.SearchBody();
        body.setQuery("无理由退货");
        Map<String, Object> data = defaultLimitController.search(body).getData();

        assertEquals(1, ((List<?>) data.get("hits")).size());
        verify(retriever).search(eq("无理由退货"), anyList(), eq(20));
    }
    private Map<String, Object> params(Wrapper<?> wrapper) {
        return ((com.baomidou.mybatisplus.core.conditions.AbstractWrapper<?, ?, ?>) wrapper).getParamNameValuePairs();
    }

    private KbDoc doc(Long id, String status, Long productId, String docType, String title) {
        KbDoc doc = new KbDoc();
        doc.setId(id); doc.setStatus(status); doc.setDeleted(0); doc.setProductId(productId);
        doc.setDocType(docType); doc.setTitle(title);
        return doc;
    }

    private KbChunk chunk(Long id, Long docId, Long productId, String docType, String content) {
        KbChunk chunk = new KbChunk();
        chunk.setId(id); chunk.setDocId(docId); chunk.setProductId(productId);
        chunk.setDocType(docType); chunk.setContent(content);
        return chunk;
    }
}
