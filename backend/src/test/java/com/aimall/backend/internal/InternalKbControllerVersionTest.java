package com.aimall.backend.internal;

import com.aimall.backend.common.ApiResponse;
import com.aimall.backend.entity.KbChunk;
import com.aimall.backend.entity.KbDoc;
import com.aimall.backend.mapper.KbChunkMapper;
import com.aimall.backend.mapper.KbDocMapper;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.conditions.Wrapper;
import com.baomidou.mybatisplus.core.metadata.TableInfoHelper;
import org.apache.ibatis.builder.MapperBuilderAssistant;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class InternalKbControllerVersionTest {
    @BeforeAll
    static void initializeMybatisMetadata() {
        TableInfoHelper.initTableInfo(new MapperBuilderAssistant(new MybatisConfiguration(), ""), KbChunk.class);
    }

    private final KbDocMapper docMapper = mock(KbDocMapper.class);
    private final KbChunkMapper chunkMapper = mock(KbChunkMapper.class);
    private final Bm25Retriever bm25Retriever = mock(Bm25Retriever.class);
    private final InternalKbController controller = new InternalKbController(docMapper, chunkMapper, bm25Retriever);

    @Test
    void keywordSearchRestrictsChunksToTheCurrentDocumentVersion() {
        InternalKbController.SearchBody body = new InternalKbController.SearchBody();
        body.setQuery("退货政策");
        when(docMapper.selectList(any())).thenReturn(List.of(doc(1L, "ACTIVE", 2, "退货政策")));
        when(chunkMapper.selectList(any())).thenReturn(List.of());

        controller.search(body);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Wrapper<KbChunk>> captor = ArgumentCaptor.forClass(Wrapper.class);
        verify(chunkMapper).selectList(captor.capture());
        String sql = captor.getValue().getSqlSegment();
        assertTrue(sql.contains("doc_version"), sql);
        assertTrue(sql.contains("SELECT version FROM kb_doc"), sql);
    }

    @Test
    void activeIngestPrunesSupersededRelationalChunks() {
        KbDoc doc = doc(7L, "ACTIVE", 3, "退换货政策");
        when(docMapper.selectById(7L)).thenReturn(doc);
        InternalKbController.ResultBody body = new InternalKbController.ResultBody();
        body.setDocId(7L);
        body.setStatus("ACTIVE");
        body.setChunkCount(4);

        controller.result(body);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Wrapper<KbChunk>> captor = ArgumentCaptor.forClass(Wrapper.class);
        verify(chunkMapper).delete(captor.capture());
        String sql = captor.getValue().getSqlSegment();
        assertTrue(sql.contains("doc_id"), sql);
        assertTrue(sql.contains("doc_version"), sql);
        verify(docMapper).updateById(any(KbDoc.class));
    }

    @Test
    void currentChunksReturnsOnlyActiveChunksAtTheOwningDocumentVersion() {
        KbChunk current = chunk(11L, 1L, 2);
        KbChunk old = chunk(12L, 1L, 1);
        KbChunk disabled = chunk(13L, 2L, 4);
        when(chunkMapper.selectBatchIds(List.of(11L, 12L, 13L, 99L)))
                .thenReturn(List.of(current, old, disabled));
        when(docMapper.selectBatchIds(List.of(1L, 2L))).thenReturn(List.of(
                doc(1L, "ACTIVE", 2, "现行政策"),
                doc(2L, "DISABLED", 4, "停用政策")
        ));
        InternalKbController.CurrentChunksBody body = new InternalKbController.CurrentChunksBody();
        body.setChunkIds(List.of(11L, 12L, 13L, 99L));

        ApiResponse<Map<String, String>> response = controller.currentChunks(body);

        assertEquals(Map.of("11", "现行政策"), response.getData());
    }

    private static KbChunk chunk(long id, long docId, int version) {
        KbChunk chunk = new KbChunk();
        chunk.setId(id);
        chunk.setDocId(docId);
        chunk.setDocVersion(version);
        return chunk;
    }

    private static KbDoc doc(long id, String status, int version, String title) {
        KbDoc doc = new KbDoc();
        doc.setId(id);
        doc.setStatus(status);
        doc.setVersion(version);
        doc.setTitle(title);
        return doc;
    }
}
