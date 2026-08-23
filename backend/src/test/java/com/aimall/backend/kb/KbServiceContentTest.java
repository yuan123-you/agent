package com.aimall.backend.kb;

import com.aimall.backend.chat.AiClient;
import com.aimall.backend.common.BizException;
import com.aimall.backend.config.ObjectStorage;
import com.aimall.backend.entity.KbDoc;
import com.aimall.backend.mapper.KbChunkMapper;
import com.aimall.backend.mapper.KbDocMapper;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class KbServiceContentTest {
    private final KbDocMapper docMapper = mock(KbDocMapper.class);
    private final ObjectStorage storage = mock(ObjectStorage.class);
    private final KbService service = new KbService(
            docMapper, mock(KbChunkMapper.class), mock(AiClient.class), storage);

    @Test
    void contentLoadsTheStoredSourceDocument() throws Exception {
        KbDoc doc = document("policy.md", "MD");
        byte[] bytes = "# 退换货政策".getBytes(StandardCharsets.UTF_8);
        when(docMapper.selectById(12L)).thenReturn(doc);
        when(storage.get("policy.md")).thenReturn(bytes);

        KbService.DocumentContent content = service.content(12L);

        assertEquals("退换货政策", content.title());
        assertEquals("MD", content.format());
        assertArrayEquals(bytes, content.bytes());
        verify(storage).get("policy.md");
    }

    @Test
    void contentReportsStorageReadFailures() throws Exception {
        when(docMapper.selectById(12L)).thenReturn(document("missing.pdf", "PDF"));
        when(storage.get("missing.pdf")).thenThrow(new IllegalStateException("not found"));

        BizException error = assertThrows(BizException.class, () -> service.content(12L));

        assertEquals(3001, error.getCode());
        assertEquals("文件读取失败", error.getMessage());
    }

    private KbDoc document(String fileUrl, String format) {
        KbDoc doc = new KbDoc();
        doc.setId(12L);
        doc.setTitle("退换货政策");
        doc.setFileUrl(fileUrl);
        doc.setFileFormat(format);
        return doc;
    }
}
